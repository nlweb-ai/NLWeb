"""Phase 2: Train Neural GAM on top of fine-tuned ModernBERT embeddings.

Usage:
    python -m training.train_gam [--config config/training_config.yaml]

Takes pre-extracted BERT [CLS] embeddings + handcrafted features and trains
an interpretable Neural GAM scorer. Each feature's contribution can be
independently visualized.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.neural_gam import NeuralGAM, GAMDataset


def load_jsonl(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def prepare_features(examples: list[dict], schema_mapping: dict) -> dict:
    """Extract handcrafted features from examples as tensors."""
    return {
        "query_length": torch.tensor(
            [ex["query_length"] for ex in examples], dtype=torch.float32),
        "item_name_length": torch.tensor(
            [ex["item_name_length"] for ex in examples], dtype=torch.float32),
        "word_overlap": torch.tensor(
            [ex["query_item_word_overlap"] for ex in examples], dtype=torch.float32),
        "schema_type_idx": torch.tensor(
            [schema_mapping.get(
                ex["schema_type"][0] if isinstance(ex["schema_type"], list) else ex["schema_type"],
                len(schema_mapping))
             for ex in examples], dtype=torch.long),
        "difficulty": torch.tensor(
            [ex["difficulty"] for ex in examples], dtype=torch.float32),
    }


def normalize_features(features: dict, stats: dict = None) -> tuple[dict, dict]:
    """Normalize scalar features to zero mean, unit variance.

    Returns normalized features and stats dict (for inference).
    """
    if stats is None:
        stats = {}
        for key in ["query_length", "item_name_length", "word_overlap", "difficulty"]:
            vals = features[key]
            stats[key] = {"mean": vals.mean().item(), "std": vals.std().item() + 1e-8}

    normalized = dict(features)
    for key in ["query_length", "item_name_length", "word_overlap", "difficulty"]:
        normalized[key] = (features[key] - stats[key]["mean"]) / stats[key]["std"]

    return normalized, stats


def train_epoch(model, dataloader, optimizer, criterion, device):
    model.train()
    total_loss = 0
    n = 0

    for batch in dataloader:
        bert_emb = batch["bert_embedding"].to(device)
        targets = batch["score"].to(device).unsqueeze(1)

        features = {k: batch[k].to(device) for k in
                     ["query_length", "item_name_length", "word_overlap",
                      "schema_type_idx", "difficulty"]}

        optimizer.zero_grad()
        predictions = model(bert_emb, **features)
        loss = criterion(predictions, targets)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        n += 1

    return total_loss / max(n, 1)


@torch.no_grad()
def evaluate(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0
    all_preds, all_targets = [], []
    n = 0

    for batch in dataloader:
        bert_emb = batch["bert_embedding"].to(device)
        targets = batch["score"].to(device).unsqueeze(1)

        features = {k: batch[k].to(device) for k in
                     ["query_length", "item_name_length", "word_overlap",
                      "schema_type_idx", "difficulty"]}

        predictions = model(bert_emb, **features)
        loss = criterion(predictions, targets)

        total_loss += loss.item()
        n += 1
        all_preds.append(predictions.cpu())
        all_targets.append(targets.cpu())

    all_preds = torch.cat(all_preds)
    all_targets = torch.cat(all_targets)

    mae = (all_preds - all_targets).abs().mean().item()
    from scipy.stats import spearmanr
    rho, _ = spearmanr(all_preds.numpy().flatten(), all_targets.numpy().flatten())

    return {"loss": total_loss / max(n, 1), "mae": mae, "spearman_rho": rho}


@torch.no_grad()
def analyze_contributions(model, dataloader, device):
    """Analyze average absolute contribution of each feature subnet."""
    model.eval()
    totals = None
    count = 0

    for batch in dataloader:
        bert_emb = batch["bert_embedding"].to(device)
        features = {k: batch[k].to(device) for k in
                     ["query_length", "item_name_length", "word_overlap",
                      "schema_type_idx", "difficulty"]}

        _, contributions = model(bert_emb, **features, return_contributions=True)

        if totals is None:
            totals = {k: 0.0 for k in contributions}
        for k, v in contributions.items():
            totals[k] += v.abs().sum().item()
        count += bert_emb.size(0)

    print("\nFeature importance (avg absolute contribution):")
    for k, v in sorted(totals.items(), key=lambda x: -x[1]):
        print(f"  {k:25s}: {v / count:.4f}")


def main():
    parser = argparse.ArgumentParser(description="Train Neural GAM")
    parser.add_argument("--config", type=str,
                        default="config/training_config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    gam_cfg = cfg["gam"]
    data_cfg = cfg["data"]
    bert_cfg = cfg["modernbert"]

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"Device: {device}")

    project_root = Path(__file__).resolve().parents[1]
    prepared_dir = project_root / data_cfg["prepared_dir"]
    bert_dir = project_root / bert_cfg["output_dir"]

    # Load pre-extracted embeddings
    print("Loading BERT embeddings...")
    train_emb = torch.load(bert_dir / "train_embeddings.pt", weights_only=True)
    val_emb = torch.load(bert_dir / "val_embeddings.pt", weights_only=True)
    test_emb = torch.load(bert_dir / "test_embeddings.pt", weights_only=True)
    print(f"  Train: {train_emb.shape}, Val: {val_emb.shape}, Test: {test_emb.shape}")

    # Load examples for handcrafted features
    print("Loading feature data...")
    train_data = load_jsonl(prepared_dir / "train.jsonl")
    val_data = load_jsonl(prepared_dir / "val.jsonl")
    test_data = load_jsonl(prepared_dir / "test.jsonl")

    # Schema type mapping
    with open(prepared_dir / "schema_type_mapping.json") as f:
        schema_mapping = json.load(f)

    # Prepare features
    train_features = prepare_features(train_data, schema_mapping)
    val_features = prepare_features(val_data, schema_mapping)
    test_features = prepare_features(test_data, schema_mapping)

    # Normalize
    train_features, norm_stats = normalize_features(train_features)
    val_features, _ = normalize_features(val_features, norm_stats)
    test_features, _ = normalize_features(test_features, norm_stats)

    train_scores = torch.tensor([ex["score"] for ex in train_data], dtype=torch.float32)
    val_scores = torch.tensor([ex["score"] for ex in val_data], dtype=torch.float32)
    test_scores = torch.tensor([ex["score"] for ex in test_data], dtype=torch.float32)

    # Datasets
    train_dataset = GAMDataset(train_emb, train_features, train_scores)
    val_dataset = GAMDataset(val_emb, val_features, val_scores)
    test_dataset = GAMDataset(test_emb, test_features, test_scores)

    train_loader = DataLoader(train_dataset, batch_size=gam_cfg["batch_size"],
                              shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=gam_cfg["batch_size"],
                            shuffle=False, num_workers=2, pin_memory=True)
    test_loader = DataLoader(test_dataset, batch_size=gam_cfg["batch_size"],
                             shuffle=False, num_workers=2, pin_memory=True)

    # Model
    model = NeuralGAM(
        bert_dim=gam_cfg["bert_feature_dim"],
        num_schema_types=len(schema_mapping),
        subnet_hidden=gam_cfg["subnet_hidden_units"],
        subnet_activation=gam_cfg["subnet_activation"],
        subnet_dropout=gam_cfg["subnet_dropout"],
    ).to(device)

    print(f"GAM parameters: {sum(p.numel() for p in model.parameters()):,}")

    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=gam_cfg["learning_rate"],
        weight_decay=gam_cfg["weight_decay"],
    )

    # Training with early stopping
    output_dir = project_root / gam_cfg["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    best_val_loss = float("inf")
    patience_counter = 0
    patience = gam_cfg.get("patience", 10)

    print(f"\nTraining GAM for up to {gam_cfg['num_epochs']} epochs "
          f"(patience={patience})...\n")

    for epoch in range(1, gam_cfg["num_epochs"] + 1):
        t0 = time.time()
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device)
        val_metrics = evaluate(model, val_loader, criterion, device)
        elapsed = time.time() - t0

        print(f"Epoch {epoch:3d} ({elapsed:.1f}s) | "
              f"Train: {train_loss:.4f} | "
              f"Val: {val_metrics['loss']:.4f} | "
              f"MAE: {val_metrics['mae']:.4f} | "
              f"ρ: {val_metrics['spearman_rho']:.4f}", end="")

        if val_metrics["loss"] < best_val_loss:
            best_val_loss = val_metrics["loss"]
            patience_counter = 0
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "val_metrics": val_metrics,
                "norm_stats": norm_stats,
                "schema_mapping": schema_mapping,
                "config": gam_cfg,
            }, output_dir / "best_gam.pt")
            print(" ✓")
        else:
            patience_counter += 1
            print(f" (patience {patience_counter}/{patience})")
            if patience_counter >= patience:
                print("Early stopping.")
                break

    # Load best and evaluate on test
    best = torch.load(output_dir / "best_gam.pt", weights_only=False)
    model.load_state_dict(best["model_state_dict"])

    test_metrics = evaluate(model, test_loader, criterion, device)
    print(f"\nTest metrics:")
    print(f"  Loss: {test_metrics['loss']:.4f} | "
          f"MAE: {test_metrics['mae']:.4f} | "
          f"Spearman ρ: {test_metrics['spearman_rho']:.4f}")

    # Feature importance analysis
    analyze_contributions(model, test_loader, device)

    print("\nPhase 2 complete. Use inference/scorer.py for production scoring.")


if __name__ == "__main__":
    main()

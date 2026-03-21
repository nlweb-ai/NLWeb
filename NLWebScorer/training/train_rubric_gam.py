"""Train Rubric GAM on top of fine-tuned ModernBERT embeddings.

Usage:
    python -m training.train_rubric_gam --config config/training_config_rubric_gam.yaml
    python -m training.train_rubric_gam --config config/training_config_rubric_gam.yaml --mode gated
    python -m training.train_rubric_gam --config config/training_config_rubric_gam.yaml --mode interaction

Takes pre-extracted BERT [CLS] embeddings + 16 rubric features grouped by
category and trains an interpretable Rubric GAM. Each rubric group's
contribution can be independently analyzed.
"""

import argparse
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Sampler
from scipy.stats import spearmanr
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.rubric_gam import (
    RubricGAM, RubricGAMDataset, RUBRIC_GROUPS, GROUP_NAMES, ALL_RUBRIC_FEATURES)
from training.loss_utils import (
    pairwise_ranking_loss as _ranking_loss,
    pairwise_score_diff_loss as _score_diff_loss,
    lambda_weighted_score_diff_loss as _lambda_loss,
    satisficer_metrics as _satisficer_metrics,
)


class QueryGroupedBatchSampler(Sampler):
    """Batch sampler that groups examples from the same query together."""

    def __init__(self, query_ids, batch_size):
        self.query_groups = defaultdict(list)
        for idx, qid in enumerate(query_ids):
            self.query_groups[qid].append(idx)
        self.batch_size = batch_size

    def __iter__(self):
        group_keys = list(self.query_groups.keys())
        random.shuffle(group_keys)
        for qid in group_keys:
            indices = list(self.query_groups[qid])
            random.shuffle(indices)
            for i in range(0, len(indices), self.batch_size):
                yield indices[i:i + self.batch_size]

    def __len__(self):
        return sum(
            (len(g) + self.batch_size - 1) // self.batch_size
            for g in self.query_groups.values()
        )


def load_jsonl(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def prepare_rubric_features(examples: list[dict]) -> dict[str, torch.Tensor]:
    """Extract rubric features grouped by category from examples."""
    grouped = {}
    for group_name, feature_names in RUBRIC_GROUPS.items():
        vals = []
        for ex in examples:
            vals.append([float(ex.get(f, 0.0)) for f in feature_names])
        grouped[group_name] = torch.tensor(vals, dtype=torch.float32)
    return grouped


def normalize_rubric_features(features: dict[str, torch.Tensor],
                              stats: dict = None) -> tuple[dict, dict]:
    """Normalize rubric features to zero mean, unit variance per feature."""
    if stats is None:
        stats = {}
        for group_name, tensor in features.items():
            group_stats = []
            for col in range(tensor.shape[1]):
                vals = tensor[:, col]
                group_stats.append({
                    "mean": vals.mean().item(),
                    "std": vals.std().item() + 1e-8,
                })
            stats[group_name] = group_stats

    normalized = {}
    for group_name, tensor in features.items():
        normed = tensor.clone()
        for col, s in enumerate(stats[group_name]):
            normed[:, col] = (tensor[:, col] - s["mean"]) / s["std"]
        normalized[group_name] = normed

    return normalized, stats


def train_epoch(model, dataloader, optimizer, criterion, device,
                ranking_alpha=0.0, score_diff_alpha=0.0, lambda_alpha=0.0):
    model.train()
    total_loss = 0
    n = 0

    for batch in dataloader:
        bert_emb = batch["bert_embedding"].to(device)
        targets = batch["score"].to(device).unsqueeze(1)
        rubric = {name: batch[f"rubric_{name}"].to(device) for name in GROUP_NAMES}

        optimizer.zero_grad()
        predictions = model(bert_emb, rubric)
        loss = criterion(predictions, targets)

        if ranking_alpha > 0:
            loss = loss + ranking_alpha * _ranking_loss(predictions, targets)
        if score_diff_alpha > 0:
            loss = loss + score_diff_alpha * _score_diff_loss(predictions, targets)
        if lambda_alpha > 0:
            loss = loss + lambda_alpha * _lambda_loss(predictions, targets)

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
        rubric = {name: batch[f"rubric_{name}"].to(device) for name in GROUP_NAMES}

        predictions = model(bert_emb, rubric)
        loss = criterion(predictions, targets)

        total_loss += loss.item()
        n += 1
        all_preds.append(predictions.cpu())
        all_targets.append(targets.cpu())

    all_preds = torch.cat(all_preds)
    all_targets = torch.cat(all_targets)

    mae = (all_preds - all_targets).abs().mean().item()
    rho, _ = spearmanr(all_preds.numpy().flatten(), all_targets.numpy().flatten())

    return {"loss": total_loss / max(n, 1), "mae": mae, "spearman_rho": rho}


@torch.no_grad()
def analyze_contributions(model, dataloader, device):
    """Analyze average absolute contribution of each rubric group."""
    model.eval()
    totals = None
    count = 0

    for batch in dataloader:
        bert_emb = batch["bert_embedding"].to(device)
        rubric = {name: batch[f"rubric_{name}"].to(device) for name in GROUP_NAMES}

        _, contributions = model(bert_emb, rubric, return_contributions=True)

        if totals is None:
            totals = {k: 0.0 for k in contributions if k != "gate_weights"}
        for k in totals:
            totals[k] += contributions[k].abs().sum().item()
        count += bert_emb.size(0)

    print("\nRubric group importance (avg |contribution|):")
    for k, v in sorted(totals.items(), key=lambda x: -x[1]):
        print(f"  {k:20s}: {v / count:.4f}")

    if model.mode == "gated":
        # Show average gate weights
        gate_totals = torch.zeros(model.num_groups)
        count2 = 0
        for batch in dataloader:
            bert_emb = batch["bert_embedding"].to(device)
            rubric = {name: batch[f"rubric_{name}"].to(device) for name in GROUP_NAMES}
            _, contributions = model(bert_emb, rubric, return_contributions=True)
            gate_totals += contributions["gate_weights"].cpu().sum(dim=0)
            count2 += bert_emb.size(0)
        print("\nAverage gate weights (query-conditioned):")
        for i, name in enumerate(GROUP_NAMES):
            print(f"  {name:20s}: {gate_totals[i] / count2:.4f}")


def satisficer_metrics(preds, targets, examples, k=5):
    """Delegate to shared loss_utils.satisficer_metrics (includes pairwise accuracy).

    Also computes top_k_overlap and high_bad for full evaluation.
    """
    base = _satisficer_metrics(preds, targets, examples, k=k)

    # Add extra metrics for full evaluation
    query_groups = defaultdict(list)
    for p, t, ex in zip(preds, targets, examples):
        query_groups[ex["query"]].append((p, t))

    top_k_overlaps, high_bad_all = [], []
    for query, items in query_groups.items():
        if len(items) < k:
            continue
        targets_q = np.array([x[1] for x in items])
        if not any(t >= 0.6 for t in targets_q):
            continue
        preds_q = np.array([x[0] for x in items])
        pred_top_k = set(np.argsort(preds_q)[-k:])
        true_top_k = set(np.argsort(targets_q)[-k:])
        top_k_overlaps.append(len(pred_top_k & true_top_k) / k)
        high_bad_all.append(sum(1 for i in pred_top_k if targets_q[i] <= 0.1) / k)

    base["top_k_overlap"] = float(np.mean(top_k_overlaps)) if top_k_overlaps else 0
    base["high_bad"] = float(np.mean(high_bad_all)) if high_bad_all else 0
    return base


@torch.no_grad()
def compute_val_satisficer(model, dataloader, examples, device, k=5):
    """Compute satisficer metrics on a validation/test split."""
    model.eval()
    all_preds = []
    for batch in dataloader:
        bert_emb = batch["bert_embedding"].to(device)
        rubric = {name: batch[f"rubric_{name}"].to(device) for name in GROUP_NAMES}
        preds = model(bert_emb, rubric)
        all_preds.append(preds.cpu().squeeze(-1))
    preds_np = torch.cat(all_preds).numpy()
    targets_np = np.array([ex["score"] for ex in examples])
    return satisficer_metrics(preds_np, targets_np, examples, k=k)


def full_evaluation(model, split_name, dataloader, examples, criterion, device):
    """Run full evaluation: metrics + per-site breakdown + satisficer."""
    metrics = evaluate(model, dataloader, criterion, device)
    print(f"\n  {split_name.upper()} ({len(examples)} examples):")
    print(f"    Loss: {metrics['loss']:.4f} | "
          f"MAE: {metrics['mae']*100:.2f} | "
          f"Spearman ρ: {metrics['spearman_rho']:.4f}")

    # Get predictions for satisficer metrics
    model.eval()
    all_preds = []
    with torch.no_grad():
        for batch in dataloader:
            bert_emb = batch["bert_embedding"].to(device)
            rubric = {name: batch[f"rubric_{name}"].to(device) for name in GROUP_NAMES}
            preds = model(bert_emb, rubric)
            all_preds.append(preds.cpu().squeeze(-1))
    preds_np = torch.cat(all_preds).numpy()
    targets_np = np.array([ex["score"] for ex in examples])

    sat = satisficer_metrics(preds_np, targets_np, examples, k=5)
    if sat["n_queries"] > 0:
        print(f"    Satisficer (top-5, {sat['n_queries']} answerable queries):")
        print(f"      good_picks: {sat['good_picks']:.3f} | "
              f"bad_picks: {sat['bad_picks']:.3f} | "
              f"high_bad: {sat['high_bad']:.3f} | "
              f"satisficer_score: {sat['satisficer_score']:.3f}")
        print(f"      pairwise_accuracy: {sat['pairwise_accuracy']:.3f} "
              f"({sat['pairwise_total']} pairs)")

    # Per-site breakdown
    site_groups = defaultdict(lambda: ([], []))
    for p, t, ex in zip(preds_np, targets_np, examples):
        site_groups[ex.get("site", "unknown")][0].append(p)
        site_groups[ex.get("site", "unknown")][1].append(t)

    if len(site_groups) > 1:
        print(f"    Per-site:")
        for site in sorted(site_groups.keys()):
            p, t = site_groups[site]
            rho, _ = spearmanr(p, t)
            mae = float(np.mean(np.abs(np.array(p) - np.array(t)))) * 100
            print(f"      {site:25s}: ρ={rho:.4f} MAE={mae:.1f} (n={len(p)})")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Train Rubric GAM")
    parser.add_argument("--config", type=str,
                        default="config/training_config_rubric_gam.yaml")
    parser.add_argument("--mode", type=str, default=None,
                        choices=["additive", "gated", "interaction"],
                        help="GAM mode (overrides config)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    gam_cfg = cfg["rubric_gam"]
    data_cfg = cfg["data"]
    bert_cfg = cfg["modernbert"]

    mode = args.mode or gam_cfg.get("mode", "additive")
    gam_cfg["mode"] = mode

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"Device: {device}")
    print(f"Mode: {mode}")

    project_root = Path(__file__).resolve().parents[1]
    prepared_dir = project_root / data_cfg["prepared_dir"]
    bert_dir = project_root / bert_cfg["output_dir"]

    # Load pre-extracted BERT embeddings
    print("\nLoading BERT embeddings...")
    train_emb = torch.load(bert_dir / "train_embeddings.pt", weights_only=True)
    val_emb = torch.load(bert_dir / "val_embeddings.pt", weights_only=True)
    test_emb = torch.load(bert_dir / "test_embeddings.pt", weights_only=True)
    bert_dim = train_emb.shape[1]
    print(f"  Train: {train_emb.shape}, Val: {val_emb.shape}, Test: {test_emb.shape}")
    print(f"  BERT dim: {bert_dim}")

    holdout_emb = None
    if (bert_dir / "holdout_embeddings.pt").exists():
        holdout_emb = torch.load(bert_dir / "holdout_embeddings.pt", weights_only=True)
        print(f"  Holdout: {holdout_emb.shape}")

    # Load examples for rubric features
    print("Loading feature data...")
    train_data = load_jsonl(prepared_dir / "train.jsonl")
    val_data = load_jsonl(prepared_dir / "val.jsonl")
    test_data = load_jsonl(prepared_dir / "test.jsonl")

    holdout_data = None
    holdout_path = prepared_dir / "holdout_eval.jsonl"
    if holdout_path.exists() and holdout_emb is not None:
        holdout_data = load_jsonl(holdout_path)

    # Prepare rubric features
    print("Preparing rubric features...")
    train_rubric = prepare_rubric_features(train_data)
    val_rubric = prepare_rubric_features(val_data)
    test_rubric = prepare_rubric_features(test_data)

    # Normalize
    train_rubric, norm_stats = normalize_rubric_features(train_rubric)
    val_rubric, _ = normalize_rubric_features(val_rubric, norm_stats)
    test_rubric, _ = normalize_rubric_features(test_rubric, norm_stats)

    holdout_rubric = None
    if holdout_data is not None:
        holdout_rubric = prepare_rubric_features(holdout_data)
        holdout_rubric, _ = normalize_rubric_features(holdout_rubric, norm_stats)

    # Print feature stats
    print("  Feature groups:")
    for group_name, features in RUBRIC_GROUPS.items():
        print(f"    {group_name}: {len(features)} features → "
              f"tensor shape {train_rubric[group_name].shape}")

    train_scores = torch.tensor([ex["score"] for ex in train_data], dtype=torch.float32)
    val_scores = torch.tensor([ex["score"] for ex in val_data], dtype=torch.float32)
    test_scores = torch.tensor([ex["score"] for ex in test_data], dtype=torch.float32)

    # Assign query IDs for ranking loss
    all_queries = sorted(set(ex["query"] for ex in train_data))
    query_to_id = {q: i for i, q in enumerate(all_queries)}
    train_query_ids = torch.tensor([query_to_id[ex["query"]] for ex in train_data], dtype=torch.long)

    # Datasets
    train_dataset = RubricGAMDataset(train_emb, train_rubric, train_scores, train_query_ids)
    val_dataset = RubricGAMDataset(val_emb, val_rubric, val_scores)
    test_dataset = RubricGAMDataset(test_emb, test_rubric, test_scores)

    batch_size = gam_cfg.get("batch_size", 256)
    ranking_alpha = gam_cfg.get("ranking_alpha", 0.0)
    score_diff_alpha = gam_cfg.get("score_diff_alpha", 0.0)
    lambda_alpha = gam_cfg.get("lambda_alpha", 0.0)

    if ranking_alpha > 0 or score_diff_alpha > 0 or lambda_alpha > 0:
        # Use query-grouped batching for pairwise ranking loss
        grouped_sampler = QueryGroupedBatchSampler(
            train_query_ids.tolist(), batch_size=batch_size)
        train_loader = DataLoader(train_dataset, batch_sampler=grouped_sampler,
                                  num_workers=2, pin_memory=True)
        loss_parts = []
        if ranking_alpha > 0:
            loss_parts.append(f"rank={ranking_alpha}")
        if score_diff_alpha > 0:
            loss_parts.append(f"diff={score_diff_alpha}")
        if lambda_alpha > 0:
            loss_parts.append(f"lambda={lambda_alpha}")
        print(f"  Using query-grouped batching ({', '.join(loss_parts)})")
    else:
        train_loader = DataLoader(train_dataset, batch_size=batch_size,
                                  shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size,
                            shuffle=False, num_workers=2, pin_memory=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size,
                             shuffle=False, num_workers=2, pin_memory=True)

    holdout_loader = None
    if holdout_data is not None and holdout_emb is not None:
        holdout_scores = torch.tensor(
            [ex["score"] for ex in holdout_data], dtype=torch.float32)
        holdout_dataset = RubricGAMDataset(holdout_emb, holdout_rubric, holdout_scores)
        holdout_loader = DataLoader(holdout_dataset, batch_size=batch_size,
                                    shuffle=False, num_workers=2, pin_memory=True)

    # Model
    model = RubricGAM(
        bert_dim=bert_dim,
        bert_proj_dim=gam_cfg.get("bert_proj_dim", 64),
        bert_hidden=gam_cfg.get("bert_hidden", [128, 64, 32]),
        rubric_hidden=gam_cfg.get("rubric_hidden", [64, 32]),
        activation=gam_cfg.get("activation", "relu"),
        dropout=gam_cfg.get("dropout", 0.1),
        mode=mode,
        interaction_hidden=gam_cfg.get("interaction_hidden", [16]),
    ).to(device)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nRubricGAM ({mode}) parameters: {n_params:,}")

    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=gam_cfg.get("learning_rate", 1e-3),
        weight_decay=gam_cfg.get("weight_decay", 1e-4),
    )

    # Learning rate scheduler
    scheduler = None
    lr_sched = gam_cfg.get("lr_scheduler", None)
    if lr_sched == "cosine":
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=gam_cfg.get("num_epochs", 200), eta_min=1e-6)
        print(f"Using cosine annealing LR scheduler")
    elif lr_sched == "plateau":
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=5, min_lr=1e-6)
        print(f"Using ReduceLROnPlateau LR scheduler")

    # Output directory
    output_dir = project_root / gam_cfg["output_dir"] / mode
    output_dir.mkdir(parents=True, exist_ok=True)

    best_selection = float("-inf")
    patience_counter = 0
    patience = gam_cfg.get("patience", 10)
    num_epochs = gam_cfg.get("num_epochs", 50)
    mae_lambda = gam_cfg.get("mae_lambda", 1.0)

    print(f"\nTraining Rubric GAM ({mode}) for up to {num_epochs} epochs "
          f"(patience={patience})...")
    print(f"  Model selection: satisficer_score - {mae_lambda} * MAE (top-5)\n")

    for epoch in range(1, num_epochs + 1):
        t0 = time.time()
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device,
                                 ranking_alpha=ranking_alpha,
                                 score_diff_alpha=score_diff_alpha,
                                 lambda_alpha=lambda_alpha)
        val_metrics = evaluate(model, val_loader, criterion, device)

        # Compute satisficer metrics on val set for model selection
        val_sat = compute_val_satisficer(model, val_loader, val_data, device, k=5)
        sat_score = val_sat["satisficer_score"]
        val_mae = val_metrics["mae"]
        selection_score = sat_score - mae_lambda * val_mae
        elapsed = time.time() - t0

        print(f"Epoch {epoch:3d} ({elapsed:.1f}s) | "
              f"Train: {train_loss:.4f} | "
              f"Val MSE: {val_metrics['loss']:.4f} | "
              f"MAE: {val_mae:.4f} | "
              f"good: {val_sat['good_picks']:.3f} | "
              f"bad: {val_sat['bad_picks']:.3f} | "
              f"pair: {val_sat['pairwise_accuracy']:.3f} | "
              f"sel: {selection_score:.3f}", end="")

        # Step scheduler (use MSE for ReduceLROnPlateau, epoch for cosine)
        if scheduler is not None:
            if isinstance(scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                scheduler.step(val_metrics["loss"])
            else:
                scheduler.step()

        # Select best model by combined score (higher = better)
        if selection_score > best_selection:
            best_selection = selection_score
            patience_counter = 0
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "val_metrics": val_metrics,
                "val_satisficer": val_sat,
                "selection_score": selection_score,
                "norm_stats": norm_stats,
                "config": gam_cfg,
                "mode": mode,
                "bert_dim": bert_dim,
            }, output_dir / "best_rubric_gam.pt")
            print(" ✓")
        else:
            patience_counter += 1
            print(f" (patience {patience_counter}/{patience})")
            if patience_counter >= patience:
                print("Early stopping.")
                break

    # Load best and evaluate
    best = torch.load(output_dir / "best_rubric_gam.pt", weights_only=False)
    model.load_state_dict(best["model_state_dict"])

    print(f"\n{'='*60}")
    print(f"EVALUATION — Rubric GAM ({mode})")
    print(f"{'='*60}")

    full_evaluation(model, "test", test_loader, test_data, criterion, device)

    if holdout_loader is not None:
        full_evaluation(model, "holdout", holdout_loader, holdout_data, criterion, device)

    # Feature importance
    analyze_contributions(model, test_loader, device)

    print(f"\nBest model saved to {output_dir / 'best_rubric_gam.pt'}")
    print("Done.")


if __name__ == "__main__":
    main()

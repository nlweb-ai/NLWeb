"""Evaluate NLWebScorer: ModernBERT-only vs full pipeline (BERT + GAM).

Usage:
    python -m training.evaluate [--config config/training_config.yaml]

Reports:
  - MSE, MAE, Spearman ρ for both models
  - Score distribution analysis
  - Per-difficulty and per-site breakdowns
  - GAM feature importance
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import torch
from torch.utils.data import DataLoader
from scipy.stats import spearmanr
from transformers import AutoTokenizer
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.modernbert_scorer import ModernBERTScorer, ScorerDataset
from models.rubric_gam import RubricGAM, RubricGAMDataset, GROUP_NAMES
from training.train_rubric_gam import prepare_rubric_features, normalize_rubric_features


def load_jsonl(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


@torch.no_grad()
def eval_bert(model, dataloader, device):
    model.eval()
    all_preds, all_targets = [], []
    for batch in dataloader:
        preds = model(batch["input_ids"].to(device),
                      batch["attention_mask"].to(device))
        all_preds.append(preds.cpu().squeeze(-1))
        all_targets.append(batch["score"])
    return torch.cat(all_preds), torch.cat(all_targets)


@torch.no_grad()
def eval_gam(model, dataloader, device):
    model.eval()
    all_preds, all_targets = [], []
    for batch in dataloader:
        bert_emb = batch["bert_embedding"].to(device)
        rubric = {name: batch[f"rubric_{name}"].to(device) for name in GROUP_NAMES}
        preds = model(bert_emb, rubric)
        all_preds.append(preds.cpu().squeeze(-1))
        all_targets.append(batch["score"])
    return torch.cat(all_preds), torch.cat(all_targets)


def compute_metrics(preds, targets, label=""):
    preds_np = preds.numpy()
    targets_np = targets.numpy()
    mse = ((preds - targets) ** 2).mean().item()
    mae = (preds - targets).abs().mean().item()
    rho, _ = spearmanr(preds_np, targets_np)

    # Rescale to 0-100 for interpretability
    mae_100 = mae * 100
    rmse_100 = (mse ** 0.5) * 100

    print(f"  {label}")
    print(f"    MSE: {mse:.6f}  |  RMSE (0-100): {rmse_100:.2f}")
    print(f"    MAE: {mae:.6f}  |  MAE  (0-100): {mae_100:.2f}")
    print(f"    Spearman ρ: {rho:.4f}")
    return {"mse": mse, "mae": mae, "spearman_rho": rho}


def per_group_analysis(preds, targets, examples, group_key):
    """Compute metrics per group (site, difficulty, etc.)."""
    groups = defaultdict(lambda: ([], []))
    for pred, target, ex in zip(preds, targets, examples):
        key = ex.get(group_key, "unknown")
        groups[key][0].append(pred.item())
        groups[key][1].append(target.item())

    print(f"\n  Per-{group_key}:")
    for key in sorted(groups.keys()):
        p, t = groups[key]
        p_t = torch.tensor(p)
        t_t = torch.tensor(t)
        mae = (p_t - t_t).abs().mean().item() * 100
        rho, _ = spearmanr(p, t)
        print(f"    {str(key):25s}: MAE={mae:5.1f}  ρ={rho:.3f}  (n={len(p)})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/training_config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    project_root = Path(__file__).resolve().parents[1]
    prepared_dir = project_root / cfg["data"]["prepared_dir"]
    bert_dir = project_root / cfg["modernbert"]["output_dir"]
    gam_cfg = cfg["rubric_gam"]
    gam_dir = project_root / gam_cfg["output_dir"]

    # Load test data
    test_data = load_jsonl(prepared_dir / "test.jsonl")
    print(f"Test set: {len(test_data)} examples\n")

    # ── Evaluate BERT-only ──
    print("=" * 50)
    print("ModernBERT-only (regression head)")
    print("=" * 50)

    bert_state = torch.load(bert_dir / "best_model.pt", map_location=device,
                            weights_only=False)
    bert_cfg = bert_state["config"]
    tokenizer = AutoTokenizer.from_pretrained(bert_cfg["model_name"])

    bert_model = ModernBERTScorer(model_name=bert_cfg["model_name"]).to(device)
    bert_model.load_state_dict(bert_state["model_state_dict"])

    test_dataset = ScorerDataset(test_data, tokenizer,
                                 max_length=cfg["data"].get("max_seq_length", 512))
    test_loader = DataLoader(test_dataset, batch_size=64, num_workers=2)

    bert_preds, targets = eval_bert(bert_model, test_loader, device)
    bert_metrics = compute_metrics(bert_preds, targets, "BERT-only")
    per_group_analysis(bert_preds, targets, test_data, "difficulty")
    per_group_analysis(bert_preds, targets, test_data, "site")

    # ── Evaluate BERT + GAM ──
    print("\n" + "=" * 50)
    print("ModernBERT + Neural GAM")
    print("=" * 50)

    gam_state = torch.load(gam_dir / "best_rubric_gam.pt", map_location=device,
                           weights_only=False)
    norm_stats = gam_state["norm_stats"]
    bert_dim = gam_state.get("bert_dim", 1024)

    gam_model = RubricGAM(
        bert_dim=bert_dim,
        bert_proj_dim=gam_cfg.get("bert_proj_dim", 64),
        bert_hidden=gam_cfg.get("bert_hidden", [128, 64, 32]),
        rubric_hidden=gam_cfg.get("rubric_hidden", [64, 32]),
        activation=gam_cfg.get("activation", "relu"),
        dropout=gam_cfg.get("dropout", 0.1),
        mode=gam_cfg.get("mode", "additive"),
        interaction_hidden=gam_cfg.get("interaction_hidden", [16]),
    ).to(device)
    gam_model.load_state_dict(gam_state["model_state_dict"])

    test_emb = torch.load(bert_dir / "test_embeddings.pt", weights_only=True)
    test_rubric = prepare_rubric_features(test_data)
    test_rubric, _ = normalize_rubric_features(test_rubric, norm_stats)
    test_scores = torch.tensor([ex["score"] for ex in test_data], dtype=torch.float32)

    gam_dataset = RubricGAMDataset(test_emb, test_rubric, test_scores)
    gam_loader = DataLoader(gam_dataset, batch_size=256, num_workers=2)

    gam_preds, targets = eval_gam(gam_model, gam_loader, device)
    gam_metrics = compute_metrics(gam_preds, targets, "BERT + GAM")
    per_group_analysis(gam_preds, targets, test_data, "difficulty")
    per_group_analysis(gam_preds, targets, test_data, "site")

    # ── Comparison ──
    print("\n" + "=" * 50)
    print("Comparison")
    print("=" * 50)
    for metric in ["mse", "mae", "spearman_rho"]:
        b = bert_metrics[metric]
        g = gam_metrics[metric]
        direction = "↑" if metric == "spearman_rho" else "↓"
        better = "GAM" if (g > b if metric == "spearman_rho" else g < b) else "BERT"
        print(f"  {metric:15s}: BERT={b:.4f}  GAM={g:.4f}  ({direction} {better})")


if __name__ == "__main__":
    main()

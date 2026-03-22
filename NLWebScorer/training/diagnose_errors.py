"""Diagnose where the current model's errors concentrate by score bucket.

Runs the full BERT+GAM pipeline on test data and shows:
  - Error (MAE, bias) per GPT-4.1 score bucket
  - Over/under-prediction patterns
  - Where better training data would help most

Usage:
    cd NLWebScorer
    python -m training.diagnose_errors --config config/training_config_rubric_gam.yaml
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import torch
from scipy.stats import spearmanr
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.rubric_gam import RubricGAM, RubricGAMDataset, RUBRIC_GROUPS, GROUP_NAMES


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def prepare_rubric_features(examples):
    grouped = {}
    for group_name, feature_names in RUBRIC_GROUPS.items():
        vals = [[float(ex.get(f, 0.0)) for f in feature_names] for ex in examples]
        grouped[group_name] = torch.tensor(vals, dtype=torch.float32)
    return grouped


def normalize_features(grouped, norm_stats):
    for group_name, tensor in grouped.items():
        stats = norm_stats.get(group_name, [])
        for col in range(tensor.shape[1]):
            if col < len(stats):
                tensor[:, col] = (tensor[:, col] - stats[col]["mean"]) / stats[col]["std"]
    return grouped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/training_config_rubric_gam.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    device = torch.device("mps" if torch.backends.mps.is_available()
                          else "cuda" if torch.cuda.is_available() else "cpu")

    root = Path(__file__).resolve().parents[1]
    prepared_dir = root / cfg["data"]["prepared_dir"]
    bert_dir = root / cfg["modernbert"]["output_dir"]
    gam_cfg = cfg["rubric_gam"]
    gam_dir = root / gam_cfg["output_dir"] / "additive"

    # Load test data + precomputed embeddings
    test_data = load_jsonl(prepared_dir / "test.jsonl")
    test_emb = torch.load(bert_dir / "test_embeddings.pt", weights_only=True)
    print(f"Test set: {len(test_data)} examples, embeddings: {test_emb.shape}")

    # Load GAM
    gam_state = torch.load(gam_dir / "best_rubric_gam.pt", map_location=device,
                           weights_only=False)
    norm_stats = gam_state["norm_stats"]

    gam = RubricGAM(
        bert_dim=gam_state.get("bert_dim", 1024),
        bert_proj_dim=gam_cfg.get("bert_proj_dim", 64),
        bert_hidden=gam_cfg.get("bert_hidden", [128, 64, 32]),
        rubric_hidden=gam_cfg.get("rubric_hidden", [64, 32]),
        activation=gam_cfg.get("activation", "relu"),
        dropout=gam_cfg.get("dropout", 0.1),
        mode=gam_state.get("mode", "additive"),
        interaction_hidden=gam_cfg.get("interaction_hidden", [16]),
    ).to(device)
    gam.load_state_dict(gam_state["model_state_dict"])
    gam.eval()

    # Prepare features
    rubric = prepare_rubric_features(test_data)
    rubric = normalize_features(rubric, norm_stats)
    targets = torch.tensor([ex["score"] for ex in test_data], dtype=torch.float32)

    # Run inference in batches
    preds_list = []
    bs = 512
    with torch.no_grad():
        for i in range(0, len(test_data), bs):
            emb_batch = test_emb[i:i+bs].to(device)
            rubric_batch = {k: v[i:i+bs].to(device) for k, v in rubric.items()}
            out = gam(emb_batch, rubric_batch)
            preds_list.append(out.squeeze(-1).cpu())
    preds = torch.cat(preds_list)

    # Convert to 0-100 scale
    preds_100 = (preds * 100).clamp(0, 100)
    targets_100 = targets * 100

    # ── Overall metrics ──
    errors = preds_100 - targets_100
    print(f"\n{'='*70}")
    print(f"OVERALL  (n={len(test_data)})")
    print(f"{'='*70}")
    print(f"  MAE:  {errors.abs().mean():.1f}")
    print(f"  RMSE: {(errors**2).mean().sqrt():.1f}")
    print(f"  Bias: {errors.mean():+.1f}  (positive = model over-predicts)")
    rho, _ = spearmanr(preds_100.numpy(), targets_100.numpy())
    print(f"  Spearman ρ: {rho:.4f}")

    # ── By score bucket ──
    buckets = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 101)]
    bucket_labels = ["0-19", "20-39", "40-59", "60-79", "80-100"]

    print(f"\n{'='*70}")
    print(f"ERROR BY GPT-4.1 SCORE BUCKET")
    print(f"{'='*70}")
    print(f"{'Bucket':>8} {'Count':>7} {'%Data':>6} {'MAE':>6} {'Bias':>7} {'Avg Pred':>9} {'Avg True':>9} {'ρ':>7}")
    print(f"{'-'*70}")

    for (lo, hi), label in zip(buckets, bucket_labels):
        mask = (targets_100 >= lo) & (targets_100 < hi)
        n = mask.sum().item()
        if n == 0:
            print(f"{label:>8} {0:>7} {0:>5.1f}%   (no examples)")
            continue
        bucket_errors = errors[mask]
        bucket_preds = preds_100[mask]
        bucket_targets = targets_100[mask]
        mae = bucket_errors.abs().mean().item()
        bias = bucket_errors.mean().item()
        avg_pred = bucket_preds.mean().item()
        avg_true = bucket_targets.mean().item()
        if n > 2:
            rho_b, _ = spearmanr(bucket_preds.numpy(), bucket_targets.numpy())
        else:
            rho_b = float('nan')
        pct = n / len(test_data) * 100
        print(f"{label:>8} {n:>7} {pct:>5.1f}% {mae:>6.1f} {bias:>+7.1f} {avg_pred:>9.1f} {avg_true:>9.1f} {rho_b:>7.3f}")

    # ── Confusion: where does the model put items? ──
    print(f"\n{'='*70}")
    print(f"CONFUSION: True bucket → Predicted bucket distribution")
    print(f"{'='*70}")
    print(f"{'True \\ Pred':>12}", end="")
    for label in bucket_labels:
        print(f" {label:>8}", end="")
    print()
    print(f"{'-'*60}")

    for (lo, hi), label in zip(buckets, bucket_labels):
        mask = (targets_100 >= lo) & (targets_100 < hi)
        n = mask.sum().item()
        if n == 0:
            continue
        print(f"{label:>12}", end="")
        bucket_preds = preds_100[mask]
        for (plo, phi), _ in zip(buckets, bucket_labels):
            count = ((bucket_preds >= plo) & (bucket_preds < phi)).sum().item()
            pct = count / n * 100
            print(f" {pct:>7.1f}%", end="")
        print(f"  (n={n})")

    # ── Worst cases: biggest over-predictions (model says high, truth is low) ──
    print(f"\n{'='*70}")
    print(f"TOP 20 OVER-PREDICTIONS (model says relevant, GPT says irrelevant)")
    print(f"{'='*70}")
    sorted_idx = errors.argsort(descending=True)
    print(f"{'Pred':>5} {'True':>5} {'Err':>6}  {'Site':>15}  Query → Item")
    for i in sorted_idx[:20]:
        ex = test_data[i]
        query = ex["query"][:30]
        # Extract item name from item_text (after [SEP])
        item_text = ex.get("item_text", "")
        sep_idx = item_text.find("[SEP]")
        item_name = item_text[sep_idx+6:sep_idx+50].strip() if sep_idx >= 0 else ""
        print(f"{preds_100[i]:>5.0f} {targets_100[i]:>5.0f} {errors[i]:>+6.0f}  {ex.get('site',''):>15}  {query} → {item_name}")

    # ── Training data score distribution (for context) ──
    print(f"\n{'='*70}")
    print(f"TRAINING DATA SCORE DISTRIBUTION")
    print(f"{'='*70}")
    train_data = load_jsonl(prepared_dir / "train.jsonl")
    train_scores = [ex["score"] * 100 for ex in train_data]
    print(f"{'Bucket':>8} {'Count':>7} {'%':>6}")
    for (lo, hi), label in zip(buckets, bucket_labels):
        n = sum(1 for s in train_scores if lo <= s < hi)
        print(f"{label:>8} {n:>7} {n/len(train_scores)*100:>5.1f}%")
    print(f"{'Total':>8} {len(train_scores):>7}")


if __name__ == "__main__":
    main()

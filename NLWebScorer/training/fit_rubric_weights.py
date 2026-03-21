"""Fit linear rubric weights on BERT scores + rubric features.

Usage:
    python -m training.fit_rubric_weights [--config config/training_config_large.yaml]

After BERT is trained, this script:
  1. Loads the best BERT checkpoint
  2. Gets BERT predicted scores on train/val/test/holdout data
  3. Fits:  final = w_bert * bert_score + Σ wᵢ * rubric_scoreᵢ
  4. Reports learned weights and evaluation metrics
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from torch.utils.data import DataLoader
from transformers import AutoTokenizer
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.modernbert_scorer import ModernBERTScorer, ScorerDataset, SCALAR_FEATURES


def load_jsonl(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


@torch.no_grad()
def get_bert_scores(model, dataloader, device) -> np.ndarray:
    """Run BERT inference and return predicted scores as numpy array."""
    model.eval()
    all_preds = []
    for batch in dataloader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        schema_type_idx = batch["schema_type_idx"].to(device)
        rubric_features = batch["rubric_features"].to(device)
        preds = model(input_ids, attention_mask,
                      schema_type_idx=schema_type_idx,
                      rubric_features=rubric_features)
        all_preds.append(preds.cpu().squeeze(-1))
    return torch.cat(all_preds).numpy()


def build_feature_matrix(bert_scores: np.ndarray, examples: list[dict]) -> np.ndarray:
    """Build [bert_score, rubric_feat_1, ..., rubric_feat_16] matrix."""
    rubric = np.array([[ex.get(k, 0.0) for k in SCALAR_FEATURES] for ex in examples])
    return np.column_stack([bert_scores, rubric])


def get_targets(examples: list[dict]) -> np.ndarray:
    return np.array([ex["score"] for ex in examples])


def compute_metrics(preds: np.ndarray, targets: np.ndarray) -> dict:
    mse = float(np.mean((preds - targets) ** 2))
    mae = float(np.mean(np.abs(preds - targets)))
    rho, _ = spearmanr(preds, targets)
    return {"mse": mse, "mae": mae, "spearman_rho": float(rho)}


def per_group_metrics(preds, targets, examples, group_key):
    """Compute Spearman ρ per group."""
    groups = defaultdict(lambda: ([], []))
    for p, t, ex in zip(preds, targets, examples):
        key = ex.get(group_key, "unknown")
        groups[key][0].append(p)
        groups[key][1].append(t)

    results = {}
    for key in sorted(groups.keys()):
        p, t = groups[key]
        rho, _ = spearmanr(p, t)
        mae = float(np.mean(np.abs(np.array(p) - np.array(t)))) * 100
        results[key] = {"rho": rho, "mae": mae, "n": len(p)}
    return results


def satisficer_metrics(preds, targets, examples, k=10):
    """Compute satisficer-style metrics: top-k overlap, good/bad picks."""
    # Group by query
    query_groups = defaultdict(list)
    for p, t, ex in zip(preds, targets, examples):
        query_groups[ex["query"]].append((p, t))

    top_k_overlaps = []
    good_picks_all = []
    bad_picks_all = []
    high_bad_all = []

    for query, items in query_groups.items():
        if len(items) < k:
            continue
        preds_q = np.array([x[0] for x in items])
        targets_q = np.array([x[1] for x in items])

        pred_top_k = set(np.argsort(preds_q)[-k:])
        true_top_k = set(np.argsort(targets_q)[-k:])
        overlap = len(pred_top_k & true_top_k) / k
        top_k_overlaps.append(overlap)

        # Good picks: items in our top-k that are truly good (target >= 0.6)
        good = sum(1 for i in pred_top_k if targets_q[i] >= 0.6) / k
        good_picks_all.append(good)

        # Bad picks: items in our top-k that are truly bad (target <= 0.3)
        bad = sum(1 for i in pred_top_k if targets_q[i] <= 0.3) / k
        bad_picks_all.append(bad)

        # High-bad: items in our top-k that are truly very bad (target <= 0.1)
        high_bad = sum(1 for i in pred_top_k if targets_q[i] <= 0.1) / k
        high_bad_all.append(high_bad)

    return {
        "top_k_overlap": float(np.mean(top_k_overlaps)) if top_k_overlaps else 0,
        "good_picks": float(np.mean(good_picks_all)) if good_picks_all else 0,
        "bad_picks": float(np.mean(bad_picks_all)) if bad_picks_all else 0,
        "high_bad": float(np.mean(high_bad_all)) if high_bad_all else 0,
        "n_queries": len(top_k_overlaps),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fit linear rubric weights on BERT + rubric features")
    parser.add_argument("--config", type=str,
                        default="config/training_config_large.yaml")
    parser.add_argument("--alpha", type=float, default=1.0,
                        help="Ridge regularization strength")
    args = parser.parse_args()

    cfg = load_config(args.config)
    bert_cfg = cfg["modernbert"]
    data_cfg = cfg["data"]

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"Device: {device}", flush=True)

    project_root = Path(__file__).resolve().parents[1]
    prepared_dir = project_root / data_cfg["prepared_dir"]
    bert_dir = project_root / bert_cfg["output_dir"]

    # Load BERT checkpoint
    print(f"\nLoading BERT checkpoint from {bert_dir}...", flush=True)
    checkpoint = torch.load(bert_dir / "best_model.pt", map_location=device,
                            weights_only=False)
    schema_mapping = checkpoint["schema_mapping"]
    print(f"  Best epoch: {checkpoint['epoch']}", flush=True)
    print(f"  Val metrics: {checkpoint['val_metrics']}", flush=True)

    tokenizer = AutoTokenizer.from_pretrained(bert_cfg["model_name"])
    model = ModernBERTScorer(
        model_name=bert_cfg["model_name"],
        num_schema_types=len(schema_mapping),
    ).to(device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    max_len = data_cfg.get("max_seq_length", 512)
    use_cuda = device.type == "cuda"
    num_workers = 4 if use_cuda else 0
    batch_size = bert_cfg["per_device_eval_batch_size"]

    # Load all datasets
    datasets = {}
    for split in ["train", "val", "test"]:
        path = prepared_dir / f"{split}.jsonl"
        if path.exists():
            datasets[split] = load_jsonl(path)
            print(f"  {split}: {len(datasets[split])} examples", flush=True)

    holdout_path = prepared_dir / "holdout_eval.jsonl"
    if holdout_path.exists():
        datasets["holdout"] = load_jsonl(holdout_path)
        print(f"  holdout: {len(datasets['holdout'])} examples", flush=True)

    # Get BERT predictions for all splits
    print("\nRunning BERT inference...", flush=True)
    bert_scores = {}
    for split, data in datasets.items():
        ds = ScorerDataset(data, tokenizer, max_length=max_len,
                           schema_mapping=schema_mapping)
        loader = DataLoader(ds, batch_size=batch_size, shuffle=False,
                            num_workers=num_workers, pin_memory=use_cuda)
        bert_scores[split] = get_bert_scores(model, loader, device)
        print(f"  {split}: {len(bert_scores[split])} predictions", flush=True)

    # Build feature matrices
    print("\nBuilding feature matrices...", flush=True)
    feature_names = ["bert_score"] + list(SCALAR_FEATURES)
    X = {}
    y = {}
    for split, data in datasets.items():
        X[split] = build_feature_matrix(bert_scores[split], data)
        y[split] = get_targets(data)
        print(f"  {split}: X={X[split].shape}, y={y[split].shape}", flush=True)

    # Fit Ridge regression
    print(f"\nFitting Ridge regression (alpha={args.alpha})...", flush=True)
    ridge = Ridge(alpha=args.alpha, fit_intercept=True)
    ridge.fit(X["train"], y["train"])

    # Report learned weights
    print("\n" + "=" * 60, flush=True)
    print("LEARNED RUBRIC WEIGHTS", flush=True)
    print("=" * 60, flush=True)
    print(f"  {'Feature':<30s} {'Weight':>10s}", flush=True)
    print(f"  {'-'*30} {'-'*10}", flush=True)
    for name, w in sorted(zip(feature_names, ridge.coef_),
                           key=lambda x: abs(x[1]), reverse=True):
        print(f"  {name:<30s} {w:>10.4f}", flush=True)
    print(f"  {'intercept':<30s} {ridge.intercept_:>10.4f}", flush=True)

    # Evaluate all splits
    print("\n" + "=" * 60, flush=True)
    print("EVALUATION RESULTS", flush=True)
    print("=" * 60, flush=True)

    for split in ["train", "val", "test", "holdout"]:
        if split not in X:
            continue

        # BERT-only predictions
        bert_preds = bert_scores[split]
        bert_m = compute_metrics(bert_preds, y[split])

        # Linear combo predictions
        linear_preds = ridge.predict(X[split])
        linear_preds = np.clip(linear_preds, 0, 1)
        linear_m = compute_metrics(linear_preds, y[split])

        print(f"\n  {split.upper()} ({len(y[split])} examples):", flush=True)
        print(f"    {'Model':<25s} {'Spearman ρ':>12s} {'MAE (0-100)':>12s} "
              f"{'MSE':>10s}", flush=True)
        print(f"    {'-'*25} {'-'*12} {'-'*12} {'-'*10}", flush=True)
        print(f"    {'BERT-only':<25s} {bert_m['spearman_rho']:>12.4f} "
              f"{bert_m['mae']*100:>12.2f} {bert_m['mse']:>10.6f}", flush=True)
        print(f"    {'BERT + Linear Rubric':<25s} {linear_m['spearman_rho']:>12.4f} "
              f"{linear_m['mae']*100:>12.2f} {linear_m['mse']:>10.6f}", flush=True)

        delta_rho = linear_m['spearman_rho'] - bert_m['spearman_rho']
        print(f"    Δρ = {delta_rho:+.4f}", flush=True)

        # Satisficer metrics
        if split in ["test", "holdout"]:
            bert_sat = satisficer_metrics(bert_preds, y[split], datasets[split])
            linear_sat = satisficer_metrics(linear_preds, y[split], datasets[split])
            print(f"\n    Satisficer Metrics (top-10, {bert_sat['n_queries']} queries):",
                  flush=True)
            print(f"    {'Metric':<20s} {'BERT':>10s} {'Linear':>10s} {'Δ':>10s}",
                  flush=True)
            print(f"    {'-'*20} {'-'*10} {'-'*10} {'-'*10}", flush=True)
            for metric in ["top_k_overlap", "good_picks", "bad_picks", "high_bad"]:
                b, l = bert_sat[metric], linear_sat[metric]
                d = l - b
                better = "↑" if metric in ["top_k_overlap", "good_picks"] else "↓"
                print(f"    {metric:<20s} {b:>10.3f} {l:>10.3f} {d:>+10.3f} {better}",
                      flush=True)

    # Per-site breakdown for holdout
    if "holdout" in datasets:
        print("\n" + "=" * 60, flush=True)
        print("PER-SITE HOLDOUT BREAKDOWN", flush=True)
        print("=" * 60, flush=True)

        linear_holdout = ridge.predict(X["holdout"])
        linear_holdout = np.clip(linear_holdout, 0, 1)

        bert_by_site = per_group_metrics(bert_scores["holdout"], y["holdout"],
                                         datasets["holdout"], "site")
        linear_by_site = per_group_metrics(linear_holdout, y["holdout"],
                                           datasets["holdout"], "site")

        print(f"  {'Site':<25s} {'BERT ρ':>10s} {'Linear ρ':>10s} {'Δρ':>10s} "
              f"{'n':>8s}", flush=True)
        print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*8}", flush=True)
        for site in sorted(bert_by_site.keys()):
            br = bert_by_site[site]["rho"]
            lr = linear_by_site[site]["rho"]
            n = bert_by_site[site]["n"]
            print(f"  {site:<25s} {br:>10.4f} {lr:>10.4f} {lr-br:>+10.4f} "
                  f"{n:>8d}", flush=True)

    # Save the model
    output_path = bert_dir / "rubric_weights.json"
    weights_dict = {
        "feature_names": feature_names,
        "weights": ridge.coef_.tolist(),
        "intercept": float(ridge.intercept_),
        "alpha": args.alpha,
    }
    with open(output_path, "w") as f:
        json.dump(weights_dict, f, indent=2)
    print(f"\nSaved rubric weights to {output_path}", flush=True)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()

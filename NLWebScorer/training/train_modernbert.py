"""Fine-tune ModernBERT on GPT-4.1 ranking data.

Usage:
    python -m training.train_modernbert [--config config/training_config.yaml]
    python -m training.train_modernbert --config config/training_config_rubric_gam.yaml --pure-text

Supports two modes:
  - Default: ModernBERT + schema_type embedding + 16 scalar rubric features
  - Pure-text (--pure-text): ModernBERT only, no rubric features in the head.
    Forces [CLS] to learn all relevance signals from text alone.
    After training, extracts and saves [CLS] embeddings for GAM training.
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
from transformers import AutoTokenizer, get_linear_schedule_with_warmup
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models.modernbert_scorer import ModernBERTScorer, ScorerDataset
from training.loss_utils import (
    pairwise_ranking_loss as _ranking_loss,
    pairwise_score_diff_loss as _score_diff_loss,
    lambda_weighted_score_diff_loss as _lambda_loss,
    satisficer_metrics as _satisficer_metrics,
)


class QueryGroupedBatchSampler(Sampler):
    """Batch sampler that groups examples from the same query together.

    Each batch contains examples from a single query, enabling pairwise
    ranking loss computation within the batch. Queries are shuffled each
    epoch, and examples within each query are also shuffled.
    """

    def __init__(self, dataset: ScorerDataset, batch_size: int):
        self.query_groups = dataset.query_groups
        self.batch_size = batch_size

    def __iter__(self):
        # Shuffle query order
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


def _forward_batch(model, batch, device, pure_text: bool = False):
    """Extract inputs from batch and run forward pass."""
    input_ids = batch["input_ids"].to(device)
    attention_mask = batch["attention_mask"].to(device)
    if pure_text:
        return model(input_ids, attention_mask)
    schema_type_idx = batch["schema_type_idx"].to(device)
    rubric_features = batch["rubric_features"].to(device)
    return model(input_ids, attention_mask,
                 schema_type_idx=schema_type_idx,
                 rubric_features=rubric_features)


def train_epoch(model, dataloader, optimizer, scheduler, criterion, device,
                epoch: int, log_interval: int = 50, grad_accum_steps: int = 1,
                pure_text: bool = False, ranking_alpha: float = 0.0,
                score_diff_alpha: float = 0.0, lambda_alpha: float = 0.0):
    model.train()
    total_loss = 0
    total_rank_loss = 0
    total_diff_loss = 0
    total_lambda_loss = 0
    n_batches = 0

    optimizer.zero_grad()
    for i, batch in enumerate(dataloader):
        targets = batch["score"].to(device).unsqueeze(1)
        predictions = _forward_batch(model, batch, device, pure_text=pure_text)
        mse_loss = criterion(predictions, targets)

        loss = mse_loss
        if ranking_alpha > 0:
            rank_loss = _ranking_loss(predictions, targets)
            loss = loss + ranking_alpha * rank_loss
            total_rank_loss += rank_loss.item()
        if score_diff_alpha > 0:
            diff_loss = _score_diff_loss(predictions, targets)
            loss = loss + score_diff_alpha * diff_loss
            total_diff_loss += diff_loss.item()
        if lambda_alpha > 0:
            lam_loss = _lambda_loss(predictions, targets)
            loss = loss + lambda_alpha * lam_loss
            total_lambda_loss += lam_loss.item()

        (loss / grad_accum_steps).backward()

        total_loss += mse_loss.item()
        n_batches += 1

        if (i + 1) % grad_accum_steps == 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()

        if (i + 1) % log_interval == 0:
            avg = total_loss / n_batches
            lr = scheduler.get_last_lr()[0]
            extra = ""
            if ranking_alpha > 0:
                extra += f" | RankL: {total_rank_loss / n_batches:.4f}"
            if score_diff_alpha > 0:
                extra += f" | DiffL: {total_diff_loss / n_batches:.4f}"
            if lambda_alpha > 0:
                extra += f" | LamL: {total_lambda_loss / n_batches:.4f}"
            print(f"  Epoch {epoch} | Batch {i+1}/{len(dataloader)} | "
                  f"MSE: {avg:.4f}{extra} | LR: {lr:.2e}", flush=True)

    if len(dataloader) % grad_accum_steps != 0:
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()
        optimizer.zero_grad()

    return total_loss / max(n_batches, 1)


@torch.no_grad()
def evaluate(model, dataloader, criterion, device, pure_text: bool = False):
    model.eval()
    total_loss = 0
    all_preds = []
    all_targets = []
    n_batches = 0

    for batch in dataloader:
        targets = batch["score"].to(device).unsqueeze(1)
        predictions = _forward_batch(model, batch, device, pure_text=pure_text)
        loss = criterion(predictions, targets)

        total_loss += loss.item()
        n_batches += 1
        all_preds.append(predictions.cpu())
        all_targets.append(targets.cpu())

    all_preds = torch.cat(all_preds)
    all_targets = torch.cat(all_targets)

    mae = (all_preds - all_targets).abs().mean().item()
    from scipy.stats import spearmanr
    rho, _ = spearmanr(all_preds.numpy().flatten(), all_targets.numpy().flatten())

    return {
        "loss": total_loss / max(n_batches, 1),
        "mae": mae,
        "spearman_rho": rho,
    }


def satisficer_metrics(preds, targets, examples, k=5):
    """Delegate to shared loss_utils.satisficer_metrics."""
    return _satisficer_metrics(preds, targets, examples, k=k)


@torch.no_grad()
def compute_bert_satisficer(model, dataloader, examples, device,
                            pure_text=False, k=5):
    """Compute satisficer metrics for BERT model on a data split."""
    model.eval()
    all_preds = []
    for batch in dataloader:
        predictions = _forward_batch(model, batch, device, pure_text=pure_text)
        all_preds.append(predictions.cpu().squeeze(-1))
    preds_np = torch.cat(all_preds).numpy()
    targets_np = np.array([ex["score"] for ex in examples])
    return satisficer_metrics(preds_np, targets_np, examples, k=k)


@torch.no_grad()
def extract_embeddings(model, dataloader, device, pure_text: bool = False):
    """Extract [CLS] embeddings from trained BERT model."""
    model.eval()
    all_embeddings = []
    for batch in dataloader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        embeddings = model.get_embeddings(input_ids, attention_mask)
        all_embeddings.append(embeddings.cpu())
    return torch.cat(all_embeddings, dim=0)


def main():
    parser = argparse.ArgumentParser(description="Fine-tune ModernBERT for scoring")
    parser.add_argument("--config", type=str,
                        default="config/training_config.yaml")
    parser.add_argument("--pure-text", action="store_true",
                        help="Train without rubric features (pure text → score)")
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to checkpoint to resume from (e.g., checkpoints/modernbert_large_pure/best_model.pt)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    bert_cfg = cfg["modernbert"]
    data_cfg = cfg["data"]
    pure_text = args.pure_text or bert_cfg.get("pure_text", False)

    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"Device: {device}", flush=True)
    print(f"Mode: {'pure-text' if pure_text else 'rubric-features'}", flush=True)

    print(f"Loading tokenizer: {bert_cfg['model_name']}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(bert_cfg["model_name"])

    project_root = Path(__file__).resolve().parents[1]
    prepared_dir = project_root / data_cfg["prepared_dir"]

    print("Loading datasets...", flush=True)
    train_data = load_jsonl(prepared_dir / "train.jsonl")
    val_data = load_jsonl(prepared_dir / "val.jsonl")
    print(f"  Train: {len(train_data)}, Val: {len(val_data)}", flush=True)

    # Load schema mapping
    with open(prepared_dir / "schema_type_mapping.json") as f:
        schema_mapping = json.load(f)
    print(f"  Schema types: {len(schema_mapping)}", flush=True)

    max_len = data_cfg.get("max_seq_length", 512)
    train_dataset = ScorerDataset(train_data, tokenizer, max_length=max_len,
                                  schema_mapping=schema_mapping)
    val_dataset = ScorerDataset(val_data, tokenizer, max_length=max_len,
                                schema_mapping=schema_mapping)

    use_cuda = device.type == "cuda"
    num_workers = 4 if use_cuda else 0

    ranking_alpha = bert_cfg.get("ranking_alpha", 0.0)
    score_diff_alpha = bert_cfg.get("score_diff_alpha", 0.0)
    lambda_alpha = bert_cfg.get("lambda_alpha", 0.0)
    if ranking_alpha > 0 or score_diff_alpha > 0 or lambda_alpha > 0:
        # Use query-grouped batching for pairwise losses
        grouped_sampler = QueryGroupedBatchSampler(
            train_dataset, batch_size=bert_cfg["per_device_train_batch_size"])
        train_loader = DataLoader(
            train_dataset,
            batch_sampler=grouped_sampler,
            num_workers=num_workers,
            pin_memory=use_cuda,
        )
    else:
        train_loader = DataLoader(
            train_dataset,
            batch_size=bert_cfg["per_device_train_batch_size"],
            shuffle=True,
            num_workers=num_workers,
            pin_memory=use_cuda,
        )
    val_loader = DataLoader(
        val_dataset,
        batch_size=bert_cfg["per_device_eval_batch_size"],
        shuffle=False,
        num_workers=num_workers,
        pin_memory=use_cuda,
    )

    print(f"Loading model: {bert_cfg['model_name']}", flush=True)
    model = ModernBERTScorer(
        model_name=bert_cfg["model_name"],
        num_schema_types=len(schema_mapping),
        use_rubric_features=not pure_text,
    ).to(device)

    if args.resume:
        resume_path = project_root / args.resume
        print(f"  Resuming from: {resume_path}", flush=True)
        ckpt = torch.load(resume_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        print(f"  Loaded checkpoint successfully", flush=True)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Total params: {total_params:,} | Trainable: {trainable_params:,}", flush=True)

    loss_type = bert_cfg.get("loss", "mse")
    criterion = nn.HuberLoss(delta=bert_cfg.get("huber_delta", 5.0) / 100.0) \
        if loss_type == "huber" else nn.MSELoss()

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=bert_cfg["learning_rate"],
        weight_decay=bert_cfg["weight_decay"],
    )

    grad_accum_steps = bert_cfg.get("gradient_accumulation_steps", 1)
    num_update_steps = (len(train_loader) // grad_accum_steps) * bert_cfg["num_epochs"]
    warmup_steps = int(num_update_steps * bert_cfg["warmup_ratio"])
    scheduler = get_linear_schedule_with_warmup(
        optimizer, warmup_steps, num_update_steps)

    output_dir = project_root / bert_cfg["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "schema_type_mapping.json", "w") as f:
        json.dump(schema_mapping, f, indent=2)

    best_selection = float("-inf")
    best_epoch = -1
    mae_lambda = bert_cfg.get("mae_lambda", 1.0)

    print(f"\nTraining for {bert_cfg['num_epochs']} epochs...", flush=True)
    eff_batch = bert_cfg['per_device_train_batch_size'] * grad_accum_steps
    print(f"  Batch size: {bert_cfg['per_device_train_batch_size']} x {grad_accum_steps} = {eff_batch} effective", flush=True)
    print(f"  Learning rate: {bert_cfg['learning_rate']}", flush=True)
    print(f"  Loss: {loss_type}", flush=True)
    print(f"  Warmup steps: {warmup_steps}/{num_update_steps}", flush=True)
    if pure_text:
        print(f"  Mode: PURE TEXT (no rubric features)", flush=True)
    else:
        print(f"  Rubric features: 16 scalar + schema_type embedding", flush=True)
    if ranking_alpha > 0:
        print(f"  Ranking loss alpha: {ranking_alpha}", flush=True)
    if score_diff_alpha > 0:
        print(f"  Score-diff loss alpha: {score_diff_alpha}", flush=True)
    if lambda_alpha > 0:
        print(f"  LambdaRank loss alpha: {lambda_alpha}", flush=True)
    if ranking_alpha > 0 or score_diff_alpha > 0 or lambda_alpha > 0:
        print(f"  (query-grouped batching enabled)", flush=True)
    print(f"  Model selection: satisficer_score - {mae_lambda} * MAE (top-5)", flush=True)
    print(flush=True)

    for epoch in range(1, bert_cfg["num_epochs"] + 1):
        t0 = time.time()
        train_loss = train_epoch(model, train_loader, optimizer, scheduler,
                                 criterion, device, epoch,
                                 grad_accum_steps=grad_accum_steps,
                                 pure_text=pure_text,
                                 ranking_alpha=ranking_alpha,
                                 score_diff_alpha=score_diff_alpha,
                                 lambda_alpha=lambda_alpha)
        val_metrics = evaluate(model, val_loader, criterion, device,
                               pure_text=pure_text)

        # Compute satisficer metrics on val set for model selection
        val_sat = compute_bert_satisficer(
            model, val_loader, val_data, device, pure_text=pure_text, k=5)
        sat_score = val_sat["satisficer_score"]
        val_mae = val_metrics["mae"]
        selection_score = sat_score - mae_lambda * val_mae
        elapsed = time.time() - t0

        print(f"Epoch {epoch}/{bert_cfg['num_epochs']} ({elapsed:.0f}s)", flush=True)
        print(f"  Train Loss: {train_loss:.4f}", flush=True)
        print(f"  Val MSE: {val_metrics['loss']:.4f} | "
              f"MAE: {val_mae:.4f} | "
              f"ρ: {val_metrics['spearman_rho']:.4f} | "
              f"good: {val_sat['good_picks']:.3f} | "
              f"bad: {val_sat['bad_picks']:.3f} | "
              f"pair: {val_sat['pairwise_accuracy']:.3f} | "
              f"sel: {selection_score:.3f}", flush=True)

        if selection_score > best_selection:
            best_selection = selection_score
            best_epoch = epoch
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_metrics": val_metrics,
                "val_satisficer": val_sat,
                "selection_score": selection_score,
                "config": {**bert_cfg, "pure_text": pure_text},
                "schema_mapping": schema_mapping,
            }, output_dir / "best_model.pt")
            print(f"  ✓ New best (sel={selection_score:.3f})", flush=True)

    print(f"\nBest model: epoch {best_epoch} (sel={best_selection:.3f})", flush=True)

    # Test set evaluation
    print("\nEvaluating on test set...", flush=True)
    model.load_state_dict(
        torch.load(output_dir / "best_model.pt", weights_only=False)["model_state_dict"])

    test_data = load_jsonl(prepared_dir / "test.jsonl")
    test_dataset = ScorerDataset(test_data, tokenizer, max_length=max_len,
                                 schema_mapping=schema_mapping)
    test_loader = DataLoader(test_dataset, batch_size=bert_cfg["per_device_eval_batch_size"],
                             shuffle=False, num_workers=num_workers, pin_memory=use_cuda)

    test_metrics = evaluate(model, test_loader, criterion, device,
                            pure_text=pure_text)
    test_sat = compute_bert_satisficer(
        model, test_loader, test_data, device, pure_text=pure_text, k=5)
    print(f"Test metrics:", flush=True)
    print(f"  Loss: {test_metrics['loss']:.4f} | "
          f"MAE: {test_metrics['mae']:.4f} | "
          f"Spearman ρ: {test_metrics['spearman_rho']:.4f}", flush=True)
    print(f"  Satisficer (top-5, {test_sat['n_queries']} answerable queries):", flush=True)
    print(f"    good_picks: {test_sat['good_picks']:.3f} | "
          f"bad_picks: {test_sat['bad_picks']:.3f} | "
          f"satisficer_score: {test_sat['satisficer_score']:.3f}", flush=True)

    # Extract and save [CLS] embeddings for GAM training
    if pure_text:
        print("\nExtracting [CLS] embeddings for GAM training...", flush=True)
        eval_batch_size = bert_cfg["per_device_eval_batch_size"]

        for split_name, split_data in [("train", train_data), ("val", val_data),
                                        ("test", test_data)]:
            ds = ScorerDataset(split_data, tokenizer, max_length=max_len,
                               schema_mapping=schema_mapping)
            loader = DataLoader(ds, batch_size=eval_batch_size, shuffle=False,
                                num_workers=num_workers, pin_memory=use_cuda)
            emb = extract_embeddings(model, loader, device, pure_text=pure_text)
            out_path = output_dir / f"{split_name}_embeddings.pt"
            torch.save(emb, out_path)
            print(f"  {split_name}: {emb.shape} → {out_path}", flush=True)

        # Holdout if available
        holdout_path = prepared_dir / "holdout_eval.jsonl"
        if holdout_path.exists():
            holdout_data = load_jsonl(holdout_path)
            ds = ScorerDataset(holdout_data, tokenizer, max_length=max_len,
                               schema_mapping=schema_mapping)
            loader = DataLoader(ds, batch_size=eval_batch_size, shuffle=False,
                                num_workers=num_workers, pin_memory=use_cuda)
            emb = extract_embeddings(model, loader, device, pure_text=pure_text)
            out_path = output_dir / "holdout_embeddings.pt"
            torch.save(emb, out_path)
            print(f"  holdout: {emb.shape} → {out_path}", flush=True)

    print("\nTraining complete.", flush=True)


if __name__ == "__main__":
    main()

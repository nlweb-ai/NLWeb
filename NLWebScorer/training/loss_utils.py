"""Shared loss functions and evaluation metrics for NLWebScorer.

Contains:
- pairwise_ranking_loss: Margin-based ranking loss
- pairwise_score_diff_loss: MSE on score differences
- lambda_weighted_score_diff_loss: Score-diff loss with LambdaRank weighting
- satisficer_metrics: Top-k good/bad picks evaluation
- pairwise_accuracy: Fraction of correctly ordered pairs
"""

from collections import defaultdict

import numpy as np
import torch


def pairwise_ranking_loss(predictions, targets, margin=0.05):
    """Margin-based pairwise ranking loss within a batch.

    For pairs (i,j) where target_i > target_j + margin,
    encourage pred_i > pred_j.
    """
    pred = predictions.squeeze(-1)
    tgt = targets.squeeze(-1)

    tgt_diff = tgt.unsqueeze(0) - tgt.unsqueeze(1)
    pred_diff = pred.unsqueeze(0) - pred.unsqueeze(1)

    valid = tgt_diff > margin
    if not valid.any():
        return torch.tensor(0.0, device=predictions.device)

    pair_loss = torch.clamp(margin - pred_diff[valid], min=0.0)
    return pair_loss.mean()


def pairwise_score_diff_loss(predictions, targets, min_gap=0.05):
    """MSE on pairwise score differences within a batch.

    Teaches the model to reproduce the exact magnitude of score gaps.
    """
    pred = predictions.squeeze(-1)
    tgt = targets.squeeze(-1)
    n = tgt.size(0)

    if n < 2:
        return torch.tensor(0.0, device=predictions.device)

    tgt_diff = tgt.unsqueeze(0) - tgt.unsqueeze(1)
    pred_diff = pred.unsqueeze(0) - pred.unsqueeze(1)

    row_idx, col_idx = torch.triu_indices(n, n, offset=1, device=tgt.device)
    tgt_pairs = tgt_diff[row_idx, col_idx]
    pred_pairs = pred_diff[row_idx, col_idx]

    valid = tgt_pairs.abs() > min_gap
    if not valid.any():
        return torch.tensor(0.0, device=predictions.device)

    diff_error = (pred_pairs[valid] - tgt_pairs[valid]) ** 2
    return diff_error.mean()


def lambda_weighted_score_diff_loss(predictions, targets, k=5, min_gap=0.05,
                                     boost=5.0):
    """Score-diff loss with LambdaRank-style weighting.

    Pairs near the top-k boundary are weighted by how much swapping them
    would change the satisficer metric (good_picks - 2*bad_picks).

    Args:
        predictions: Model predictions, shape (N,) or (N,1)
        targets: Ground truth scores, shape (N,) or (N,1)
        k: Top-k for satisficer metric
        min_gap: Minimum target gap to consider a pair
        boost: Multiplier for boundary pair weights
    """
    pred = predictions.squeeze(-1)
    tgt = targets.squeeze(-1)
    n = pred.size(0)

    if n < 2:
        return torch.tensor(0.0, device=predictions.device)

    # Get predicted ranks (0 = highest predicted score)
    pred_ranks = torch.argsort(torch.argsort(pred, descending=True))

    # Pairwise diffs (upper triangle only)
    tgt_diff = tgt.unsqueeze(0) - tgt.unsqueeze(1)
    pred_diff = pred.unsqueeze(0) - pred.unsqueeze(1)

    row_idx, col_idx = torch.triu_indices(n, n, offset=1, device=pred.device)
    tgt_pairs = tgt_diff[row_idx, col_idx]
    pred_pairs = pred_diff[row_idx, col_idx]

    valid = tgt_pairs.abs() > min_gap
    if not valid.any():
        return torch.tensor(0.0, device=predictions.device)

    # Compute LambdaRank weights
    rank_i = pred_ranks[row_idx].float()
    rank_j = pred_ranks[col_idx].float()
    score_i = tgt[row_idx]
    score_j = tgt[col_idx]

    in_top_i = rank_i < k
    in_top_j = rank_j < k

    # Boundary pairs: exactly one item is in top-k
    boundary = (in_top_i != in_top_j)

    # For boundary pairs, compute |ΔSatisficer| if these two were swapped
    # The item NOT in top-k would enter; the one IN top-k would leave
    entering_score = torch.where(in_top_i, score_j, score_i)
    leaving_score = torch.where(in_top_i, score_i, score_j)

    k_f = float(k)
    delta = torch.zeros_like(tgt_pairs)

    # Good item (≥0.6) entering top-k: +1/k to satisficer
    delta = delta + torch.where(entering_score >= 0.6,
                                 torch.tensor(1.0 / k_f, device=pred.device),
                                 torch.tensor(0.0, device=pred.device))
    # Good item leaving top-k: -1/k
    delta = delta - torch.where(leaving_score >= 0.6,
                                 torch.tensor(1.0 / k_f, device=pred.device),
                                 torch.tensor(0.0, device=pred.device))
    # Bad item (≤0.3) entering top-k: -2/k (bad_picks penalty is 2x)
    delta = delta - torch.where(entering_score <= 0.3,
                                 torch.tensor(2.0 / k_f, device=pred.device),
                                 torch.tensor(0.0, device=pred.device))
    # Bad item leaving top-k: +2/k
    delta = delta + torch.where(leaving_score <= 0.3,
                                 torch.tensor(2.0 / k_f, device=pred.device),
                                 torch.tensor(0.0, device=pred.device))

    # Weight: baseline 1.0 + boost * |delta| for boundary pairs
    weights = torch.where(boundary,
                           1.0 + boost * delta.abs(),
                           torch.tensor(1.0, device=pred.device))

    # Weighted MSE on score differences
    diff_error = (pred_pairs[valid] - tgt_pairs[valid]) ** 2
    pair_weights = weights[valid]

    return (diff_error * pair_weights).sum() / pair_weights.sum()


def satisficer_metrics(preds, targets, examples, k=5):
    """Top-k satisficer metrics + pairwise accuracy.

    Returns good_picks, bad_picks, satisficer_score, pairwise_accuracy.
    Only evaluates queries with at least one good result (score >= 0.6).
    """
    query_groups = defaultdict(list)
    for p, t, ex in zip(preds, targets, examples):
        query_groups[ex["query"]].append((p, t))

    good_picks_all, bad_picks_all = [], []
    pair_correct, pair_total = 0, 0

    for query, items in query_groups.items():
        if len(items) < k:
            continue
        targets_q = np.array([x[1] for x in items])
        if not any(t >= 0.6 for t in targets_q):
            continue
        preds_q = np.array([x[0] for x in items])

        # Satisficer metrics
        pred_top_k = set(np.argsort(preds_q)[-k:])
        good_picks_all.append(
            sum(1 for i in pred_top_k if targets_q[i] >= 0.6) / k)
        bad_picks_all.append(
            sum(1 for i in pred_top_k if targets_q[i] <= 0.3) / k)

        # Pairwise accuracy (vectorized)
        n = len(preds_q)
        tgt_d = targets_q[:, None] - targets_q[None, :]
        pred_d = preds_q[:, None] - preds_q[None, :]
        mask = np.triu(np.ones((n, n), dtype=bool), k=1) & (np.abs(tgt_d) > 0.05)
        if mask.sum() > 0:
            agree = (tgt_d[mask] * pred_d[mask]) > 0
            pair_correct += int(agree.sum())
            pair_total += int(mask.sum())

    good = float(np.mean(good_picks_all)) if good_picks_all else 0
    bad = float(np.mean(bad_picks_all)) if bad_picks_all else 0

    return {
        "good_picks": good,
        "bad_picks": bad,
        "n_queries": len(good_picks_all),
        "satisficer_score": good - 2.0 * bad,
        "pairwise_accuracy": pair_correct / max(pair_total, 1),
        "pairwise_total": pair_total,
    }

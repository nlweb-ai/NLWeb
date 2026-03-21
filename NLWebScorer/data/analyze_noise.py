"""Analyze noise in NLWebScorer training data.

Detects:
1. Within-query inconsistencies: items with similar text but very different scores
2. Cross-query inconsistencies: same item scored differently across queries
3. Low-discriminative queries: all items scored similarly (no ranking signal)
4. Text-score misalignment: scores that don't correlate with text relevance

Usage:
    python -m data.analyze_noise --data-dir data/prepared_hard
    python -m data.analyze_noise --data-dir data/prepared_hard --output-weights data/prepared_hard/quality_weights.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f]


def text_overlap(text_a, text_b):
    """Jaccard similarity between two texts (word-level)."""
    words_a = set(re.findall(r'\w+', text_a.lower()))
    words_b = set(re.findall(r'\w+', text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def analyze_within_query(examples):
    """Find items in the same query with similar text but different scores."""
    query_groups = defaultdict(list)
    for i, ex in enumerate(examples):
        query_groups[(ex["site"], ex["query"])].append((i, ex))

    inconsistencies = []
    for (site, query), items in query_groups.items():
        if len(items) < 2:
            continue
        for idx_a in range(len(items)):
            for idx_b in range(idx_a + 1, len(items)):
                i_a, ex_a = items[idx_a]
                i_b, ex_b = items[idx_b]
                score_diff = abs(ex_a["score"] - ex_b["score"])
                if score_diff < 0.2:
                    continue
                overlap = text_overlap(ex_a["item_text"], ex_b["item_text"])
                if overlap > 0.7:
                    inconsistencies.append({
                        "site": site,
                        "query": query,
                        "idx_a": i_a,
                        "idx_b": i_b,
                        "score_a": ex_a["score"],
                        "score_b": ex_b["score"],
                        "score_diff": score_diff,
                        "text_overlap": overlap,
                    })

    return inconsistencies


def analyze_cross_query(examples):
    """Find items that appear across queries with inconsistent scores."""
    # Group by item URL/name (proxy for identity)
    item_groups = defaultdict(list)
    for i, ex in enumerate(examples):
        # Use site + item_text hash as item identity
        item_key = (ex["site"], ex["item_text"][:200])
        item_groups[item_key].append((i, ex))

    inconsistencies = []
    for item_key, occurrences in item_groups.items():
        if len(occurrences) < 2:
            continue
        scores = [ex["score"] for _, ex in occurrences]
        score_range = max(scores) - min(scores)
        if score_range > 0.3:
            inconsistencies.append({
                "site": item_key[0],
                "item_preview": item_key[1][:80],
                "n_queries": len(occurrences),
                "scores": scores,
                "score_range": score_range,
                "queries": [ex["query"] for _, ex in occurrences],
                "indices": [i for i, _ in occurrences],
            })

    return inconsistencies


def analyze_low_discriminative(examples):
    """Find queries where all items score similarly (no ranking signal)."""
    query_groups = defaultdict(list)
    for ex in examples:
        query_groups[(ex["site"], ex["query"])].append(ex["score"])

    low_disc = []
    for (site, query), scores in query_groups.items():
        if len(scores) < 5:
            continue
        score_arr = np.array(scores)
        variance = score_arr.var()
        score_range = score_arr.max() - score_arr.min()
        if variance < 0.005:  # Very low variance
            low_disc.append({
                "site": site,
                "query": query,
                "n_items": len(scores),
                "mean_score": float(score_arr.mean()),
                "variance": float(variance),
                "range": float(score_range),
                "min": float(score_arr.min()),
                "max": float(score_arr.max()),
            })

    return low_disc


def analyze_text_score_alignment(examples):
    """Check if scores correlate with simple text relevance signals."""
    query_groups = defaultdict(list)
    for ex in examples:
        query_groups[(ex["site"], ex["query"])].append(ex)

    misaligned = []
    for (site, query), items in query_groups.items():
        if len(items) < 5:
            continue

        # Compare query_term_coverage with score
        coverages = np.array([ex.get("query_term_coverage", 0) for ex in items])
        scores = np.array([ex["score"] for ex in items])

        if coverages.std() < 0.01 or scores.std() < 0.01:
            continue

        # Spearman correlation between coverage and score
        from scipy.stats import spearmanr
        rho, pval = spearmanr(coverages, scores)

        if rho < -0.3 and pval < 0.05:
            # Negative correlation: high coverage → low score (suspicious)
            misaligned.append({
                "site": site,
                "query": query,
                "n_items": len(items),
                "coverage_score_rho": float(rho),
                "p_value": float(pval),
                "mean_coverage": float(coverages.mean()),
                "mean_score": float(scores.mean()),
            })

    return misaligned


def compute_quality_weights(examples, within_query_issues, cross_query_issues,
                             low_disc_queries):
    """Compute per-example quality weights (0-1) based on noise analysis."""
    weights = np.ones(len(examples))

    # Downweight examples involved in within-query inconsistencies
    for issue in within_query_issues:
        weights[issue["idx_a"]] *= 0.5
        weights[issue["idx_b"]] *= 0.5

    # Downweight examples involved in cross-query inconsistencies
    for issue in cross_query_issues:
        for idx in issue["indices"]:
            weights[idx] *= 0.7

    # Downweight examples from low-discriminative queries
    low_disc_set = set((q["site"], q["query"]) for q in low_disc_queries)
    for i, ex in enumerate(examples):
        if (ex["site"], ex["query"]) in low_disc_set:
            weights[i] *= 0.5

    return weights


def main():
    parser = argparse.ArgumentParser(description="Analyze noise in training data")
    parser.add_argument("--data-dir", type=str, default="data/prepared_hard")
    parser.add_argument("--output-weights", type=str, default=None,
                        help="Path to save quality weights JSON")
    parser.add_argument("--split", type=str, default="train",
                        help="Which split to analyze (train, val, test)")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / args.data_dir

    print(f"Loading {args.split} data from {data_dir}...", flush=True)
    examples = load_jsonl(data_dir / f"{args.split}.jsonl")
    print(f"  {len(examples)} examples", flush=True)

    # 1. Within-query inconsistencies
    print("\n" + "=" * 60)
    print("1. WITHIN-QUERY INCONSISTENCIES")
    print("   (Similar text, different scores within same query)")
    print("=" * 60)
    within_issues = analyze_within_query(examples)
    if within_issues:
        print(f"\n  Found {len(within_issues)} inconsistent pairs:")
        for issue in sorted(within_issues, key=lambda x: -x["score_diff"])[:20]:
            print(f"    [{issue['site']}] '{issue['query'][:50]}' "
                  f"scores={issue['score_a']:.2f} vs {issue['score_b']:.2f} "
                  f"(overlap={issue['text_overlap']:.2f})")
    else:
        print("\n  No within-query inconsistencies found (all similar-text pairs "
              "have similar scores).")

    # 2. Cross-query inconsistencies
    print("\n" + "=" * 60)
    print("2. CROSS-QUERY INCONSISTENCIES")
    print("   (Same item scored differently across queries)")
    print("=" * 60)
    cross_issues = analyze_cross_query(examples)
    if cross_issues:
        print(f"\n  Found {len(cross_issues)} items with inconsistent scores:")
        for issue in sorted(cross_issues, key=lambda x: -x["score_range"])[:20]:
            print(f"    [{issue['site']}] range={issue['score_range']:.2f} "
                  f"scores={[f'{s:.2f}' for s in issue['scores']]} "
                  f"item='{issue['item_preview'][:40]}...'")
            for q, s in zip(issue["queries"], issue["scores"]):
                print(f"      query='{q[:50]}' → score={s:.2f}")
    else:
        print("\n  No cross-query inconsistencies found "
              "(items don't repeat across queries, or scores are consistent).")

    # 3. Low-discriminative queries
    print("\n" + "=" * 60)
    print("3. LOW-DISCRIMINATIVE QUERIES")
    print("   (All items scored similarly — no ranking signal)")
    print("=" * 60)
    low_disc = analyze_low_discriminative(examples)
    if low_disc:
        print(f"\n  Found {len(low_disc)} low-discriminative queries "
              f"(variance < 0.005):")
        # Group by type
        all_high = [q for q in low_disc if q["mean_score"] >= 0.6]
        all_low = [q for q in low_disc if q["mean_score"] <= 0.3]
        mixed = [q for q in low_disc
                 if 0.3 < q["mean_score"] < 0.6]
        print(f"    All-good (mean≥0.6): {len(all_high)} queries")
        print(f"    All-bad (mean≤0.3):  {len(all_low)} queries")
        print(f"    All-medium:          {len(mixed)} queries")
        print(f"\n  Examples:")
        for q in sorted(low_disc, key=lambda x: x["variance"])[:15]:
            print(f"    [{q['site']}] '{q['query'][:45]}' "
                  f"mean={q['mean_score']:.2f} var={q['variance']:.4f} "
                  f"range={q['range']:.2f} n={q['n_items']}")
    else:
        print("\n  No low-discriminative queries found.")

    # 4. Text-score alignment
    print("\n" + "=" * 60)
    print("4. TEXT-SCORE MISALIGNMENT")
    print("   (Queries where text relevance negatively correlates with score)")
    print("=" * 60)
    misaligned = analyze_text_score_alignment(examples)
    if misaligned:
        print(f"\n  Found {len(misaligned)} queries with negative "
              "coverage-score correlation:")
        for m in sorted(misaligned, key=lambda x: x["coverage_score_rho"])[:15]:
            print(f"    [{m['site']}] '{m['query'][:45]}' "
                  f"ρ={m['coverage_score_rho']:.3f} "
                  f"(p={m['p_value']:.3f}, n={m['n_items']})")
    else:
        print("\n  No text-score misalignment found.")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_queries = len(set((ex["site"], ex["query"]) for ex in examples))
    print(f"  Total examples: {len(examples)}")
    print(f"  Total queries:  {total_queries}")
    print(f"  Within-query inconsistencies: {len(within_issues)}")
    print(f"  Cross-query inconsistencies:  {len(cross_issues)}")
    print(f"  Low-discriminative queries:   {len(low_disc)} "
          f"({len(low_disc)/total_queries*100:.1f}%)")
    print(f"  Text-score misaligned:        {len(misaligned)}")

    # Compute and save quality weights
    if args.output_weights:
        print(f"\nComputing quality weights...", flush=True)
        weights = compute_quality_weights(
            examples, within_issues, cross_issues, low_disc)
        weights_data = {
            "weights": weights.tolist(),
            "n_downweighted": int((weights < 1.0).sum()),
            "mean_weight": float(weights.mean()),
            "min_weight": float(weights.min()),
        }
        with open(args.output_weights, "w") as f:
            json.dump(weights_data, f)
        print(f"  Saved weights to {args.output_weights}")
        print(f"  {weights_data['n_downweighted']}/{len(weights)} examples "
              f"downweighted (mean={weights_data['mean_weight']:.3f})")


if __name__ == "__main__":
    main()

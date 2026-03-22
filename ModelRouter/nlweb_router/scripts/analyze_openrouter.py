"""Analyze OpenRouter model scores vs GPT-4.1 reference.

Computes rank correlation (Spearman's rho) per query, then averages across queries.
This measures how well each model preserves the ranking of items within a query.

Reads   data/scores_azure_oai.json (GPT-4.1 reference)
        data/scores_azure_oai_gpt-4.1-mini.json (Azure mini model)
        data/scores_azure_oai_gpt-4o-mini.json (Azure 4o-mini model)
        data/scores_openrouter.json
        data/cost_openrouter.json
Writes  data/analysis_openrouter.json
"""

import argparse
import json
from pathlib import Path
from statistics import mean, median

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
AZURE_SCORES_PATH = DATA_DIR / "scores_azure_oai.json"
AZURE_41MINI_PATH = DATA_DIR / "scores_azure_oai_gpt-4.1-mini.json"
AZURE_4OMINI_PATH = DATA_DIR / "scores_azure_oai_gpt-4o-mini.json"
OPENROUTER_SCORES_PATH = DATA_DIR / "scores_openrouter.json"
OPENROUTER_COST_PATH = DATA_DIR / "cost_openrouter.json"
OUTPUT_PATH = DATA_DIR / "analysis_openrouter.json"


def get_ranks(values: list[float]) -> list[float]:
    """Convert values to ranks (1-based, higher value = lower rank number)."""
    indexed = [(v, i) for i, v in enumerate(values)]
    indexed.sort(key=lambda x: -x[0])  # Sort descending
    ranks = [0.0] * len(values)
    for rank, (_, orig_idx) in enumerate(indexed, 1):
        ranks[orig_idx] = float(rank)
    return ranks


def spearman_correlation(x: list[float], y: list[float]) -> float:
    """Compute Spearman's rank correlation coefficient."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0

    ranks_x = get_ranks(x)
    ranks_y = get_ranks(y)

    n = len(x)
    mean_x = sum(ranks_x) / n
    mean_y = sum(ranks_y) / n

    numerator = sum((rx - mean_x) * (ry - mean_y) for rx, ry in zip(ranks_x, ranks_y))
    sum_sq_x = sum((rx - mean_x) ** 2 for rx in ranks_x)
    sum_sq_y = sum((ry - mean_y) ** 2 for ry in ranks_y)

    denominator = (sum_sq_x * sum_sq_y) ** 0.5
    if denominator == 0:
        return 0.0

    return numerator / denominator


def top_k_overlap(model_scores: list[float], ref_scores: list[float], k: int) -> int:
    """Count how many of the top-k items by ref_scores are in the top-k by model_scores."""
    if len(model_scores) < k or len(ref_scores) < k:
        return 0

    # Get indices of top-k items for each
    indexed_model = [(s, i) for i, s in enumerate(model_scores)]
    indexed_ref = [(s, i) for i, s in enumerate(ref_scores)]

    indexed_model.sort(key=lambda x: -x[0])  # Descending
    indexed_ref.sort(key=lambda x: -x[0])

    model_top_k = set(i for _, i in indexed_model[:k])
    ref_top_k = set(i for _, i in indexed_ref[:k])

    return len(model_top_k & ref_top_k)


def bad_picks(model_scores: list[float], ref_scores: list[float], top_k: int, threshold: int = 50) -> int:
    """Count how many of model's top-k have ref_score below threshold."""
    if len(model_scores) < top_k:
        return 0

    # Get indices of model's top-k items
    indexed_model = [(s, i) for i, s in enumerate(model_scores)]
    indexed_model.sort(key=lambda x: -x[0])  # Descending (best first)
    model_top_k_indices = [i for _, i in indexed_model[:top_k]]

    # Count how many have ref_score < threshold
    return sum(1 for idx in model_top_k_indices if ref_scores[idx] < threshold)


def good_picks(model_scores: list[float], ref_scores: list[float], top_k: int, threshold: int = 70) -> int:
    """Count how many of model's top-k have ref_score >= threshold."""
    if len(model_scores) < top_k:
        return 0

    # Get indices of model's top-k items
    indexed_model = [(s, i) for i, s in enumerate(model_scores)]
    indexed_model.sort(key=lambda x: -x[0])  # Descending (best first)
    model_top_k_indices = [i for _, i in indexed_model[:top_k]]

    # Count how many have ref_score >= threshold
    return sum(1 for idx in model_top_k_indices if ref_scores[idx] >= threshold)


def main():
    parser = argparse.ArgumentParser(description="Analyze OpenRouter models vs GPT-4.1")
    parser.add_argument("-n", "--top-n", type=int, default=5,
                        help="Number of top models to show (default: 5)")
    args = parser.parse_args()

    # Load GPT-4.1 scores grouped by query
    if not AZURE_SCORES_PATH.exists():
        print(f"ERROR: No Azure scores at {AZURE_SCORES_PATH}")
        return

    print(f"Loading {AZURE_SCORES_PATH}...")
    with open(AZURE_SCORES_PATH) as f:
        azure_data = json.load(f)

    # Build lookup: query -> {url -> gpt41_score}
    gpt41_by_query: dict[str, dict[str, int]] = {}
    for q in azure_data:
        query = q["query"]
        gpt41_by_query[query] = {}
        for item in q.get("items", []):
            url = item.get("url", "")
            score = item.get("score", -1)
            if score >= 0:
                gpt41_by_query[query][url] = score

    total_gpt41 = sum(len(v) for v in gpt41_by_query.values())
    print(f"  Loaded {total_gpt41} GPT-4.1 scores across {len(gpt41_by_query)} queries")

    # Load OpenRouter scores
    if not OPENROUTER_SCORES_PATH.exists():
        print(f"ERROR: No OpenRouter scores at {OPENROUTER_SCORES_PATH}")
        return

    print(f"Loading {OPENROUTER_SCORES_PATH}...")
    with open(OPENROUTER_SCORES_PATH) as f:
        openrouter_data = json.load(f)

    # Structure: {model: {query: [(or_score, gpt41_score, latency), ...]}}
    model_query_data: dict[str, dict[str, list[tuple[int, int, int]]]] = {}

    for q in openrouter_data:
        query = q["query"]
        gpt41_scores_for_query = gpt41_by_query.get(query, {})

        for item in q.get("items", []):
            url = item.get("url", "")
            gpt41_score = gpt41_scores_for_query.get(url)

            if gpt41_score is None:
                continue

            for ms in item.get("model_scores", []):
                model = ms.get("model", "")
                or_score = ms.get("score", -1)
                latency = ms.get("response_time_ms", 0)

                if or_score >= 0 and model:
                    if model not in model_query_data:
                        model_query_data[model] = {}
                    if query not in model_query_data[model]:
                        model_query_data[model][query] = []
                    model_query_data[model][query].append((or_score, gpt41_score, latency))

    print(f"  Found {len(model_query_data)} OpenRouter models with matched scores")

    # Load Azure mini model scores (gpt-4.1-mini)
    if AZURE_41MINI_PATH.exists():
        print(f"Loading {AZURE_41MINI_PATH}...")
        with open(AZURE_41MINI_PATH) as f:
            azure_41mini_data = json.load(f)

        for q in azure_41mini_data:
            query = q["query"]
            gpt41_scores_for_query = gpt41_by_query.get(query, {})

            for item in q.get("items", []):
                url = item.get("url", "")
                gpt41_score = gpt41_scores_for_query.get(url)
                model_score = item.get("score", -1)
                latency = item.get("response_time_ms", 0)

                if gpt41_score is not None and model_score >= 0:
                    model = "azure/gpt-4.1-mini"
                    if model not in model_query_data:
                        model_query_data[model] = {}
                    if query not in model_query_data[model]:
                        model_query_data[model][query] = []
                    model_query_data[model][query].append((model_score, gpt41_score, latency))

        print(f"  Added azure/gpt-4.1-mini scores")

    # Load Azure mini model scores (gpt-4o-mini)
    if AZURE_4OMINI_PATH.exists():
        print(f"Loading {AZURE_4OMINI_PATH}...")
        with open(AZURE_4OMINI_PATH) as f:
            azure_4omini_data = json.load(f)

        for q in azure_4omini_data:
            query = q["query"]
            gpt41_scores_for_query = gpt41_by_query.get(query, {})

            for item in q.get("items", []):
                url = item.get("url", "")
                gpt41_score = gpt41_scores_for_query.get(url)
                model_score = item.get("score", -1)
                latency = item.get("response_time_ms", 0)

                if gpt41_score is not None and model_score >= 0:
                    model = "azure/gpt-4o-mini"
                    if model not in model_query_data:
                        model_query_data[model] = {}
                    if query not in model_query_data[model]:
                        model_query_data[model][query] = []
                    model_query_data[model][query].append((model_score, gpt41_score, latency))

        print(f"  Added azure/gpt-4o-mini scores")

    print(f"  Total: {len(model_query_data)} models with matched scores")

    # Load cost data
    cost_lookup = {}
    if OPENROUTER_COST_PATH.exists():
        print(f"Loading {OPENROUTER_COST_PATH}...")
        with open(OPENROUTER_COST_PATH) as f:
            cost_data = json.load(f)
        for entry in cost_data:
            model = entry.get("model", "")
            cost_lookup[model] = {
                "total_cost_usd": entry.get("total_cost_usd", 0),
                "cost_per_pair_usd": entry.get("cost_per_pair_usd", 0),
            }

    # Add Azure model costs
    azure_41mini_cost_path = DATA_DIR / "cost_azure_oai_gpt-4.1-mini.json"
    if azure_41mini_cost_path.exists():
        with open(azure_41mini_cost_path) as f:
            cost_info = json.load(f)
        cost_lookup["azure/gpt-4.1-mini"] = {
            "total_cost_usd": cost_info.get("total_cost_usd", 0),
            "cost_per_pair_usd": cost_info.get("cost_per_pair_usd", 0),
        }

    azure_4omini_cost_path = DATA_DIR / "cost_azure_oai_gpt-4o-mini.json"
    if azure_4omini_cost_path.exists():
        with open(azure_4omini_cost_path) as f:
            cost_info = json.load(f)
        cost_lookup["azure/gpt-4o-mini"] = {
            "total_cost_usd": cost_info.get("total_cost_usd", 0),
            "cost_per_pair_usd": cost_info.get("cost_per_pair_usd", 0),
        }

    # Compute metrics per model
    model_metrics = []

    for model, query_data in model_query_data.items():
        # Compute Spearman correlation per query, then average
        # For latency: compute time to first result (min latency per query), then average
        query_correlations = []
        first_result_latencies = []  # min latency per query
        top5_overlaps = []  # overlap of top-5 items
        top10_overlaps = []  # overlap of top-10 items
        bad5_below50 = []  # model's top-5 with ref score < 50
        bad10_below50 = []  # model's top-10 with ref score < 50
        good5_above70 = []  # model's top-5 with ref score >= 70
        good10_above70 = []  # model's top-10 with ref score >= 70
        good5_above60 = []  # model's top-5 with ref score >= 60
        good10_above60 = []  # model's top-10 with ref score >= 60
        total_pairs = 0

        for query, items in query_data.items():
            if len(items) < 3:  # Need at least 3 items for meaningful correlation
                continue

            or_scores = [d[0] for d in items]
            gpt41_scores = [d[1] for d in items]
            latencies = [d[2] for d in items]

            corr = spearman_correlation(or_scores, gpt41_scores)
            query_correlations.append(corr)

            # Top-K overlap metrics
            if len(items) >= 5:
                top5_overlaps.append(top_k_overlap(or_scores, gpt41_scores, 5))
            if len(items) >= 10:
                top10_overlaps.append(top_k_overlap(or_scores, gpt41_scores, 10))

            # Bad picks: model's top-K items where GPT-4.1 score < 50
            if len(items) >= 10:
                bad5_below50.append(bad_picks(or_scores, gpt41_scores, 5, 50))
                bad10_below50.append(bad_picks(or_scores, gpt41_scores, 10, 50))
                # Good picks: model's top-K items where GPT-4.1 score >= threshold
                good5_above70.append(good_picks(or_scores, gpt41_scores, 5, 70))
                good10_above70.append(good_picks(or_scores, gpt41_scores, 10, 70))
                good5_above60.append(good_picks(or_scores, gpt41_scores, 5, 60))
                good10_above60.append(good_picks(or_scores, gpt41_scores, 10, 60))

            # Time to first result = minimum latency for this query
            if latencies:
                first_result_latencies.append(min(latencies))

            total_pairs += len(items)

        if not query_correlations:
            continue

        avg_rank_corr = mean(query_correlations)
        # Average "time to first result" across queries
        avg_first_result_ms = mean(first_result_latencies) if first_result_latencies else 0
        # Average top-K overlaps
        avg_top5_overlap = mean(top5_overlaps) if top5_overlaps else 0
        avg_top10_overlap = mean(top10_overlaps) if top10_overlaps else 0
        # Average bad picks (model's top-K with ref score < 50)
        avg_bad5_below50 = mean(bad5_below50) if bad5_below50 else 0
        avg_bad10_below50 = mean(bad10_below50) if bad10_below50 else 0
        # Average good picks (model's top-K with ref score >= threshold)
        avg_good5_above70 = mean(good5_above70) if good5_above70 else 0
        avg_good10_above70 = mean(good10_above70) if good10_above70 else 0
        avg_good5_above60 = mean(good5_above60) if good5_above60 else 0
        avg_good10_above60 = mean(good10_above60) if good10_above60 else 0

        cost_info = cost_lookup.get(model, {})

        model_metrics.append({
            "model": model,
            "num_queries": len(query_correlations),
            "num_pairs": total_pairs,
            "rank_correlation": round(avg_rank_corr, 4),
            "top5_overlap": round(avg_top5_overlap, 2),
            "top10_overlap": round(avg_top10_overlap, 2),
            "good5_70": round(avg_good5_above70, 2),
            "good10_70": round(avg_good10_above70, 2),
            "good5_60": round(avg_good5_above60, 2),
            "good10_60": round(avg_good10_above60, 2),
            "bad5_50": round(avg_bad5_below50, 2),
            "bad10_50": round(avg_bad10_below50, 2),
            "avg_first_result_ms": round(avg_first_result_ms, 1),
            "total_cost_usd": round(cost_info.get("total_cost_usd", 0), 6),
            "cost_per_pair_usd": round(cost_info.get("cost_per_pair_usd", 0), 8),
        })

    # Sort by rank correlation descending
    model_metrics.sort(key=lambda x: x["rank_correlation"], reverse=True)

    # Print all models
    print(f"\n{'='*170}")
    print(f"{'Model':<40} {'Spearman':>8} {'Top5':>5} {'Top10':>5} {'G5@70':>6} {'G10@70':>6} {'G5@60':>6} {'G10@60':>6} {'B5<50':>6} {'B10<50':>6} {'1st Res':>8} {'Cost/1K':>8}")
    print(f"{'='*170}")

    for m in model_metrics:
        cost_per_1k = m['cost_per_pair_usd'] * 50 * 1000  # 50 items per query, 1000 queries
        print(f"{m['model']:<40} {m['rank_correlation']:>8.4f} {m['top5_overlap']:>5.1f} {m['top10_overlap']:>5.1f} {m['good5_70']:>6.2f} {m['good10_70']:>6.2f} {m['good5_60']:>6.2f} {m['good10_60']:>6.2f} {m['bad5_50']:>6.2f} {m['bad10_50']:>6.2f} {m['avg_first_result_ms']:>6.0f}ms ${cost_per_1k:>6.2f}")

    # Top N by rank correlation
    top_corr = model_metrics[:args.top_n]

    print(f"\n>>> TOP {args.top_n} BY RANK CORRELATION:")
    print(f"{'Rank':<5} {'Model':<40} {'Spearman':>8} {'G5@70':>6} {'G10@70':>6} {'G5@60':>6} {'G10@60':>6} {'B5<50':>6} {'1st Res':>8} {'Cost/1K':>8}")
    print("-" * 130)
    for i, m in enumerate(top_corr, 1):
        cost_per_1k = m['cost_per_pair_usd'] * 50 * 1000
        print(f"{i:<5} {m['model']:<40} {m['rank_correlation']:>8.4f} {m['good5_70']:>6.2f} {m['good10_70']:>6.2f} {m['good5_60']:>6.2f} {m['good10_60']:>6.2f} {m['bad5_50']:>6.2f} {m['avg_first_result_ms']:>6.0f}ms ${cost_per_1k:>6.2f}")

    # Among top N, rank by latency (time to first result)
    by_latency = sorted(top_corr, key=lambda x: x["avg_first_result_ms"])

    print(f"\n>>> TOP {args.top_n} - RANKED BY TIME TO FIRST RESULT:")
    print(f"{'Rank':<5} {'Model':<40} {'1st Res':>8} {'Spearman':>8} {'G5@70':>6} {'G10@70':>6} {'B5<50':>6} {'Cost/1K':>8}")
    print("-" * 100)
    for i, m in enumerate(by_latency, 1):
        cost_per_1k = m['cost_per_pair_usd'] * 50 * 1000
        print(f"{i:<5} {m['model']:<40} {m['avg_first_result_ms']:>6.0f}ms {m['rank_correlation']:>8.4f} {m['good5_70']:>6.2f} {m['good10_70']:>6.2f} {m['bad5_50']:>6.2f} ${cost_per_1k:>6.2f}")

    # Among top N, rank by cost
    by_cost = sorted(top_corr, key=lambda x: x["cost_per_pair_usd"])

    print(f"\n>>> TOP {args.top_n} - RANKED BY COST:")
    print(f"{'Rank':<5} {'Model':<40} {'Cost/1K':>8} {'Spearman':>8} {'G5@70':>6} {'G10@70':>6} {'B5<50':>6} {'1st Res':>8}")
    print("-" * 100)
    for i, m in enumerate(by_cost, 1):
        cost_per_1k = m['cost_per_pair_usd'] * 50 * 1000
        print(f"{i:<5} {m['model']:<40} ${cost_per_1k:>6.2f} {m['rank_correlation']:>8.4f} {m['good5_70']:>6.2f} {m['good10_70']:>6.2f} {m['bad5_50']:>6.2f} {m['avg_first_result_ms']:>6.0f}ms")

    # Save results
    output = {
        "all_models": model_metrics,
        "top_by_rank_correlation": top_corr,
        "top_by_latency": by_latency,
        "top_by_cost": by_cost,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

"""Analyze model scores against multiple reference models.

Computes rank correlation (Spearman's rho) per query for each candidate model
against each reference model (GPT-4.1, gpt-4.1-mini, gpt-4o-mini, gemma-3-27b, mistral-small).

Writes data/analysis_multi_ref.json
"""

import json
from pathlib import Path
from statistics import mean

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Score files
SCORE_FILES = {
    "gpt-4.1": DATA_DIR / "scores_azure_oai_gpt-4.1.json",
    "gpt-4.1-mini": DATA_DIR / "scores_azure_oai_gpt-4.1-mini.json",
    "gpt-4o-mini": DATA_DIR / "scores_azure_oai_gpt-4o-mini.json",
}

OPENROUTER_SCORES_PATH = DATA_DIR / "scores_openrouter.json"
OPENROUTER_COST_PATH = DATA_DIR / "cost_openrouter.json"
RETRIEVAL_RESULTS_PATH = DATA_DIR / "retrieval_results.json"
OUTPUT_PATH = DATA_DIR / "analysis_multi_ref.json"

# Difficulty categories: map difficulty level (1-5) to category name
DIFFICULTY_CATEGORIES = {
    1: "easy",      # Very Easy
    2: "easy",      # Easy
    3: "medium",    # Medium
    4: "hard",      # Hard
    5: "very_hard", # Very Hard
}

# Reference models we can compare against
REFERENCE_MODELS = [
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o-mini",
    "google/gemma-3-27b-it",
    "mistralai/mistral-small-3.1-24b-instruct",
    "meta-llama/llama-3.1-8b-instruct",
    "openai/gpt-oss-120b",
    "deepseek/deepseek-r1-distill-llama-70b",
    "google/gemma-3-12b-it",
    "inception/mercury",
]


def get_ranks(values: list[float]) -> list[float]:
    """Convert values to ranks (1-based, higher value = lower rank number)."""
    indexed = [(v, i) for i, v in enumerate(values)]
    indexed.sort(key=lambda x: -x[0])
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
    """Count overlap of top-k items."""
    if len(model_scores) < k or len(ref_scores) < k:
        return 0

    indexed_model = sorted(enumerate(model_scores), key=lambda x: -x[1])
    indexed_ref = sorted(enumerate(ref_scores), key=lambda x: -x[1])

    model_top_k = set(i for i, _ in indexed_model[:k])
    ref_top_k = set(i for i, _ in indexed_ref[:k])

    return len(model_top_k & ref_top_k)


def good_picks(model_scores: list[float], ref_scores: list[float], top_k: int, threshold: int) -> int:
    """Count model's top-k items where ref score >= threshold."""
    if len(model_scores) < top_k:
        return 0

    indexed_model = sorted(enumerate(model_scores), key=lambda x: -x[1])
    model_top_k_indices = [i for i, _ in indexed_model[:top_k]]

    return sum(1 for idx in model_top_k_indices if ref_scores[idx] >= threshold)


def bad_picks(model_scores: list[float], ref_scores: list[float], top_k: int, threshold: int = 50) -> int:
    """Count model's top-k items where ref score < threshold."""
    if len(model_scores) < top_k:
        return 0

    indexed_model = sorted(enumerate(model_scores), key=lambda x: -x[1])
    model_top_k_indices = [i for i, _ in indexed_model[:top_k]]

    return sum(1 for idx in model_top_k_indices if ref_scores[idx] < threshold)


def high_score_bad_picks(model_scores: list[float], ref_scores: list[float],
                         model_threshold: int = 75, ref_threshold: int = 50) -> int:
    """Count items where model score >= model_threshold but ref score < ref_threshold.

    This measures how often a model gives a high score (>=75) to items that the
    reference model considers bad (<50).
    """
    return sum(1 for ms, rs in zip(model_scores, ref_scores)
               if ms >= model_threshold and rs < ref_threshold)


def load_query_difficulty() -> dict[str, str]:
    """Load difficulty category for each query from retrieval_results.json.

    Returns {query: category} where category is one of: easy, medium, hard, very_hard
    """
    if not RETRIEVAL_RESULTS_PATH.exists():
        return {}

    with open(RETRIEVAL_RESULTS_PATH) as f:
        data = json.load(f)

    result = {}
    for q in data:
        query = q.get("query", "")
        difficulty = q.get("difficulty", 3)  # Default to medium
        category = DIFFICULTY_CATEGORIES.get(difficulty, "medium")
        result[query] = category
    return result


def load_scores_by_query(path: Path) -> dict[str, dict[str, int]]:
    """Load scores from a file, returning {query: {url: score}}."""
    if not path.exists():
        return {}

    with open(path) as f:
        data = json.load(f)

    result = {}
    for q in data:
        query = q["query"]
        result[query] = {}
        for item in q.get("items", []):
            url = item.get("url", "")
            score = item.get("score", -1)
            if score >= 0:
                result[query][url] = score
    return result


def load_openrouter_scores() -> dict[str, dict[str, dict[str, tuple[int, int]]]]:
    """Load OpenRouter scores: {model: {query: {url: (score, latency)}}}."""
    if not OPENROUTER_SCORES_PATH.exists():
        return {}

    # Try to load JSON, handling partial/corrupted files
    try:
        with open(OPENROUTER_SCORES_PATH) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  Warning: JSON parsing error at line {e.lineno}. Attempting partial recovery...")
        # Try to read and parse up to the error
        with open(OPENROUTER_SCORES_PATH) as f:
            content = f.read()
        # Find the last complete JSON array element
        last_bracket = content.rfind('}')
        while last_bracket > 0:
            try:
                # Try to find a valid JSON ending
                test_content = content[:last_bracket+1]
                # Count brackets to find valid end
                open_brackets = test_content.count('[') - test_content.count(']')
                if open_brackets > 0:
                    test_content += ']' * open_brackets
                data = json.loads(test_content)
                print(f"  Recovered {len(data)} queries from partial file")
                break
            except json.JSONDecodeError:
                last_bracket = content.rfind('}', 0, last_bracket)
        else:
            print("  Could not recover data from corrupted file")
            return {}

    result = {}
    for q in data:
        query = q["query"]
        for item in q.get("items", []):
            url = item.get("url", "")
            for ms in item.get("model_scores", []):
                model = ms.get("model", "")
                score = ms.get("score", -1)
                latency = ms.get("response_time_ms", 0)

                if score >= 0 and model:
                    if model not in result:
                        result[model] = {}
                    if query not in result[model]:
                        result[model][query] = {}
                    result[model][query][url] = (score, latency)

    return result


def load_vector_db_scores() -> dict[str, dict[str, tuple[int, int]]]:
    """Load vector database scores from retrieval_results.json.

    Converts search_score (0-1 range) to 0-100 scale for comparison.
    Returns {query: {url: (score, latency)}} where latency is 0 (instant).
    """
    if not RETRIEVAL_RESULTS_PATH.exists():
        return {}

    with open(RETRIEVAL_RESULTS_PATH) as f:
        data = json.load(f)

    result = {}
    for q in data:
        query = q.get("query", "")
        if not query:
            continue

        result[query] = {}
        for item in q.get("items", []):
            url = item.get("url", "")
            search_score = item.get("search_score", 0)
            # Convert search_score (typically 0.5-0.7 range) to 0-100 scale
            # Use a linear mapping that expands the typical range
            # Score of 0.5 -> 0, Score of 0.7 -> 100, clamped
            normalized = int(max(0, min(100, (search_score - 0.5) * 500)))
            result[query][url] = (normalized, 0)  # 0ms latency (instant)

    return result


def load_cost_data() -> dict[str, dict]:
    """Load cost data for all models."""
    cost_lookup = {}

    # OpenRouter costs
    if OPENROUTER_COST_PATH.exists():
        with open(OPENROUTER_COST_PATH) as f:
            for entry in json.load(f):
                model = entry.get("model", "")
                cost_lookup[model] = {
                    "total_cost_usd": entry.get("total_cost_usd", 0),
                    "cost_per_pair_usd": entry.get("cost_per_pair_usd", 0),
                    "avg_response_time_ms": entry.get("avg_response_time_ms", 0),
                }

    # Azure model costs
    azure_costs = {
        "gpt-4.1": DATA_DIR / "cost_azure_oai_gpt-4.1.json",
        "gpt-4.1-mini": DATA_DIR / "cost_azure_oai_gpt-4.1-mini.json",
        "gpt-4o-mini": DATA_DIR / "cost_azure_oai_gpt-4o-mini.json",
    }

    for model, path in azure_costs.items():
        if path.exists():
            with open(path) as f:
                info = json.load(f)
            cost_lookup[f"azure/{model}"] = {
                "total_cost_usd": info.get("total_cost_usd", 0),
                "cost_per_pair_usd": info.get("cost_per_pair_usd", 0),
                "avg_response_time_ms": info.get("avg_response_time_ms", 0),
            }

    # Vector DB has zero cost
    cost_lookup["vector-db"] = {
        "total_cost_usd": 0,
        "cost_per_pair_usd": 0,
        "avg_response_time_ms": 0,
    }

    return cost_lookup


def compute_metrics_vs_reference(
    candidate_scores: dict[str, dict[str, tuple[int, int]]],  # {query: {url: (score, latency)}}
    ref_scores: dict[str, dict[str, int]],  # {query: {url: score}}
    query_difficulty: dict[str, str] | None = None,  # {query: category}
    difficulty_filter: str | None = None,  # Filter to specific category (easy, medium, hard, very_hard)
) -> dict | None:
    """Compute metrics for a candidate model against a reference.

    If difficulty_filter is provided, only queries matching that category are included.
    """
    query_correlations = []
    top5_overlaps = []
    top10_overlaps = []
    good5_70 = []
    good10_70 = []
    bad5_50 = []
    bad10_50 = []
    high_bad_75_50 = []  # Items with model score >=75 but ref score <50
    first_result_latencies = []
    total_pairs = 0

    for query, ref_items in ref_scores.items():
        # Filter by difficulty if specified
        if difficulty_filter and query_difficulty:
            query_cat = query_difficulty.get(query, "medium")
            if query_cat != difficulty_filter:
                continue

        if query not in candidate_scores:
            continue

        cand_items = candidate_scores[query]

        # Find common URLs
        common_urls = set(ref_items.keys()) & set(cand_items.keys())
        if len(common_urls) < 3:
            continue

        urls = list(common_urls)
        cand_vals = [cand_items[u][0] for u in urls]
        ref_vals = [ref_items[u] for u in urls]
        latencies = [cand_items[u][1] for u in urls]

        corr = spearman_correlation(cand_vals, ref_vals)
        query_correlations.append(corr)

        if len(urls) >= 5:
            top5_overlaps.append(top_k_overlap(cand_vals, ref_vals, 5))
        if len(urls) >= 10:
            top10_overlaps.append(top_k_overlap(cand_vals, ref_vals, 10))
            good5_70.append(good_picks(cand_vals, ref_vals, 5, 70))
            good10_70.append(good_picks(cand_vals, ref_vals, 10, 70))
            bad5_50.append(bad_picks(cand_vals, ref_vals, 5, 50))
            bad10_50.append(bad_picks(cand_vals, ref_vals, 10, 50))

        # Count items where model gives high score but ref gives low score
        high_bad_75_50.append(high_score_bad_picks(cand_vals, ref_vals, 75, 50))

        if latencies:
            first_result_latencies.append(min(latencies))

        total_pairs += len(urls)

    if not query_correlations:
        return None

    return {
        "num_queries": len(query_correlations),
        "num_pairs": total_pairs,
        "rank_correlation": round(mean(query_correlations), 4),
        "top5_overlap": round(mean(top5_overlaps), 2) if top5_overlaps else 0,
        "top10_overlap": round(mean(top10_overlaps), 2) if top10_overlaps else 0,
        "good5_70": round(mean(good5_70), 2) if good5_70 else 0,
        "good10_70": round(mean(good10_70), 2) if good10_70 else 0,
        "bad5_50": round(mean(bad5_50), 2) if bad5_50 else 0,
        "bad10_50": round(mean(bad10_50), 2) if bad10_50 else 0,
        "high_bad_75_50": round(mean(high_bad_75_50), 2) if high_bad_75_50 else 0,
        "avg_first_result_ms": round(mean(first_result_latencies), 1) if first_result_latencies else 0,
    }


def main():
    print("Loading score files...")

    # Load all Azure scores
    azure_scores = {}
    for name, path in SCORE_FILES.items():
        scores = load_scores_by_query(path)
        if scores:
            azure_scores[name] = scores
            print(f"  {name}: {sum(len(v) for v in scores.values())} scores across {len(scores)} queries")

    # Load OpenRouter scores
    openrouter_scores = load_openrouter_scores()
    print(f"  OpenRouter: {len(openrouter_scores)} models")

    # Load cost data
    cost_data = load_cost_data()

    # Load query difficulty mapping
    query_difficulty = load_query_difficulty()
    print(f"  Query difficulty: {len(query_difficulty)} queries mapped")

    # Build candidate model scores in unified format: {model: {query: {url: (score, latency)}}}
    all_candidate_scores = {}

    # Add Azure models as candidates
    for name, path in SCORE_FILES.items():
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)

        model_key = f"azure/{name}"
        all_candidate_scores[model_key] = {}
        for q in data:
            query = q["query"]
            all_candidate_scores[model_key][query] = {}
            for item in q.get("items", []):
                url = item.get("url", "")
                score = item.get("score", -1)
                latency = item.get("response_time_ms", 0)
                if score >= 0:
                    all_candidate_scores[model_key][query][url] = (score, latency)

    # Add OpenRouter models
    all_candidate_scores.update(openrouter_scores)

    # Add vector database as a "model"
    vector_db_scores = load_vector_db_scores()
    if vector_db_scores:
        all_candidate_scores["vector-db"] = vector_db_scores
        print(f"  Vector DB: {sum(len(v) for v in vector_db_scores.values())} scores across {len(vector_db_scores)} queries")

    print(f"\nTotal candidate models: {len(all_candidate_scores)}")

    # Build reference scores dict
    all_ref_scores = {}

    # Azure reference models
    for name, scores in azure_scores.items():
        all_ref_scores[name] = scores

    # OpenRouter reference models
    openrouter_refs = [
        "google/gemma-3-27b-it",
        "mistralai/mistral-small-3.1-24b-instruct",
        "meta-llama/llama-3.1-8b-instruct",
        "openai/gpt-oss-120b",
        "deepseek/deepseek-r1-distill-llama-70b",
        "google/gemma-3-12b-it",
        "inception/mercury",
    ]
    for ref_model in openrouter_refs:
        if ref_model in openrouter_scores:
            # Convert to {query: {url: score}} format
            ref_data = {}
            for query, items in openrouter_scores[ref_model].items():
                ref_data[query] = {url: score for url, (score, _) in items.items()}
            all_ref_scores[ref_model] = ref_data

    print(f"Reference models: {list(all_ref_scores.keys())}")

    # Difficulty categories to compute metrics for
    difficulty_categories = ["easy", "medium", "hard", "very_hard"]

    # Compute metrics for each candidate vs each reference
    results = {
        "reference_models": list(all_ref_scores.keys()),
        "candidate_models": [],
        "difficulty_categories": difficulty_categories,
        "metrics_by_reference": {},
        "metrics_by_difficulty": {},  # {difficulty: {ref: [metrics]}}
    }

    # Initialize difficulty structure
    for diff in difficulty_categories:
        results["metrics_by_difficulty"][diff] = {}

    for ref_name, ref_scores in all_ref_scores.items():
        print(f"\nComputing metrics vs {ref_name}...")
        results["metrics_by_reference"][ref_name] = []

        # Initialize per-difficulty for this reference
        for diff in difficulty_categories:
            results["metrics_by_difficulty"][diff][ref_name] = []

        for cand_name, cand_scores in all_candidate_scores.items():
            # Skip self-comparison
            if cand_name == f"azure/{ref_name}" or cand_name == ref_name:
                continue

            # Compute overall metrics
            metrics = compute_metrics_vs_reference(cand_scores, ref_scores)
            if metrics is None:
                continue

            # Add cost info
            cost_info = cost_data.get(cand_name, {})
            metrics["model"] = cand_name
            metrics["cost_per_pair_usd"] = cost_info.get("cost_per_pair_usd", 0)
            metrics["total_cost_usd"] = cost_info.get("total_cost_usd", 0)

            results["metrics_by_reference"][ref_name].append(metrics)

            # Compute per-difficulty metrics
            for diff in difficulty_categories:
                diff_metrics = compute_metrics_vs_reference(
                    cand_scores, ref_scores,
                    query_difficulty=query_difficulty,
                    difficulty_filter=diff
                )
                if diff_metrics:
                    diff_metrics["model"] = cand_name
                    diff_metrics["cost_per_pair_usd"] = cost_info.get("cost_per_pair_usd", 0)
                    diff_metrics["total_cost_usd"] = cost_info.get("total_cost_usd", 0)
                    results["metrics_by_difficulty"][diff][ref_name].append(diff_metrics)

        # Sort by correlation descending
        results["metrics_by_reference"][ref_name].sort(
            key=lambda x: x["rank_correlation"], reverse=True
        )

        # Sort per-difficulty by correlation
        for diff in difficulty_categories:
            results["metrics_by_difficulty"][diff][ref_name].sort(
                key=lambda x: x["rank_correlation"], reverse=True
            )

        print(f"  {len(results['metrics_by_reference'][ref_name])} candidate models compared")

    # Get unique candidate list
    all_candidates = set()
    for ref_metrics in results["metrics_by_reference"].values():
        for m in ref_metrics:
            all_candidates.add(m["model"])
    results["candidate_models"] = sorted(all_candidates)

    # Save results
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {OUTPUT_PATH}")

    # Print summary
    print("\n" + "=" * 80)
    print("TOP 5 BY CORRELATION (vs each reference)")
    print("=" * 80)

    for ref_name in all_ref_scores.keys():
        print(f"\n>>> vs {ref_name}:")
        for m in results["metrics_by_reference"][ref_name][:5]:
            cost_1k = m["cost_per_pair_usd"] * 50 * 1000
            print(f"  {m['model']:<45} ρ={m['rank_correlation']:.3f}  ${cost_1k:.2f}/1K")

    # Print summary by difficulty
    print("\n" + "=" * 80)
    print("CORRELATION BY DIFFICULTY (vs gpt-4.1)")
    print("=" * 80)
    if "gpt-4.1" in all_ref_scores:
        for diff in difficulty_categories:
            print(f"\n>>> {diff.upper()}:")
            for m in results["metrics_by_difficulty"][diff].get("gpt-4.1", [])[:3]:
                print(f"  {m['model']:<45} ρ={m['rank_correlation']:.3f}  ({m['num_queries']} queries)")


if __name__ == "__main__":
    main()

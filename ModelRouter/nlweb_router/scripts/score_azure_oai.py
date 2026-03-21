"""Score every (query, item) pair using Azure OAI models.

Reads   data/retrieval_results.json
Writes  data/scores_azure_oai_{model}.json
        data/cost_azure_oai_{model}.json

Features:
- Adaptive parallelism with rate limit backoff
- Retries failed items (doesn't record errors)
- Slowly increases rate when successful
- Saves progress after each query batch
- Supports multiple models: gpt-4.1, gpt-4.1-mini, gpt-4o-mini
"""

import argparse
import json
import os
import sys
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from openai import AzureOpenAI

from json_utils import trim_json

# Unbuffer stdout for real-time output
sys.stdout.reconfigure(line_buffering=True)

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

DATA_DIR     = Path(__file__).resolve().parents[1] / "data"
RESULTS_PATH = DATA_DIR / "retrieval_results.json"

AOAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AOAI_KEY      = os.environ["AZURE_OPENAI_API_KEY"]
AOAI_API_VER  = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# Model configurations: deployment name -> (prompt_cost, completion_cost) per 1M tokens
MODEL_CONFIGS = {
    "gpt-4.1": {
        "prompt_cost": 2.00 / 1_000_000,
        "completion_cost": 8.00 / 1_000_000,
    },
    "gpt-4.1-mini": {
        "prompt_cost": 0.40 / 1_000_000,
        "completion_cost": 1.60 / 1_000_000,
    },
    "gpt-4o-mini": {
        "prompt_cost": 0.15 / 1_000_000,
        "completion_cost": 0.60 / 1_000_000,
    },
}

DEFAULT_MODEL = "gpt-4.1"

# These will be set in main() based on selected model
MODEL = None
PROMPT_COST = None
COMPLETION_COST = None
OUT_PATH = None
COST_PATH = None

MAX_RETRIES = 5
TIMEOUT_SECONDS = 10.0

# Adaptive rate control
MIN_PARALLEL = 5
MAX_PARALLEL = 100
DEFAULT_PARALLEL = 50

# ── NLWeb ranking prompt (must match ranking.py exactly) ─────────────────────
# This is the default RANKING_PROMPT from NLWeb core/ranking.py
RANKING_PROMPT = """\
Assign a score between 0 and 100 to the following item \
based on how relevant it is to the user's question. \
Use your knowledge from other sources, about the item, to make a judgement.
If the score is above 50, provide a short description of the item \
highlighting the relevance to the user's question, without mentioning the user's question.
Provide an explanation of the relevance of the item to the user's question, \
without mentioning the user's question or the score or explicitly mentioning the term relevance.
If the score is below 75, in the description, include the reason why it is still relevant.
The user's question is: {query}. The item's description is {description}

Respond with a JSON object containing:
- "score": integer between 0 and 100
- "description": short description of the item

Output only the JSON object, no other text.
"""


class RateController:
    """Adaptive rate controller that backs off on rate limits."""

    def __init__(self, initial_parallel: int):
        self.parallel = initial_parallel
        self.lock = threading.Lock()
        self.consecutive_successes = 0
        self.last_rate_change = time.time()

    def on_rate_limit(self):
        """Called when we hit a rate limit - reduce parallelism."""
        with self.lock:
            old = self.parallel
            self.parallel = max(MIN_PARALLEL, self.parallel // 2)
            self.consecutive_successes = 0
            self.last_rate_change = time.time()
            if old != self.parallel:
                print(f"  [RATE] Reducing parallelism: {old} -> {self.parallel}")

    def on_success(self):
        """Called on successful request - maybe increase rate."""
        with self.lock:
            self.consecutive_successes += 1
            # Increase rate slowly after sustained success
            if self.consecutive_successes >= 50 and time.time() - self.last_rate_change > 30:
                old = self.parallel
                self.parallel = min(MAX_PARALLEL, self.parallel + 5)
                self.consecutive_successes = 0
                self.last_rate_change = time.time()
                if old != self.parallel:
                    print(f"  [RATE] Increasing parallelism: {old} -> {self.parallel}")

    def get_parallel(self):
        with self.lock:
            return self.parallel


def score_one(client: AzureOpenAI, query: str, item: dict, idx: int, rate_ctrl: RateController) -> dict | None:
    """Score a single item. Returns result dict or None if should retry."""
    item_name = item.get("name", "")[:30]
    # Apply trim_json to match NLWeb behavior - reduces token count significantly
    raw_desc = item.get("schema_json", item.get("name", ""))
    trimmed_desc = trim_json(raw_desc)
    # Convert back to string if trim_json returned a dict
    if isinstance(trimmed_desc, dict):
        desc = json.dumps(trimmed_desc)
    else:
        desc = trimmed_desc
    prompt = RANKING_PROMPT.format(query=query, description=desc)

    t0 = time.time()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
            timeout=TIMEOUT_SECONDS,
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        content = resp.choices[0].message.content
        usage = resp.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        try:
            # Strip markdown code fences if present (gpt-4.1-mini wraps in ```json)
            clean_content = content.strip()
            if clean_content.startswith("```"):
                # Remove opening fence (```json or ```)
                first_newline = clean_content.find("\n")
                if first_newline != -1:
                    clean_content = clean_content[first_newline + 1:]
                # Remove closing fence
                if clean_content.endswith("```"):
                    clean_content = clean_content[:-3].strip()
            parsed = json.loads(clean_content)
            score = parsed.get("score", -1)
        except json.JSONDecodeError:
            parsed = {"score": -1, "description": content[:100]}
            score = -1

        parsed["response_time_ms"] = elapsed_ms
        parsed["prompt_tokens"] = prompt_tokens
        parsed["completion_tokens"] = completion_tokens
        parsed["total_tokens"] = prompt_tokens + completion_tokens

        rate_ctrl.on_success()
        print(f"  [{idx}] OK score={score} {elapsed_ms}ms item='{item_name}...'")
        return {
            "url": item["url"],
            "name": item["name"],
            "idx": idx,
            **parsed,
        }

    except Exception as e:
        error_msg = str(e)
        elapsed_ms = int((time.time() - t0) * 1000)

        # Check for rate limit error
        if "429" in error_msg or "rate" in error_msg.lower() or "too many" in error_msg.lower():
            rate_ctrl.on_rate_limit()
            print(f"  [{idx}] RATE_LIMIT '{item_name}...' - will retry")
            return None  # Signal to retry

        # Other errors - also retry
        print(f"  [{idx}] ERR '{item_name}...' {error_msg[:50]} - will retry")
        return None


def score_items_with_retry(client: AzureOpenAI, query: str, items: list, rate_ctrl: RateController) -> list:
    """Score all items, retrying failures until all succeed."""
    results = [None] * len(items)
    pending = list(range(len(items)))  # Indices still to process
    attempt = 0

    while pending and attempt < MAX_RETRIES:
        attempt += 1
        if attempt > 1:
            wait_time = min(30, 2 ** attempt)
            print(f"  Retry attempt {attempt}, waiting {wait_time}s, {len(pending)} items remaining...")
            time.sleep(wait_time)

        still_pending = []
        current_parallel = rate_ctrl.get_parallel()

        with ThreadPoolExecutor(max_workers=current_parallel) as executor:
            futures = {}
            for i in pending:
                future = executor.submit(score_one, client, query, items[i], i, rate_ctrl)
                futures[future] = i

            for future in as_completed(futures):
                i = futures[future]
                try:
                    result = future.result()
                    if result is None:
                        # Need to retry this one
                        still_pending.append(i)
                    else:
                        results[i] = result
                except Exception as e:
                    print(f"  [{i}] EXCEPTION: {str(e)[:50]} - will retry")
                    still_pending.append(i)

        pending = still_pending

        if pending:
            print(f"  {len(pending)} items still pending after attempt {attempt}")

    # If we still have pending items after all retries, create error entries
    for i in pending:
        print(f"  [{i}] GIVING UP after {MAX_RETRIES} attempts")
        results[i] = {
            "url": items[i]["url"],
            "name": items[i]["name"],
            "idx": i,
            "score": -1,
            "description": "ERROR: Max retries exceeded",
            "response_time_ms": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "error": True,
        }

    return results


def save_progress(all_scores, total_prompt_tokens, total_completion_tokens, total_time_ms, total_pairs, done):
    """Save current progress to disk."""
    actual_cost = (total_prompt_tokens * PROMPT_COST +
                   total_completion_tokens * COMPLETION_COST)

    cost_data = {
        "model": MODEL,
        "total_pairs": done,
        "total_pairs_target": total_pairs,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "total_cost_usd": actual_cost,
        "cost_per_pair_usd": actual_cost / done if done else 0,
        "avg_response_time_ms": total_time_ms / done if done else 0,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(all_scores, f, indent=2)
    with open(COST_PATH, "w") as f:
        json.dump(cost_data, f, indent=2)


def main():
    global MODEL, PROMPT_COST, COMPLETION_COST, OUT_PATH, COST_PATH

    parser = argparse.ArgumentParser(description="Score query-item pairs with Azure OpenAI")
    parser.add_argument("-m", "--model", type=str, default=DEFAULT_MODEL,
                        choices=list(MODEL_CONFIGS.keys()),
                        help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("-p", "--parallel", type=int, default=DEFAULT_PARALLEL,
                        help=f"Initial parallel API calls (default: {DEFAULT_PARALLEL})")
    args = parser.parse_args()

    # Set global model configuration
    MODEL = args.model
    PROMPT_COST = MODEL_CONFIGS[MODEL]["prompt_cost"]
    COMPLETION_COST = MODEL_CONFIGS[MODEL]["completion_cost"]
    OUT_PATH = DATA_DIR / f"scores_azure_oai_{MODEL}.json"
    COST_PATH = DATA_DIR / f"cost_azure_oai_{MODEL}.json"

    if not RESULTS_PATH.exists():
        print(f"ERROR: No retrieval results at {RESULTS_PATH}")
        return

    print(f"Loading {RESULTS_PATH}...")
    with open(RESULTS_PATH) as f:
        queries = json.load(f)

    total_pairs = sum(len(q["items"]) for q in queries)
    print(f"Found {len(queries)} queries, {total_pairs} items")
    print(f"Model: {MODEL}, Endpoint: {AOAI_ENDPOINT}")
    print(f"Initial parallel: {args.parallel}, Min: {MIN_PARALLEL}, Max: {MAX_PARALLEL}")
    print(f"Timeout: {TIMEOUT_SECONDS}s, Max retries: {MAX_RETRIES}")

    # Initialize rate controller
    rate_ctrl = RateController(args.parallel)

    # Load existing progress if any
    all_scores = []
    done = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_time_ms = 0
    errors = 0
    start_query_idx = 0

    if OUT_PATH.exists():
        print(f"Loading existing progress from {OUT_PATH}...")
        with open(OUT_PATH) as f:
            all_scores = json.load(f)
        start_query_idx = len(all_scores)
        # Recalculate stats from existing data
        for qscore in all_scores:
            for item in qscore.get("items", []):
                done += 1
                total_prompt_tokens += item.get("prompt_tokens", 0)
                total_completion_tokens += item.get("completion_tokens", 0)
                total_time_ms += item.get("response_time_ms", 0)
                if item.get("error"):
                    errors += 1
        print(f"Resuming from query {start_query_idx + 1}, already have {done} pairs scored")

    if start_query_idx >= len(queries):
        print("All queries already scored!")
        return

    print()

    client = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_KEY,
        api_version=AOAI_API_VER,
    )

    for qi, qobj in enumerate(queries):
        # Skip already processed queries
        if qi < start_query_idx:
            continue
        query = qobj["query"]
        site = qobj["site"]
        items = qobj["items"]

        current_parallel = rate_ctrl.get_parallel()
        print(f"\n=== Query {qi+1}/{len(queries)}: [{site}] {query[:50]}... ({len(items)} items, parallel={current_parallel}) ===")

        # Process items with retry logic
        item_results = score_items_with_retry(client, query, items, rate_ctrl)

        # Update stats
        for r in item_results:
            if r:
                done += 1
                total_prompt_tokens += r.get("prompt_tokens", 0)
                total_completion_tokens += r.get("completion_tokens", 0)
                total_time_ms += r.get("response_time_ms", 0)
                if r.get("error"):
                    errors += 1
                # Remove idx field
                if "idx" in r:
                    del r["idx"]

        all_scores.append({
            "site": site,
            "query": query,
            "query_length": len(query),
            "model": MODEL,
            "items": item_results,
        })

        # Save after each query
        save_progress(all_scores, total_prompt_tokens, total_completion_tokens, total_time_ms, total_pairs, done)

        actual_cost = (total_prompt_tokens * PROMPT_COST +
                       total_completion_tokens * COMPLETION_COST)
        print(f"  -> Saved. Progress: {done}/{total_pairs}, ${actual_cost:.4f}, {errors} errors, parallel={rate_ctrl.get_parallel()}")

    # Final summary
    actual_cost = (total_prompt_tokens * PROMPT_COST +
                   total_completion_tokens * COMPLETION_COST)

    print(f"\n{'='*70}")
    print(f"DONE! {done}/{total_pairs} pairs, {errors} errors")
    print(f"Tokens: {total_prompt_tokens} + {total_completion_tokens} = {total_prompt_tokens + total_completion_tokens}")
    print(f"Cost: ${actual_cost:.4f} (${actual_cost/done:.6f}/pair)" if done else "Cost: N/A")
    print(f"Avg latency: {total_time_ms/done:.0f}ms" if done else "")
    print(f"Output: {OUT_PATH}")


if __name__ == "__main__":
    main()

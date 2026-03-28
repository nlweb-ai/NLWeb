"""Score every (query, item) pair using each OpenRouter model.

Uses asyncio for efficient concurrent API calls - can maintain 1000+ requests in flight
with minimal memory overhead compared to threads.

Reads   data/retrieval_results.json
        data/cheapest_models.json
Writes  data/scores_openrouter.json       (all models, all queries)
        data/cost_openrouter.json         (per-model cost rollup)

Features:
- Asyncio-based concurrency for efficient parallel requests
- Maintains MAX_PARALLEL concurrent requests at all times
- Adaptive parallelism with rate limit backoff
- Retries failed items with exponential backoff
- Saves progress periodically
- Skips already-completed (query, item, model) tuples on restart
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import AsyncOpenAI, APITimeoutError

from json_utils import trim_json

# Unbuffer stdout for real-time output
sys.stdout.reconfigure(line_buffering=True)

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

DATA_DIR      = Path(__file__).resolve().parents[1] / "data"
RESULTS_PATH  = DATA_DIR / "retrieval_results.json"
MODELS_PATH   = DATA_DIR / "cheapest_models.json"
OUT_PATH      = DATA_DIR / "scores_openrouter.json"
COST_PATH     = DATA_DIR / "cost_openrouter.json"

OPENROUTER_KEY = os.environ["OPENROUTER_API_KEY"]

# ── Config ───────────────────────────────────────────────────────────────────
MAX_RETRIES = 5
TIMEOUT_SECONDS = 10.0

# Adaptive rate control
MIN_PARALLEL = 5
MAX_PARALLEL = 50
DEFAULT_PARALLEL = 50

# Save interval (seconds)
SAVE_INTERVAL = 30

# Models known to be unavailable or problematic
SKIP_MODELS = {
    "nousresearch/deephermes-3-mistral-24b-preview",  # 404
    "nvidia/nemotron-nano-9b-v2",   # returns empty content
    "arcee-ai/trinity-mini",        # unparseable responses
}

# ── NLWeb ranking prompt (must match ranking.py exactly) ─────────────────────
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


@dataclass
class WorkItem:
    """Represents a single (query, item, model) scoring task."""
    qi: int
    ii: int
    model_idx: int
    model_id: str
    query: str
    item: dict
    site: str
    attempt: int = 1


class RateController:
    """Adaptive rate controller that backs off on rate limits."""

    def __init__(self, initial_parallel: int):
        self.parallel = initial_parallel
        self.consecutive_successes = 0
        self.last_rate_change = time.time()
        self._lock = asyncio.Lock()

    async def on_rate_limit(self):
        """Called when we hit a rate limit - reduce parallelism."""
        async with self._lock:
            old = self.parallel
            self.parallel = max(MIN_PARALLEL, self.parallel // 2)
            self.consecutive_successes = 0
            self.last_rate_change = time.time()
            if old != self.parallel:
                print(f"  [RATE] Reducing parallelism: {old} -> {self.parallel}")

    async def on_success(self):
        """Called on successful request - maybe increase rate."""
        async with self._lock:
            self.consecutive_successes += 1
            # Increase rate slowly after sustained success
            if self.consecutive_successes >= 100 and time.time() - self.last_rate_change > 30:
                old = self.parallel
                self.parallel = min(MAX_PARALLEL, self.parallel + 20)
                self.consecutive_successes = 0
                self.last_rate_change = time.time()
                if old != self.parallel:
                    print(f"  [RATE] Increasing parallelism: {old} -> {self.parallel}")

    def get_parallel(self):
        return self.parallel


def parse_json_response(content: str) -> dict:
    """Parse JSON from model response, stripping markdown fences if present."""
    text = content.strip()
    m = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


async def score_one(client: AsyncOpenAI, work: WorkItem, rate_ctrl: RateController) -> tuple[WorkItem, dict | None]:
    """Score a single work item. Returns (work_item, result) where result is None if should retry.

    Timeouts return a valid result with score=0 and latency=5000ms (no retry).
    """
    item_name = work.item.get("name", "")[:25]
    # Apply trim_json to match NLWeb behavior
    raw_desc = work.item.get("schema_json", work.item.get("name", ""))
    trimmed_desc = trim_json(raw_desc)
    if isinstance(trimmed_desc, dict):
        desc = json.dumps(trimmed_desc)
    else:
        desc = trimmed_desc
    prompt = RANKING_PROMPT.format(query=work.query, description=desc)

    t0 = time.time()
    try:
        resp = await client.chat.completions.create(
            model=work.model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=512,
            timeout=TIMEOUT_SECONDS,
            extra_body={
                "provider": {
                    "sort": "latency",
                }
            },
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        content = resp.choices[0].message.content or ""
        usage = resp.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0

        try:
            parsed = parse_json_response(content)
            score = parsed.get("score", -1)
        except (json.JSONDecodeError, Exception):
            parsed = {"score": -1, "description": content[:100]}
            score = -1

        parsed["response_time_ms"] = elapsed_ms
        parsed["prompt_tokens"] = prompt_tokens
        parsed["completion_tokens"] = completion_tokens
        parsed["total_tokens"] = prompt_tokens + completion_tokens

        await rate_ctrl.on_success()
        model_short = work.model_id.split("/")[-1][:20]
        print(f"  [Q{work.qi}I{work.ii}M{work.model_idx}] OK score={score:3d} {elapsed_ms:4d}ms {model_short} '{item_name}...'")

        return (work, {
            "model": work.model_id,
            "url": work.item["url"],
            "name": work.item["name"],
            **parsed,
        })

    except (asyncio.TimeoutError, APITimeoutError):
        # Timeout: return score=0, latency=5000ms, no retry
        model_short = work.model_id.split("/")[-1][:20]
        timeout_ms = int(TIMEOUT_SECONDS * 1000)
        print(f"  [Q{work.qi}I{work.ii}M{work.model_idx}] TIMEOUT {model_short} score=0 {timeout_ms}ms")
        return (work, {
            "model": work.model_id,
            "url": work.item["url"],
            "name": work.item["name"],
            "score": 0,
            "description": "TIMEOUT",
            "response_time_ms": timeout_ms,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "timeout": True,
        })

    except Exception as e:
        error_msg = str(e)
        elapsed_ms = int((time.time() - t0) * 1000)

        if "429" in error_msg or "rate" in error_msg.lower() or "too many" in error_msg.lower():
            await rate_ctrl.on_rate_limit()
            model_short = work.model_id.split("/")[-1][:20]
            print(f"  [Q{work.qi}I{work.ii}M{work.model_idx}] RATE_LIMIT {model_short} (attempt {work.attempt})")
            return (work, None)

        model_short = work.model_id.split("/")[-1][:20]
        print(f"  [Q{work.qi}I{work.ii}M{work.model_idx}] ERR {model_short}: {error_msg[:40]} (attempt {work.attempt})")
        return (work, None)


def save_progress(all_scores, model_stats):
    """Save current progress to disk."""
    with open(OUT_PATH, "w") as f:
        json.dump(all_scores, f, indent=2)

    cost_data = []
    for model_id, stats in model_stats.items():
        if stats["done"] == 0:
            continue
        cost_data.append({
            "model": model_id,
            "total_pairs": stats["done"],
            "total_prompt_tokens": stats["prompt_tokens"],
            "total_completion_tokens": stats["completion_tokens"],
            "total_tokens": stats["prompt_tokens"] + stats["completion_tokens"],
            "total_cost_usd": stats["cost"],
            "cost_per_pair_usd": stats["cost"] / stats["done"] if stats["done"] else 0,
            "avg_response_time_ms": stats["time_ms"] / stats["done"] if stats["done"] else 0,
            "errors": stats["errors"],
        })

    cost_data.sort(key=lambda x: x["total_cost_usd"])
    with open(COST_PATH, "w") as f:
        json.dump(cost_data, f, indent=2)


async def main():
    parser = argparse.ArgumentParser(description="Score query-item pairs with OpenRouter models")
    parser.add_argument("-p", "--parallel", type=int, default=DEFAULT_PARALLEL,
                        help=f"Initial parallel API calls (default: {DEFAULT_PARALLEL})")
    args = parser.parse_args()

    if not RESULTS_PATH.exists():
        print(f"ERROR: No retrieval results at {RESULTS_PATH}")
        return
    if not MODELS_PATH.exists():
        print(f"ERROR: No model list at {MODELS_PATH}")
        return

    print(f"Loading {RESULTS_PATH}...")
    with open(RESULTS_PATH) as f:
        queries = json.load(f)

    print(f"Loading {MODELS_PATH}...")
    with open(MODELS_PATH) as f:
        all_models = json.load(f)

    # Filter models
    models = []
    for m in all_models:
        mid = m["id"]
        if mid.endswith(":free"):
            print(f"  Skipping {mid} (free tier, rate-limited)")
            continue
        if mid in SKIP_MODELS:
            print(f"  Skipping {mid} (known unavailable)")
            continue
        models.append(m)

    total_queries = len(queries)
    total_items = sum(len(q["items"]) for q in queries)
    total_models = len(models)
    total_calls = total_items * total_models

    print(f"\nConfig:")
    print(f"  Queries: {total_queries}")
    print(f"  Items: {total_items}")
    print(f"  Models: {total_models}")
    print(f"  Total API calls needed: {total_calls}")
    print(f"  Initial parallel: {args.parallel}, Min: {MIN_PARALLEL}, Max: {MAX_PARALLEL}")
    print(f"  Timeout: {TIMEOUT_SECONDS}s, Max retries: {MAX_RETRIES}")

    # Initialize rate controller
    rate_ctrl = RateController(args.parallel)

    # Build model cost lookup
    model_costs = {m["id"]: (m["prompt_cost_per_token"], m["completion_cost_per_token"])
                   for m in models}

    # Initialize model stats
    model_stats = {m["id"]: {"done": 0, "prompt_tokens": 0, "completion_tokens": 0,
                              "time_ms": 0, "cost": 0.0, "errors": 0}
                   for m in models}

    # Load existing progress
    all_scores = []
    completed = set()

    if OUT_PATH.exists():
        print(f"\nLoading existing progress from {OUT_PATH}...")
        with open(OUT_PATH) as f:
            all_scores = json.load(f)

        for qi, entry in enumerate(all_scores):
            for ii, item_data in enumerate(entry.get("items", [])):
                for model_result in item_data.get("model_scores", []):
                    mid = model_result.get("model", "")
                    completed.add((qi, ii, mid))
                    if mid in model_stats:
                        model_stats[mid]["done"] += 1
                        model_stats[mid]["prompt_tokens"] += model_result.get("prompt_tokens", 0)
                        model_stats[mid]["completion_tokens"] += model_result.get("completion_tokens", 0)
                        model_stats[mid]["time_ms"] += model_result.get("response_time_ms", 0)
                        if model_result.get("error"):
                            model_stats[mid]["errors"] += 1
                        if mid in model_costs:
                            pc, cc = model_costs[mid]
                            model_stats[mid]["cost"] += (model_result.get("prompt_tokens", 0) * pc +
                                                         model_result.get("completion_tokens", 0) * cc)

        already_done = len(completed)
        print(f"  Found {already_done} completed (query, item, model) tuples")
        print(f"  Remaining: {total_calls - already_done} API calls")

    if len(completed) >= total_calls:
        print("All query-item-model combinations already scored!")
        return

    # Ensure all_scores structure is complete
    for qi, qobj in enumerate(queries):
        while len(all_scores) <= qi:
            all_scores.append(None)

        if all_scores[qi] is None:
            all_scores[qi] = {
                "site": qobj["site"],
                "query": qobj["query"],
                "query_length": len(qobj["query"]),
                "items": [],
            }

        query_result = all_scores[qi]
        items = qobj["items"]

        while len(query_result["items"]) < len(items):
            idx = len(query_result["items"])
            query_result["items"].append({
                "url": items[idx]["url"],
                "name": items[idx]["name"],
                "model_scores": [],
            })

    # Build per-model work queues for fair scheduling
    # This ensures fast models don't starve slow models of parallelism
    print("\nBuilding per-model work queues...")
    model_queues = {m["id"]: [] for m in models}  # model_id -> list of WorkItems

    for qi, qobj in enumerate(queries):
        query = qobj["query"]
        site = qobj["site"]
        items = qobj["items"]

        for ii, item in enumerate(items):
            for mi, m in enumerate(models):
                if (qi, ii, m["id"]) not in completed:
                    model_queues[m["id"]].append(WorkItem(
                        qi=qi, ii=ii, model_idx=mi, model_id=m["id"],
                        query=query, item=item, site=site
                    ))

    total_work = sum(len(q) for q in model_queues.values())
    active_models = [mid for mid, q in model_queues.items() if len(q) > 0]
    print(f"  Work items in queue: {total_work}")
    print(f"  Active models with remaining work: {len(active_models)}")
    print()

    # Create async client
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_KEY,
    )

    # Progress tracking
    completed_count = len(completed)
    last_save_time = time.time()
    start_time = time.time()
    retry_queue = []  # (ready_time, work_item)

    # Per-model tracking for fair scheduling
    model_in_flight = {m["id"]: 0 for m in models}  # count of in-flight requests per model
    model_queue_idx = {m["id"]: 0 for m in models}  # next index in each model's queue
    model_ids = [m["id"] for m in models]
    round_robin_idx = 0  # for fair model selection

    print(f"Starting with {rate_ctrl.get_parallel()} parallel requests...")
    print(f"  Total models: {len(models)}, round-robin selection (no per-model caps)")
    print("=" * 80)

    # Semaphore to limit total concurrency
    sem = asyncio.Semaphore(MAX_PARALLEL)

    async def process_work(work: WorkItem) -> tuple[WorkItem, dict | None, bool]:
        """Process a work item with semaphore control."""
        async with sem:
            result = await score_one(client, work, rate_ctrl)
            return (*result, True)

    # Active tasks
    pending_tasks = set()

    def get_next_work():
        """Get next work item using round-robin across models for fairness.

        Round-robin ensures we cycle through models fairly when selecting,
        but fast models that complete quickly will naturally get more total work done.
        No per-model caps - the global semaphore limits total parallelism.
        """
        nonlocal round_robin_idx
        now = time.time()

        # Check retry queue first
        while retry_queue and retry_queue[0][0] <= now:
            _, work_item = retry_queue.pop(0)
            return work_item

        # Round-robin through models for fair selection
        # No per-model cap - fast models will naturally process more
        for _ in range(len(model_ids)):
            model_id = model_ids[round_robin_idx]
            round_robin_idx = (round_robin_idx + 1) % len(model_ids)

            # Skip if this model's queue is exhausted
            queue = model_queues[model_id]
            idx = model_queue_idx[model_id]
            if idx >= len(queue):
                continue

            # Get next work item for this model
            work = queue[idx]
            model_queue_idx[model_id] = idx + 1
            return work

        return None

    # Fill initial batch
    current_parallel = rate_ctrl.get_parallel()
    while len(pending_tasks) < current_parallel:
        work = get_next_work()
        if work is None:
            break
        model_in_flight[work.model_id] += 1
        task = asyncio.create_task(process_work(work))
        pending_tasks.add(task)

    def has_remaining_work():
        """Check if there's any work left in queues or retries."""
        if retry_queue:
            return True
        for mid in model_ids:
            if model_queue_idx[mid] < len(model_queues[mid]):
                return True
        return False

    # Process until done
    while pending_tasks or has_remaining_work():
        if not pending_tasks:
            # Wait for retry queue
            if retry_queue:
                wait_time = max(0.1, retry_queue[0][0] - time.time())
                await asyncio.sleep(min(wait_time, 1.0))
                # Try to get work again
                work = get_next_work()
                if work:
                    model_in_flight[work.model_id] += 1
                    task = asyncio.create_task(process_work(work))
                    pending_tasks.add(task)
            continue

        # Wait for at least one task to complete
        done, pending_tasks = await asyncio.wait(
            pending_tasks,
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in done:
            try:
                work_item, result, _ = task.result()

                # Decrement in-flight count for this model
                model_in_flight[work_item.model_id] -= 1

                if result is None:
                    # Failed - retry if attempts remaining
                    if work_item.attempt < MAX_RETRIES:
                        retry_work = WorkItem(
                            qi=work_item.qi, ii=work_item.ii,
                            model_idx=work_item.model_idx, model_id=work_item.model_id,
                            query=work_item.query, item=work_item.item,
                            site=work_item.site, attempt=work_item.attempt + 1
                        )
                        wait_time = min(30, 2 ** work_item.attempt)
                        ready_time = time.time() + wait_time
                        retry_queue.append((ready_time, retry_work))
                        retry_queue.sort(key=lambda x: x[0])
                    else:
                        # Max retries - record error
                        model_short = work_item.model_id.split("/")[-1][:20]
                        print(f"  [Q{work_item.qi}I{work_item.ii}M{work_item.model_idx}] GIVING UP {model_short}")

                        error_result = {
                            "model": work_item.model_id,
                            "url": work_item.item["url"],
                            "name": work_item.item["name"],
                            "score": -1,
                            "description": "ERROR: Max retries exceeded",
                            "response_time_ms": 0,
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                            "error": True,
                        }

                        item_result = all_scores[work_item.qi]["items"][work_item.ii]
                        item_result["model_scores"].append(error_result)
                        completed.add((work_item.qi, work_item.ii, work_item.model_id))
                        model_stats[work_item.model_id]["done"] += 1
                        model_stats[work_item.model_id]["errors"] += 1
                        completed_count += 1
                else:
                    # Success - record result
                    item_result = all_scores[work_item.qi]["items"][work_item.ii]
                    item_result["model_scores"].append(result)
                    completed.add((work_item.qi, work_item.ii, work_item.model_id))

                    model_id = result["model"]
                    model_stats[model_id]["done"] += 1
                    model_stats[model_id]["prompt_tokens"] += result.get("prompt_tokens", 0)
                    model_stats[model_id]["completion_tokens"] += result.get("completion_tokens", 0)
                    model_stats[model_id]["time_ms"] += result.get("response_time_ms", 0)
                    if model_id in model_costs:
                        pc, cc = model_costs[model_id]
                        model_stats[model_id]["cost"] += (result.get("prompt_tokens", 0) * pc +
                                                          result.get("completion_tokens", 0) * cc)
                    completed_count += 1

            except Exception as e:
                print(f"  Task exception: {str(e)[:50]}")

        # Fill up to current parallel limit
        current_parallel = rate_ctrl.get_parallel()
        while len(pending_tasks) < current_parallel:
            work = get_next_work()
            if work is None:
                break
            model_in_flight[work.model_id] += 1
            task = asyncio.create_task(process_work(work))
            pending_tasks.add(task)

        # Periodic save
        now = time.time()
        if now - last_save_time >= SAVE_INTERVAL:
            save_progress(all_scores, model_stats)
            elapsed = now - start_time
            rate = completed_count / elapsed if elapsed > 0 else 0
            total_cost = sum(s["cost"] for s in model_stats.values())
            pending_retries = len(retry_queue)
            print(f"\n  [PROGRESS] {completed_count}/{total_calls} ({100*completed_count/total_calls:.1f}%) "
                  f"| {rate:.1f}/s | ${total_cost:.4f} | parallel={current_parallel} | "
                  f"in_flight={len(pending_tasks)} | retries={pending_retries}\n")
            last_save_time = now

    # Final save
    save_progress(all_scores, model_stats)

    # Final summary
    elapsed = time.time() - start_time
    print(f"\n{'='*80}")
    print("FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"\nTotal time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"\n{'Model':<50s} {'Pairs':>6s} {'Cost':>10s} {'$/pair':>12s} {'Latency':>8s} {'Errors':>6s}")
    print("-" * 95)

    sorted_stats = sorted(model_stats.items(), key=lambda x: x[1]["cost"])
    for model_id, stats in sorted_stats:
        if stats["done"] == 0:
            continue
        avg_latency = stats["time_ms"] / stats["done"] if stats["done"] else 0
        cost_per_pair = stats["cost"] / stats["done"] if stats["done"] else 0
        print(f"{model_id:<50s} {stats['done']:>6d} ${stats['cost']:>9.4f} "
              f"${cost_per_pair:>11.8f} {avg_latency:>6.0f}ms {stats['errors']:>6d}")

    total_cost = sum(s["cost"] for s in model_stats.values())
    total_done = len(completed)
    print(f"\nTotal cost: ${total_cost:.4f}")
    print(f"Total API calls: {total_done}")
    print(f"Throughput: {total_done/elapsed:.1f} calls/sec")
    print(f"Output: {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())

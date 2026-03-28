"""Fetch models from OpenRouter and write three curated lists:

  - cheapest_models_free.json     (best free models, one per family)
  - cheapest_models_ultra.json    (< $0.05/M blended, one per family)
  - cheapest_models_mid.json      ($0.05–$0.10/M blended, one per family)

Also writes cheapest_models.json with all three tiers combined.
"""

import json
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# ── Curated picks: one model per family per tier ──────────────────────────

FREE_PICKS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1-0528:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
    "qwen/qwen3-4b:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "openai/gpt-oss-120b:free",
    "z-ai/glm-4.5-air:free",
    "stepfun/step-3.5-flash:free",
]

ULTRA_CHEAP_PICKS = [
    "meta-llama/llama-3.1-8b-instruct",
    "google/gemma-3n-e4b-it",
    "mistralai/mistral-nemo",
    "liquid/lfm2-8b-a1b",
    "mistralai/ministral-3b",
    "ibm-granite/granite-4.0-h-micro",
    "nousresearch/deephermes-3-mistral-24b-preview",
    "sao10k/l3-lunaris-8b",
    "liquid/lfm-2.2-6b",
    "google/gemma-3-4b-it",
]

MID_CHEAP_PICKS = [
    "deepseek/deepseek-r1-distill-llama-70b",
    "google/gemma-3-27b-it",
    "mistralai/mistral-small-3.1-24b-instruct",
    "qwen/qwen-2.5-7b-instruct",
    "amazon/nova-micro-v1",
    "microsoft/phi-4",
    "nvidia/nemotron-nano-9b-v2",
    "cohere/command-r7b-12-2024",
    "openai/gpt-oss-120b",
    "arcee-ai/trinity-mini",
]


def main():
    print("Fetching model list from OpenRouter...")
    resp = httpx.get(OPENROUTER_MODELS_URL, timeout=30)
    resp.raise_for_status()
    models_raw = resp.json()["data"]

    # Build lookup by id
    by_id = {m["id"]: m for m in models_raw}

    def model_entry(model_id: str) -> dict:
        m = by_id.get(model_id)
        if m is None:
            print(f"  WARNING: {model_id} not found on OpenRouter, skipping")
            return None
        pricing = m.get("pricing") or {}
        p = float(pricing.get("prompt", 0))
        c = float(pricing.get("completion", 0))
        return {
            "id": model_id,
            "name": m.get("name", model_id),
            "context_length": m.get("context_length", 0),
            "prompt_cost_per_token": p,
            "completion_cost_per_token": c,
            "blended_cost": (2 * p + c) / 3,
        }

    def write_list(name: str, picks: list[str]) -> list[dict]:
        entries = [e for mid in picks if (e := model_entry(mid)) is not None]
        path = DATA_DIR / f"cheapest_models_{name}.json"
        with open(path, "w") as f:
            json.dump(entries, f, indent=2)
        print(f"\n=== {name.upper()} ({len(entries)} models) → {path.name} ===")
        for i, e in enumerate(entries, 1):
            print(f"  {i:2d}. {e['id']:<55s}  "
                  f"prompt=${e['prompt_cost_per_token']*1e6:.3f}/M  "
                  f"completion=${e['completion_cost_per_token']*1e6:.3f}/M")
        return entries

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    free_list = write_list("free", FREE_PICKS)
    ultra_list = write_list("ultra", ULTRA_CHEAP_PICKS)
    mid_list = write_list("mid", MID_CHEAP_PICKS)

    # Combined file for score_openrouter.py
    combined = free_list + ultra_list + mid_list
    combined_path = DATA_DIR / "cheapest_models.json"
    with open(combined_path, "w") as f:
        json.dump(combined, f, indent=2)
    print(f"\nCombined: {len(combined)} models → {combined_path.name}")


if __name__ == "__main__":
    main()

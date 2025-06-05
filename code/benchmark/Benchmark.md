# Speed Benchmark for NLWeb

This directory contains a speed benchmark for NLWeb.

## What It Does
- Measures the response time of single-turn and multi-turn conversations using different LLM providers.
- Reports timing statistics and generates plots for performance analysis.

## How to Run
From the `code` directory, run:

```bash
python benchmark/run_speed_benchmark.py
```

## Requirements
- Python 3.10+
- Install dependencies following the instructions in this [README](https://github.com/microsoft/NLWeb/blob/main/HelloWorld.md).
- Set up environment variables as described in the main `.env.template` (API keys, etc.).

## Input Data
- Input conversations are in `benchmark/data/conversations.jsonl`.
  - Each line is a JSON object with a `conversation` key, whose value is a list of user queries (one conversation per line).

## Output
- Results and plots are saved in `benchmark/data/results/` and `benchmark/data/benchmark_results/`.
- Console output includes timing statistics by provider.

## Notes
- The benchmark uses your current config and environment variables (see `config/`).
- For best results, ensure all required API keys are set and the backend services are reachable. 
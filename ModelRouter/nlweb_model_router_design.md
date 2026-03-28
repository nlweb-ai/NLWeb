# NLWeb Model Router: Design Doc

## Goal

Build a routing layer that sits between NLWeb and OpenRouter. Given an NLWeb task (scoring, summarization, decontextualization), dynamically select the cheapest adequate model based on query complexity. Query length (character count) is the initial complexity proxy.

## Architecture

```
NLWeb task call
  → Router: estimate complexity from len(query)
  → Router: look up cheapest adequate model for (task, complexity_tier)
  → Send to OpenRouter with selected model
  → Return response to NLWeb
```

## Phase 1: Evaluation Pipeline

### 1.1 Test Set Generation

Create a test set of queries spanning the complexity spectrum. For each of the three tasks:

- Write 20 seed queries by hand, distributed across short/medium/long
- Use a strong model (e.g., claude-sonnet-4-5-20250514 via OpenRouter) to generate 80 more, prompted to cover the full range
- Target: ~100 queries per task, with roughly equal distribution across length buckets

For the **scoring task**, each query needs ~5 representative items (item descriptions from schema.org data) paired with it. Store as:

```json
{
  "task": "scoring",
  "query": "vanilla ice cream",
  "query_length": 17,
  "items": [
    {"url": "...", "description": "Classic vanilla bean ice cream..."},
    ...
  ]
}
```

For **summarization**, each test case is a query + a set of pre-ranked items (simulate output of the scoring step).

For **decontextualization**, each test case is an item description + the query context it appeared in.

### 1.2 Golden Answers

Run every test case through the strongest model using the actual NLWeb prompt templates:

- **Scoring**: Use `RANKING_PROMPT` template. Store the score (0-100) and description.
- **Summarization**: Use the summarization prompt. Store the full summary.
- **Decontextualization**: Use the decontextualization prompt. Store the standalone description.

Run scoring cases 3x to check golden model consistency. Discard cases where the golden model's scores vary by more than 15 points across runs.

### 1.3 Candidate Model Evaluation

Select 5-8 models from OpenRouter spanning the cost spectrum. Example set (adjust based on current pricing):

```yaml
candidate_models:
  - id: "mistralai/mistral-small-latest"
    tier: cheap
  - id: "mistralai/mistral-medium-latest"
    tier: cheap
  - id: "google/gemini-2.0-flash"
    tier: mid
  - id: "anthropic/claude-3-5-haiku-20241022"
    tier: mid
  - id: "anthropic/claude-3-5-sonnet-20241022"
    tier: expensive
  # add more as appropriate
```

Run every test case through every candidate model. Store all responses.

### 1.4 Grading

Compare each candidate model's output against golden answers:

- **Scoring**: Grade = 1 if candidate score is within ±10 of golden score AND description captures the key relevance factors. Use the golden model as judge for description quality (binary: adequate/inadequate).
- **Summarization**: Use golden model as judge. Prompt: "Rate this summary against the reference on faithfulness (1-5), completeness (1-5), conciseness (1-5)." Adequate = all dimensions ≥ 4.
- **Decontextualization**: Use golden model as judge. Prompt: "Does this description make complete sense without any additional context? Yes/No." Adequate = Yes.

Output: a matrix of `(task, query, model) → adequate: bool`

## Phase 2: Threshold Discovery

### 2.1 Analysis

For each task, plot:
- X axis: query length (characters)
- Y axis: % of items where model was adequate
- One line per model

Identify natural breakpoints where cheap models start failing. Expect something like:

```
Length < 50 chars  → cheapest model works
Length 50-150      → mid-tier needed
Length > 150       → expensive model needed
```

The actual thresholds come from the data.

### 2.2 Configuration

Store the result as a simple config:

```yaml
routing_config:
  scoring:
    thresholds:
      - max_length: 50
        model: "mistralai/mistral-small-latest"
        cost_per_1k_tokens: 0.001
      - max_length: 150
        model: "google/gemini-2.0-flash"
        cost_per_1k_tokens: 0.003
      - max_length: null  # default / fallback
        model: "anthropic/claude-3-5-sonnet-20241022"
        cost_per_1k_tokens: 0.015
  summarization:
    thresholds:
      # ... same structure
  decontextualization:
    thresholds:
      # ... same structure
```

## Phase 3: Runtime Router

### 3.1 Router Module

```python
class NLWebModelRouter:
    def __init__(self, config_path: str):
        """Load routing config from YAML."""
        self.config = load_config(config_path)

    def select_model(self, task: str, query: str) -> str:
        """Return the OpenRouter model ID for this task + query."""
        query_length = len(query)
        thresholds = self.config[task]["thresholds"]
        for tier in thresholds:
            if tier["max_length"] is None or query_length <= tier["max_length"]:
                return tier["model"]
        # fallback to most expensive
        return thresholds[-1]["model"]
```

### 3.2 Integration Point

The router is called wherever NLWeb currently selects a model for an LLM call. The three call sites are:

1. **Scoring** (`rankItem` in the ranking module): before calling the LLM to score each (query, item) pair
2. **Summarization**: before calling the LLM to generate the summary answer
3. **Decontextualization**: before calling the LLM to produce standalone descriptions

Each call site passes `(task_name, query)` to the router and uses the returned model ID for the OpenRouter API call.

### 3.3 Logging

Every routed call should log:
- timestamp, task, query_length, selected_model, response_time, token_count
- This enables later analysis of whether the thresholds are right and what the actual cost savings are.

## Phase 4: Future Improvements (not in scope now)

- **Additional complexity signals**: If query length alone is too noisy, add secondary signals (token count, presence of medical/dietary terms, number of comma-separated clauses). These can be combined into a simple score without any LLM call.
- **Within-tier routing**: If a single tier has high variance, use kNN over a complexity feature vector to pick between models within that tier.
- **Online learning**: Use the logs from Phase 3.3 to detect queries where the cheap model was inadequate (e.g., user complained, or a spot-check with the golden model shows the answer was poor) and adjust thresholds.
- **Per-site tuning**: Some sites may have systematically harder or easier item descriptions. Site ID could become a routing signal.

## File Structure

```
nlweb_router/
├── config/
│   └── routing_config.yaml       # thresholds per task
├── evaluation/
│   ├── generate_test_set.py      # seed expansion + item pairing
│   ├── run_golden.py             # run golden model on test set
│   ├── run_candidates.py         # run all candidate models
│   ├── grade.py                  # compare candidates to golden
│   └── analyze_thresholds.py     # plot and find breakpoints
├── router/
│   ├── model_router.py           # NLWebModelRouter class
│   └── openrouter_client.py      # thin wrapper around OpenRouter API
├── data/
│   ├── test_sets/                # generated test cases
│   ├── golden_answers/           # golden model outputs
│   ├── candidate_answers/        # all candidate model outputs
│   └── grades/                   # adequacy matrix
└── README.md
```

## Environment

- OpenRouter API key in env var `OPENROUTER_API_KEY`
- All LLM calls go through OpenRouter (including the golden model)
- Python 3.11+, dependencies: openai (OpenRouter is OpenAI-compatible), pyyaml, matplotlib (for threshold analysis)

## Definition of Done

1. Evaluation pipeline runs end-to-end: generates test set, runs golden + candidates, grades, produces threshold analysis plots
2. Routing config YAML exists with empirically derived thresholds
3. `NLWebModelRouter` class is tested and integrated at the three NLWeb call sites
4. Logging is in place for all routed calls

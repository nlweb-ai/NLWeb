# Training Recipe: ModernBERT + Rubric GAM for Relevance Scoring

## Executive Summary

This document describes a two-stage training pipeline for building a fast, interpretable relevance scorer that replaces LLM-based ranking at inference time. The pipeline trains:

1. **Stage 1 — ModernBERT-large**: Fine-tunes a 390M-parameter encoder to predict relevance scores from (query, item) text pairs.
2. **Stage 2 — Rubric GAM**: Trains an interpretable Neural Additive Model that combines BERT's learned embeddings with hand-crafted rubric features (relevance overlap, type match, completeness, quality, specificity).

The result is a model that scores items in ~2ms each (batched on GPU), compared to ~500ms+ per item for an LLM call, while producing interpretable per-feature contribution breakdowns.

**Target audience**: Teams building relevance scoring for search, recommendation, or content ranking systems. The NLWeb implementation is used as a concrete reference throughout, but the approach generalizes to any domain where you have (query, candidate, relevance_score) triples.

---

## Table of Contents

1. [Prerequisites and Infrastructure](#1-prerequisites-and-infrastructure)
2. [Generating Training Data with an LLM](#2-generating-training-data-with-an-llm)
3. [Data Preparation and Feature Engineering](#3-data-preparation-and-feature-engineering)
4. [Diagnosing and Fixing Data Distribution Problems](#4-diagnosing-and-fixing-data-distribution-problems)
5. [Stage 1: Fine-Tuning ModernBERT](#5-stage-1-fine-tuning-modernbert)
6. [Stage 2: Training the Rubric GAM](#6-stage-2-training-the-rubric-gam)
7. [Evaluation and Metrics](#7-evaluation-and-metrics)
8. [Detecting and Eliminating Spurious Correlations](#8-detecting-and-eliminating-spurious-correlations)
9. [Production Inference](#9-production-inference)
10. [Common Failure Modes and How to Fix Them](#10-common-failure-modes-and-how-to-fix-them)
11. [Appendix: Configuration Reference](#11-appendix-configuration-reference)

---

## 1. Prerequisites and Infrastructure

### Hardware Requirements

| Stage | Minimum | Recommended | Notes |
|-------|---------|-------------|-------|
| Data preparation | Any CPU | 16GB RAM | Processing JSON + feature extraction |
| Stage 1 (ModernBERT-large) | 1× A100 40GB | 1× A100 80GB or H100 | 4.4GB model + gradients + optimizer states |
| Stage 2 (Rubric GAM) | CPU or any GPU | Any GPU | Small model (~400KB), trains in minutes |
| Inference | 1× GPU (any) | A10 or better | Batch scoring is memory-bound, not compute-bound |

ModernBERT-large has 390M parameters. With AdamW optimizer states and gradients, expect ~18GB GPU memory at batch size 4 with gradient accumulation. Apple Silicon MPS works but is 3-4x slower than A100.

### Software Dependencies

```
torch>=2.2.0
transformers>=4.40.0        # ModernBERT support
tokenizers>=0.19.0
scipy>=1.12.0               # Spearman correlation
numpy>=1.26.0
scikit-learn>=1.4.0
pyyaml>=6.0
tqdm>=4.66.0
```

### What You Need Before Starting

1. **A retrieval system** that produces candidate items for queries (vector search, BM25, etc.)
2. **An LLM** (GPT-4.1, Claude, etc.) to generate ground-truth relevance scores
3. **A corpus of queries** representative of your production traffic
4. **Schema.org-structured items** (or equivalent structured metadata for your domain)

---

## 2. Generating Training Data with an LLM

The entire pipeline is built on **LLM-as-judge** data: you use a strong LLM to score (query, item) pairs, then train a small model to approximate those scores at 100x the speed.

### Step 1: Collect Representative Queries

Pull queries from production logs, user studies, or synthetic generation. You need diversity along several axes:

- **Query intent**: navigational ("NYT crossword"), informational ("how to make sourdough"), transactional ("buy running shoes")
- **Query length**: single words ("pizza") through multi-clause ("family-friendly Italian restaurants near downtown with outdoor seating")
- **Query difficulty**: easy (high lexical overlap with good results) through hard (requires world knowledge, e.g. "movies about food, preferably asian")
- **Domain coverage**: all content types and sites your system serves

**How many?** In NLWeb, we used ~4,200 unique queries producing ~42,000 (query, item) pairs. More is better, but diminishing returns set in around 50K pairs for most domains. Focus on diversity over volume.

### Step 2: Retrieve Candidates

For each query, run your retrieval system and collect the top-K candidates (K=20 is a good starting point). Include the full structured metadata for each item — not just title and URL, but the complete schema.org JSON or equivalent.

**Critical**: Include items across the full relevance spectrum. If your retrieval only returns highly relevant items, the model will never learn to distinguish mediocre from bad. Consider:
- Adding random items from the corpus as hard negatives
- Including results from related but different queries
- Mixing in items from different content types

### Step 3: Score with an LLM

For each (query, item) pair, ask the LLM to assign a relevance score from 0-100. Use a prompt like:

```
Assign a score between 0 and 100 to the following {item_type} based on how
relevant it is to the user's question. Use your knowledge about the item to
make a judgement.

The user's question is: {query}
The item's description is: {item_description}

{"score": "integer between 0 and 100", "description": "short explanation"}
```

**Important considerations:**

- **Use your strongest available LLM.** The student (ModernBERT) can only be as good as the teacher. GPT-4.1 or Claude Opus are recommended. Do not use smaller models — their scoring inconsistencies become the ceiling for your trained model.
- **Normalize scores to [0, 1]** by dividing by 100. The training pipeline uses sigmoid outputs and MSE loss, so targets must be in this range.
- **Run scoring at low temperature** (0.0-0.2) for consistency.
- **Batch efficiently.** At ~42K pairs, expect $50-200 in LLM API costs depending on item description length and model choice.

### Step 4: Validate LLM Scores

Before proceeding, manually audit a random sample of 100+ scored pairs:

- Are scores above 70 genuinely relevant?
- Are scores below 30 genuinely irrelevant?
- Do scores in the 40-60 range represent reasonable "partial relevance"?
- Are there systematic biases? (e.g., longer descriptions always scoring higher)

If the LLM scores are noisy or biased, fix the prompt or switch models before training. Garbage in, garbage out.

---

## 3. Data Preparation and Feature Engineering

### Input Format

Each training example requires:

```json
{
  "query": "authentic Middle Eastern shawarma spice blend",
  "item_text": "[query] [SEP] [readable text from schema]",
  "score": 0.70,
  "schema_type": "Recipe",
  "site": "mediterranean_dish",
  "difficulty": 4,
  "rubric_features": {
    "query_term_coverage": 0.333,
    "title_query_overlap": 0.333,
    "exact_query_match": 0.0,
    "query_item_word_overlap": 0.3,
    "type_match": 0.8,
    "description_length": 450.0,
    "schema_field_count": 13.0,
    "has_rating": 0.0,
    "has_price": 0.0,
    "has_image": 1.0,
    "has_date": 1.0,
    "content_word_count": 85.0,
    "has_author": 1.0,
    "query_word_count": 6.0,
    "name_word_count": 4.0
  }
}
```

### The `item_text` Field

This is the text input to ModernBERT. Format: `[query] [SEP] [readable text]`

The readable text is built from the structured metadata by flattening the schema into a human-readable format. For example, a Recipe schema becomes:

```
Name: Homemade Chicken Shawarma
Description: Tender marinated chicken with Middle Eastern spices...
Author: Chef Ahmad
Ingredients: chicken thighs, cumin, coriander, turmeric...
```

**Do not include the site name** in the item text. In NLWeb, we found that including the site name (e.g., "allrecipes.com") created a spurious correlation — the model learned that certain sites always score high, rather than learning about content relevance. When we stripped site names from training data, the model's ability to generalize to new sites improved significantly. The general lesson: strip any metadata that identifies the *source* rather than describing the *content*.

**Truncation**: Cap item text at ~4000 characters before tokenization. ModernBERT's max sequence length is 1024 tokens; longer text gets truncated by the tokenizer anyway, and very long descriptions often contain boilerplate that hurts more than it helps.

### The 16 Rubric Features

These are hand-crafted features grouped into 5 categories. The GAM learns a separate function for each group, making the model interpretable.

**Group 1: Relevance (4 features)** — Lexical overlap signals

| Feature | Computation | Range |
|---------|-------------|-------|
| `query_term_coverage` | Fraction of query words found anywhere in item text | [0, 1] |
| `title_query_overlap` | Fraction of query words found in item name/title | [0, 1] |
| `exact_query_match` | 1.0 if the full query string appears as a substring in item text | {0, 1} |
| `query_item_word_overlap` | Jaccard similarity: \|Q ∩ I\| / \|Q ∪ I\| | [0, 1] |

**Group 2: Type Match (1 feature)** — Does the item's type match the query intent?

| Feature | Computation | Range |
|---------|-------------|-------|
| `type_match` | Heuristic score based on query keywords → expected schema type | [0, 1] |

Example: If the query contains "recipe" and the item is a `Recipe` schema type → 1.0. If the query mentions "buy" and the item is a `Product` → 1.0. Mismatches score lower.

**Adapt this to your domain.** If you're ranking products, the type match might check category alignment. If you're ranking documents, it might check document type (tutorial vs. reference vs. API docs).

**Group 3: Completeness (5 features)** — How much metadata does the item have?

| Feature | Computation | Range |
|---------|-------------|-------|
| `description_length` | Character count of description field | [0, ∞) |
| `schema_field_count` | Number of non-internal fields in structured data | [0, ∞) |
| `has_rating` | 1.0 if rating/review data present | {0, 1} |
| `has_price` | 1.0 if pricing data present | {0, 1} |
| `has_image` | 1.0 if image URL present | {0, 1} |

**Group 4: Quality (3 features)** — Signals of content quality

| Feature | Computation | Range |
|---------|-------------|-------|
| `has_date` | 1.0 if publication/modification date present | {0, 1} |
| `content_word_count` | Word count of description | [0, ∞) |
| `has_author` | 1.0 if author/publisher/creator present | {0, 1} |

**Group 5: Specificity (3 features)** — Query and item complexity

| Feature | Computation | Range |
|---------|-------------|-------|
| `query_word_count` | Number of words in the query | [1, ∞) |
| `name_word_count` | Number of words in item name | [1, ∞) |
| `difficulty` | Query difficulty level (from data metadata, 0-5) | [0, 5] |

### Designing Rubric Features for Your Domain

The NLWeb features above are designed for web search over schema.org data. When adapting to your domain, follow these principles:

1. **Each group should capture one semantic dimension.** Don't mix relevance signals with quality signals.
2. **Features within a group should be related.** The GAM learns one function per group — mixing unrelated features in a group forces the model to compress unrelated signals into one function.
3. **Include both lexical and structural features.** BERT handles semantics; rubric features should capture things BERT can't see from text alone (metadata completeness, type alignment, structural properties).
4. **Keep features simple and cheap to compute.** These run at inference time on every item. Complex features defeat the purpose of replacing an LLM.

**Examples for other domains:**

- **Product search**: price_in_range, brand_match, category_match, availability, review_count, seller_rating
- **Document search**: recency, document_length, section_heading_match, code_example_count, api_version_match
- **Job search**: location_match, salary_range_match, experience_level_match, skill_overlap, company_size

### Train/Val/Test Split

**Split by query, not by example.** All items for a given query must go into the same split. Otherwise, the model can memorize query patterns from training items and appear to generalize on validation items for the same query.

```python
# Correct: group by query, then split
unique_queries = list(set(example["query"] for example in data))
random.shuffle(unique_queries)
n = len(unique_queries)
train_queries = set(unique_queries[:int(0.8 * n)])
val_queries = set(unique_queries[int(0.8 * n):int(0.9 * n)])
test_queries = set(unique_queries[int(0.9 * n):])

# Wrong: random split of individual examples
# random.shuffle(data); train = data[:80%]  # DATA LEAKAGE!
```

Recommended split: **80% train / 10% val / 10% test**.

In NLWeb, this produces: ~33,500 train / ~4,200 val / ~4,200 test examples from ~42,000 total.

---

## 4. Diagnosing and Fixing Data Distribution Problems

This is where most training failures originate. A well-architected model trained on poorly distributed data will produce a poorly calibrated scorer. Spend serious time here before training.

### Problem 1: Score Distribution Imbalance

**Symptom**: Most items score 70-90 (because your retrieval system is decent), so the model learns to predict ~80 for everything and still achieves low MSE.

**Diagnosis**:
```python
import numpy as np
scores = [ex["score"] for ex in training_data]
hist, bin_edges = np.histogram(scores, bins=10)
for i, count in enumerate(hist):
    print(f"  {bin_edges[i]:.1f}-{bin_edges[i+1]:.1f}: {count:5d} {'█' * (count // 50)}")
```

If any decile has <5% of the data, you have a distribution problem.

**Fixes**:

1. **Add negative examples.** For each query, include random items from unrelated parts of your corpus. These should score 0-20 and dramatically improve the model's ability to distinguish relevant from irrelevant.

2. **Bad-heavy sampling.** Oversample the low-score deciles:
   ```python
   # Upsample items with scores 0-40 by a factor of 3x
   bad_examples = [ex for ex in data if ex["score"] < 0.4]
   augmented = data + bad_examples * 2  # Now 3x the original count of bad examples
   ```
   In NLWeb, the `--bad-heavy 3.0` flag does exactly this.

3. **Balanced decile sampling.** Ensure each score decile (0-10, 10-20, ..., 90-100) has roughly equal representation:
   ```python
   target_count = max(counts_per_decile)
   for decile in range(10):
       decile_examples = [ex for ex in data if decile/10 <= ex["score"] < (decile+1)/10]
       upsample_factor = target_count // len(decile_examples)
       augmented.extend(decile_examples * upsample_factor)
   ```

### Problem 2: Site/Source Bias

**Symptom**: Items from popular sites (IMDB, AllRecipes, NYT) consistently score higher than items from niche sites, regardless of actual relevance. The model learns "IMDB = high score" instead of "relevant movie = high score."

**Diagnosis**:
```python
from collections import defaultdict
site_scores = defaultdict(list)
for ex in data:
    site_scores[ex["site"]].append(ex["score"])

for site, scores in sorted(site_scores.items(), key=lambda x: -np.mean(x[1])):
    print(f"  {site:30s}  mean={np.mean(scores):.2f}  n={len(scores)}")
```

If the mean score varies by more than 0.15 between sites, investigate further.

**Fixes**:

1. **Strip site identifiers from item text.** Remove domain names, site names, and any text that identifies the source rather than describing the content.

2. **Per-site score normalization.** Normalize scores within each site to zero mean before training, then denormalize at inference.

3. **Stratified sampling.** Ensure each site contributes proportionally to each score decile, so the model can't learn "site X = high score."

### Problem 3: Query Difficulty Imbalance

**Symptom**: Easy queries (high lexical overlap between query and relevant items) dominate the dataset, so the model never learns to handle hard queries (requiring world knowledge).

**Diagnosis**: Check the distribution of your difficulty metadata, or compute a proxy:
```python
# Proxy: average query_term_coverage for the top-3 items per query
for query in queries:
    items = [ex for ex in data if ex["query"] == query]
    top3 = sorted(items, key=lambda x: -x["score"])[:3]
    avg_coverage = np.mean([i["rubric_features"]["query_term_coverage"] for i in top3])
    # avg_coverage > 0.7 → easy query; < 0.3 → hard query
```

**Fix**: Filter or oversample by difficulty level. In NLWeb, the `--difficulty 4,5` flag restricts training to only hard queries. For a balanced approach, ensure at least 30% of training queries are "hard" (low lexical overlap between query and relevant items).

### Problem 4: Length Bias

**Symptom**: Longer item descriptions consistently score higher because they mention more keywords. The model learns "long text = relevant."

**Diagnosis**:
```python
lengths = [len(ex["item_text"]) for ex in data]
scores = [ex["score"] for ex in data]
correlation = np.corrcoef(lengths, scores)[0, 1]
print(f"Length-score Pearson r: {correlation:.3f}")
# If |r| > 0.3, you have a length bias
```

**Fix**:
1. Truncate all descriptions to a fixed maximum (e.g., 4000 characters) before feature extraction.
2. Add description length as a rubric feature so the GAM can learn to compensate.
3. Consider normalizing LLM scores by item length during data generation.

### Problem 5: Keyword Leakage (the "Dumplings" Problem)

**Symptom**: Items that mention query keywords anywhere in their description score high, even when the item is not actually about the query topic.

**Concrete example from NLWeb**: The query "movies about food, preferably asian" should rank food-themed movies highly. But the horror movie "Three... Extremes" (Sam gang 2) scored 85 because one of its three segments involves dumplings. BERT saw the word "dumplings" in the description and concluded "this is about food" — semantic similarity is not the same as relevance.

**Diagnosis**: For your highest-scoring items in the test set, manually check whether the item is *about* the query topic or merely *mentions* it. If you find items that mention but aren't about the topic scoring above 70, you have keyword leakage.

**This is a fundamental limitation of encoder models.** BERT computes semantic similarity between query and item text. It cannot reason about whether an item is "about" a topic vs. merely mentioning it. Mitigations:

1. **Use the type_match rubric feature** to penalize type mismatches (a horror movie should score lower for a food query even if it mentions food).
2. **Add genre/category features** to your rubric if your domain has them.
3. **Accept the limitation** for production use and plan for an LLM-based scorer as a fallback for hard queries. The BERT+GAM scorer handles 80-90% of queries well; the remaining 10-20% may need LLM reasoning.
4. **Curate hard negatives** specifically for this pattern: find items that mention query keywords but are not about the topic, and ensure they're scored low in your training data.

---

## 5. Stage 1: Fine-Tuning ModernBERT

### Why ModernBERT?

ModernBERT-large (`answerdotai/ModernBERT-large`) is a 2024 encoder model with several advantages over BERT/RoBERTa:
- Native 8192-token context (though we use 1024 for efficiency)
- Flash Attention 2 support → faster training
- Rotary Position Embeddings → better length generalization
- 1024-dimensional hidden states → richer embeddings for the GAM

### Model Architecture

```
Input: "[query] [SEP] [readable item text]"
       ↓
ModernBERT-large (24 layers, 1024 hidden)
       ↓
[CLS] token embedding (1024-d)
       ↓
Linear(1024, 256) → ReLU → Dropout(0.1) → Linear(256, 1) → Sigmoid
       ↓
Output: score ∈ [0, 1]
```

In "pure text" mode (recommended), the model sees only the text and learns relevance from text alone. Rubric features are added in Stage 2 via the GAM.

### Training Configuration

```yaml
modernbert:
  model_name: "answerdotai/ModernBERT-large"
  pure_text: true                    # No rubric features in BERT — handled by GAM

  # Optimizer
  learning_rate: 1.0e-5              # Conservative for large model
  weight_decay: 0.01                 # Standard L2 regularization
  warmup_ratio: 0.1                  # 10% of steps for linear warmup

  # Batch size
  per_device_train_batch_size: 4     # Limited by GPU memory
  gradient_accumulation_steps: 8     # Effective batch size = 32
  per_device_eval_batch_size: 8

  # Training
  num_epochs: 5                      # Usually converges by epoch 3-4
  max_seq_length: 1024               # Truncate inputs to 1024 tokens

  # Loss
  loss: "mse"                        # Mean squared error
  ranking_alpha: 0.0                 # Pairwise ranking loss weight
  score_diff_alpha: 1.0              # Pairwise score-difference loss weight
  lambda_alpha: 0.5                  # LambdaRank-weighted loss weight

  # Model selection
  mae_lambda: 1.0                    # selection_score = satisficer - 1.0 * MAE
```

### Loss Functions

The training loss is a weighted combination:

**Primary: MSE Loss**
```
L_mse = mean((predicted_score - true_score)²)
```

**Auxiliary: Pairwise Score-Difference Loss** (`score_diff_alpha`)
```
For all pairs (i, j) from the same query where |true_i - true_j| > 0.05:
  L_diff = mean((pred_i - pred_j - (true_i - true_j))²)
```
This teaches the model to reproduce the *magnitude* of score differences, not just the ordering. It's more informative than simple pairwise ranking loss because it penalizes predicting a 5-point gap when the true gap is 30 points.

**Auxiliary: LambdaRank-Weighted Loss** (`lambda_alpha`)
```
For boundary pairs (one item good ≥ 0.6, the other not in top-5):
  Weight = 1.0 + 5.0 × |change in satisficer if items swapped|
  Bad items in top-5 get 2x the penalty weight
  L_lambda = weighted_mean((pred_diff - true_diff)²)
```
This focuses the model's attention on the pairs that matter most: the boundary between "in the top results" and "out of the top results."

### Query-Grouped Batching

When using pairwise losses, all items for a given query must be in the same batch (otherwise you can't compute pairwise terms). The training pipeline uses a custom `QueryGroupedBatchSampler` that:

1. Groups all examples by (site, query)
2. Shuffles the group ordering each epoch
3. Shuffles examples within each group
4. Yields one group per batch

This means batch sizes vary (some queries have 5 items, others 25), which is fine for training.

### Learning Rate Schedule

Linear warmup for the first 10% of training steps, then linear decay to 0:

```
Steps 0 to warmup_steps: LR ramps from 0 to learning_rate
Steps warmup_steps to total_steps: LR decays linearly from learning_rate to 0
```

Gradient clipping: max norm = 1.0 (prevents gradient explosions from long sequences).

### What to Monitor During Training

After each epoch, evaluate on the validation set and log:

| Metric | Good range | Concern if... |
|--------|-----------|---------------|
| Val MSE | 0.02-0.05 | > 0.08 (underfitting) or < 0.01 (overfitting) |
| Val MAE | 0.10-0.18 | > 0.20 (poor calibration) |
| Spearman ρ | 0.60-0.80 | < 0.50 (not learning ranking) |
| Satisficer score | 0.30-0.60 | < 0.20 (top-k quality is bad) |
| Good picks | 0.50-0.80 | < 0.40 (missing relevant items) |
| Bad picks | 0.00-0.10 | > 0.15 (surfacing irrelevant items) |

**Model selection**: Save the checkpoint with the highest `selection_score = satisficer_score - mae_lambda × MAE`. This balances ranking quality (satisficer) with calibration accuracy (MAE).

### Extracting Embeddings for Stage 2

After training, extract [CLS] embeddings from the best checkpoint for all splits:

```python
# Run the trained model in inference mode
model.eval()
with torch.no_grad():
    for batch in dataloader:
        embeddings = model.get_embeddings(batch["input_ids"], batch["attention_mask"])
        # embeddings shape: (batch_size, 1024)
        all_embeddings.append(embeddings.cpu())

# Save as: {train,val,test}_embeddings.pt
torch.save({"embeddings": all_embeddings, "scores": all_scores, ...}, "train_embeddings.pt")
```

**Critical**: The GAM is trained on embeddings from a specific BERT checkpoint. If you retrain BERT, you must retrain the GAM. Mixing embeddings from different BERT checkpoints produces garbage — the embedding spaces are not aligned.

---

## 6. Stage 2: Training the Rubric GAM

### What is a Rubric GAM?

A **Neural Additive Model (NAM)** where the final score is a sum of independent functions:

```
score = sigmoid(bias + f_bert(projection(cls_embedding))
                     + f_relevance(relevance_features)
                     + f_type_match(type_features)
                     + f_completeness(completeness_features)
                     + f_quality(quality_features)
                     + f_specificity(specificity_features))
```

Each `f_*` is a small MLP that operates independently on its feature group. Because the functions are additive, you can inspect each group's contribution to understand *why* an item scored the way it did.

### Three GAM Modes

**1. Additive (recommended starting point)**
```
score = sigmoid(bias + f_bert + Σ f_group)
```
Simplest, most interpretable. Each group contributes independently. Start here.

**2. Gated (query-conditioned weighting)**
```
gate_weights = softmax(g(projection(cls_embedding)))  # per query
score = sigmoid(bias + f_bert + Σ gate_i × f_group_i)
```
The BERT embedding controls *how much* each rubric group matters for a given query. For example, `type_match` might matter more for "buy running shoes" than for "what is machine learning." More expressive, but harder to interpret.

**3. Interaction (additive + cross-group term)**
```
score = sigmoid(bias + f_bert + Σ f_group + h([f_bert, f_g1, ..., f_g5]))
```
Adds a small MLP that sees all group outputs and can model interactions (e.g., "high relevance AND high completeness → bonus"). Most expressive, least interpretable.

### Architecture Details

**BERT Subnet**:
```
cls_embedding (1024-d)
  → Linear(1024, 64) → ReLU                        # Projection
  → Linear(64, 128) → ReLU → Dropout(0.1)          # Hidden 1
  → Linear(128, 64) → ReLU → Dropout(0.1)          # Hidden 2
  → Linear(64, 32)  → ReLU → Dropout(0.1)          # Hidden 3
  → Linear(32, 1)                                    # Output: scalar
```

**Per-Group Rubric Subnet** (one per feature group):
```
group_features (group_size-d)
  → Linear(group_size, 64) → ReLU → Dropout(0.1)   # Hidden 1
  → Linear(64, 32)         → ReLU → Dropout(0.1)   # Hidden 2
  → Linear(32, 1)                                    # Output: scalar
```

### Feature Normalization

Rubric features are normalized per-group before training:
```python
for group_name, features in rubric_groups.items():
    mean = features.mean(dim=0)      # per-feature mean
    std = features.std(dim=0)        # per-feature std
    normalized = (features - mean) / (std + 1e-8)
```

**Save the normalization statistics.** They must be applied identically at inference time. If you normalize at training but not inference (or vice versa), the GAM will produce garbage.

### Training Configuration

```yaml
rubric_gam:
  mode: "additive"                   # additive | gated | interaction

  # Architecture
  bert_proj_dim: 64                  # Project 1024-d CLS to 64-d
  bert_hidden: [128, 64, 32]         # Hidden layers for BERT subnet
  rubric_hidden: [64, 32]            # Hidden layers for each rubric subnet
  interaction_hidden: [16]           # Hidden layers for interaction MLP
  activation: "relu"
  dropout: 0.1

  # Optimizer
  learning_rate: 1.0e-3              # Higher than BERT (much smaller model)
  weight_decay: 1.0e-4
  batch_size: 256

  # Training
  num_epochs: 200                    # Early stopping handles actual duration
  patience: 30                       # Stop if no improvement for 30 epochs
  lr_scheduler: "cosine"             # Cosine annealing

  # Loss
  ranking_alpha: 1.0                 # Pairwise ranking loss
  mae_lambda: 1.0                    # Model selection criterion
```

The GAM is tiny (~400KB) and trains in minutes on CPU. The main risk is overfitting to the training embeddings, which is why we use aggressive early stopping (patience=30).

### What to Monitor

Same metrics as Stage 1 (MSE, MAE, Spearman ρ, satisficer score), plus:

**Feature contribution analysis**: After training, check the average absolute contribution of each group:
```
BERT subnet:       |contribution| = 0.45  (dominant signal — expected)
Relevance group:   |contribution| = 0.12
Type match:        |contribution| = 0.08
Completeness:      |contribution| = 0.05
Quality:           |contribution| = 0.03
Specificity:       |contribution| = 0.02
```

If all rubric groups have near-zero contribution, the GAM is just passing through the BERT signal and the rubric features aren't helping. This might mean:
- Features are too noisy or poorly designed
- Features are redundant with what BERT already captures
- Feature normalization is wrong

If one rubric group dominates (e.g., relevance = 0.40), check whether it's providing genuine signal or a spurious shortcut.

---

## 7. Evaluation and Metrics

### Core Metrics

**MAE (Mean Absolute Error)**: Average |predicted - true| across all items. Measures calibration — can you trust the actual score value?
- Good: < 0.15 (in 0-1 scale, i.e., < 15 points on a 0-100 scale)
- Acceptable: 0.15-0.20
- Poor: > 0.20

**Spearman ρ (Rank Correlation)**: How well does the model's ranking match the LLM's ranking? Computed per-query, then averaged.
- Good: > 0.65
- Acceptable: 0.50-0.65
- Poor: < 0.50

**MSE (Mean Squared Error)**: Penalizes large errors more than MAE. Useful for catching outliers.

### Satisficer Metrics (the ones that matter most)

These directly measure what users care about: "Are the top results good?"

For each query with ≥5 items and ≥1 good item (true score ≥ 0.6):

| Metric | Formula | What it measures |
|--------|---------|-----------------|
| `good_picks` | (good items in predicted top-5) / 5 | Recall of relevant items |
| `bad_picks` | (bad items in predicted top-5) / 5 | Intrusion of irrelevant items |
| `satisficer_score` | good_picks - 2 × bad_picks | Net quality (bad items penalized 2x) |
| `pairwise_accuracy` | (correctly ordered pairs) / (total pairs) | Overall ranking quality |

**Why 2x penalty for bad items?** A bad item in the top results is worse than a missing good item. Users tolerate seeing 4/5 relevant results, but showing 1 irrelevant result in the top 5 destroys trust.

### Per-Site Evaluation

Always break down metrics by site/source:
```
Site                  Spearman ρ    MAE    Satisficer
alltrails             0.72          0.11   0.45
imdb                  0.58          0.16   0.32
nyt_cooking           0.81          0.09   0.62
```

If one site performs much worse, investigate: Does that site have unusual score distribution? Different content types? Fewer training examples?

### Holdout Evaluation

If possible, hold out a large evaluation set (separate from train/val/test) that represents production traffic. This catches overfitting to the test set distribution that you might not notice from standard metrics.

---

## 8. Detecting and Eliminating Spurious Correlations

Spurious correlations are the #1 cause of models that look great in evaluation but fail in production. The model learns a shortcut that happens to correlate with the target in your training data but doesn't generalize.

### Systematic Detection Process

**Step 1: Feature ablation study**

For each rubric feature group, train the GAM with that group zeroed out and measure the impact:

```python
for group in ["relevance", "type_match", "completeness", "quality", "specificity"]:
    # Zero out this group's features
    ablated_features = features.clone()
    ablated_features[group] = 0
    ablated_score = gam(embeddings, ablated_features)

    delta_mae = mae(ablated_score, true) - mae(full_score, true)
    print(f"Removing {group}: MAE increases by {delta_mae:.4f}")
```

If removing a group *improves* MAE, that group is hurting the model — it's learned a spurious pattern.

**Step 2: Correlation audit**

Check correlations between each feature and the target score:
```python
for feature_name in all_features:
    r = np.corrcoef(features[feature_name], scores)[0, 1]
    print(f"{feature_name:30s}  r = {r:+.3f}")
```

Features with |r| > 0.3 deserve scrutiny: is the correlation causal (longer descriptions genuinely are more relevant) or spurious (popular sites happen to have longer descriptions)?

**Step 3: Counterfactual testing**

Create synthetic test cases that isolate individual signals:
- Take a highly relevant item, change its site to a low-scoring site → does the score drop? (If yes: site bias)
- Take an irrelevant item, make its description very long → does the score rise? (If yes: length bias)
- Take an irrelevant item, add query keywords to its description → does the score rise? (If yes: keyword leakage)

**Step 4: Error analysis on the test set**

Sort test items by |predicted - true| (largest errors first). For the top 50 worst predictions:
- What patterns do you see?
- Are certain item types consistently over- or under-scored?
- Do specific query patterns cause problems?

### Common Spurious Correlations and Fixes

| Spurious Signal | How It Manifests | Fix |
|----------------|------------------|-----|
| Site/source identity | Items from popular sites score high | Strip site names from text |
| Description length | Longer = higher score | Truncate, add length as feature |
| Keyword density | More query word mentions = higher | Use exact_query_match sparingly |
| Schema completeness | More fields = higher score | Separate completeness from relevance |
| Recency | Newer items score higher | Add date feature to GAM explicitly |
| Language/formatting | Well-formatted HTML → better text → higher | Normalize text cleaning |

### The Site Name Problem (NLWeb Case Study)

In NLWeb's initial training, the model with site names in the text (`modernbert_no_sites` is actually a misnomer — it was an early attempt) learned that "imdb" in the description meant "movie-related query → high score." When tested on a new movie database site, the model failed badly because it had never seen that site name.

The fix was simple: strip all site names and domain references from the `item_text` before tokenization. This forced the model to learn from *content* rather than *source identity*. The resulting model (`modernbert_large_pure`) generalized much better to unseen sites.

**General rule**: If you can predict the score from metadata alone (without reading the actual content), your model has a shortcut problem.

---

## 9. Production Inference

### Inference Pipeline

```python
class RelevanceScorer:
    def __init__(self, bert_checkpoint, gam_checkpoint):
        # Load BERT model + tokenizer
        self.bert_model = load_bert(bert_checkpoint)
        self.tokenizer = AutoTokenizer.from_pretrained("answerdotai/ModernBERT-large")

        # Load GAM model + normalization stats
        checkpoint = torch.load(gam_checkpoint)
        self.gam_model = RubricGAM(...)
        self.gam_model.load_state_dict(checkpoint["model_state_dict"])
        self.norm_stats = checkpoint["norm_stats"]

    def score(self, query, items):
        # 1. Build text inputs
        texts = [f"{query} [SEP] {build_readable_text(item)}" for item in items]

        # 2. Tokenize
        encoded = self.tokenizer(texts, max_length=1024, padding=True,
                                 truncation=True, return_tensors="pt")

        # 3. Get BERT embeddings
        with torch.no_grad():
            embeddings = self.bert_model.get_embeddings(
                encoded["input_ids"], encoded["attention_mask"])

        # 4. Compute rubric features
        rubric = [compute_rubric_features(query, item) for item in items]
        rubric_tensor = normalize(rubric, self.norm_stats)

        # 5. Score with GAM
        with torch.no_grad():
            scores = self.gam_model(embeddings, rubric_tensor)

        # 6. Convert to 0-100
        return (scores * 100).clamp(0, 100).round().tolist()
```

### Performance Characteristics

| Items | GPU (A10) | CPU | MPS (M2) |
|-------|-----------|-----|----------|
| 1 | ~5ms | ~50ms | ~15ms |
| 10 | ~8ms | ~200ms | ~40ms |
| 25 | ~15ms | ~500ms | ~80ms |
| 100 | ~50ms | ~2s | ~250ms |

The bottleneck is BERT tokenization + forward pass. The GAM adds <1ms regardless of batch size.

### Async Integration

Because BERT inference is CPU/GPU-bound and can block an async event loop, wrap the scoring call:

```python
results = await asyncio.to_thread(scorer.score, query, items)
```

### Interpretability at Inference Time

Request per-group contribution breakdowns:

```python
results = scorer.score(query, items, return_rubric_scores=True)
# Returns:
# {
#   "score": 82,
#   "rubric_scores": {
#     "bert": 0.78,           # BERT's semantic signal
#     "relevance": 0.12,      # Lexical overlap contribution
#     "type_match": 0.08,     # Type alignment contribution
#     "completeness": 0.04,   # Metadata richness contribution
#     "quality": 0.02,        # Content quality contribution
#     "specificity": 0.01     # Query/item complexity contribution
#   }
# }
```

This is invaluable for debugging: if BERT says 0.78 but the final score seems wrong, you can see which rubric group is pushing it in the wrong direction.

---

## 10. Common Failure Modes and How to Fix Them

### "Everything scores 70-85" (No Discrimination)

**Cause**: Score distribution in training data is narrow, or the model learned the mean.

**Fix**:
1. Check training data distribution (Section 4.1)
2. Add hard negatives
3. Use `--bad-heavy 3.0` sampling
4. Increase `score_diff_alpha` to emphasize pairwise differences

### "Scores are spread but ordering is wrong"

**Cause**: The model learned to spread scores but not to rank correctly. Often caused by misaligned pairwise loss weights.

**Fix**:
1. Increase `ranking_alpha` (pairwise ranking loss)
2. Increase `lambda_alpha` (boundary-focused loss)
3. Check for data quality issues — are the LLM ground-truth scores consistent?

### "Good on validation, bad in production"

**Cause**: Distribution mismatch between training data and production traffic.

**Fix**:
1. Audit production queries that perform poorly
2. Add representative production queries to training data
3. Check for site/source bias (Section 8)
4. Evaluate on a holdout set that mirrors production traffic

### "GAM rubric features don't help"

**Cause**: Features are redundant with BERT, or normalization is wrong.

**Fix**:
1. Check normalization stats — are they reasonable?
2. Feature ablation study (Section 8)
3. Design features that capture information BERT can't see (structural metadata, type alignment)
4. Make sure features are computed consistently between training and inference

### "BERT checkpoint works, but retraining produces worse results"

**Cause**: Training instability, different data sampling, or accidental hyperparameter changes.

**Fix**:
1. Set a fixed random seed
2. Compare training curves (loss, metrics) between old and new runs
3. Check that the data preparation pipeline hasn't changed
4. Verify that the data distribution hasn't drifted
5. **Always retrain the GAM** when you retrain BERT — embedding spaces from different checkpoints are not compatible

### "Model is great on easy queries, terrible on hard ones"

**Cause**: Easy queries dominate training data; model hasn't learned to handle queries requiring world knowledge.

**Fix**:
1. Oversample hard queries (difficulty 4-5)
2. Create synthetic hard examples
3. Accept that some queries are beyond BERT's capabilities and plan for LLM fallback
4. Consider a hybrid approach: use BERT+GAM for easy queries, LLM for hard ones (route based on query difficulty estimate)

---

## 11. Appendix: Configuration Reference

### Full Training Configuration

```yaml
# === Data ===
data:
  scores_file: "path/to/llm_scores.json"
  retrieval_file: "path/to/retrieval_results.json"
  output_dir: "path/to/prepared_data/"
  strip_sites: true                      # Remove site names from item text

# === Stage 1: ModernBERT ===
modernbert:
  model_name: "answerdotai/ModernBERT-large"
  output_dir: "./checkpoints/modernbert_large_pure"
  pure_text: true

  learning_rate: 1.0e-5
  weight_decay: 0.01
  warmup_ratio: 0.1
  num_epochs: 5

  per_device_train_batch_size: 4
  per_device_eval_batch_size: 8
  gradient_accumulation_steps: 8

  loss: "mse"
  ranking_alpha: 0.0
  score_diff_alpha: 1.0
  lambda_alpha: 0.5

  max_seq_length: 1024
  mae_lambda: 1.0

# === Stage 2: Rubric GAM ===
rubric_gam:
  output_dir: "./checkpoints/rubric_gam"
  mode: "additive"                       # additive | gated | interaction

  bert_proj_dim: 64
  bert_hidden: [128, 64, 32]
  rubric_hidden: [64, 32]
  interaction_hidden: [16]
  activation: "relu"
  dropout: 0.1

  learning_rate: 1.0e-3
  weight_decay: 1.0e-4
  num_epochs: 200
  batch_size: 256
  patience: 30
  lr_scheduler: "cosine"

  ranking_alpha: 1.0
  score_diff_alpha: 0.0
  lambda_alpha: 0.0
  mae_lambda: 1.0
```

### Rubric Feature Groups

```yaml
rubric_groups:
  relevance:
    - query_term_coverage
    - title_query_overlap
    - exact_query_match
    - query_item_word_overlap
  type_match:
    - type_match
  completeness:
    - description_length
    - schema_field_count
    - has_rating
    - has_price
    - has_image
  quality:
    - has_date
    - content_word_count
    - has_author
  specificity:
    - query_word_count
    - name_word_count
    - difficulty
```

### Satisficer Configuration

```yaml
satisficer:
  k: 5                                  # Top-k items to evaluate
  good_threshold: 0.6                   # Score ≥ 0.6 = "good" item
  bad_threshold: 0.3                    # Score ≤ 0.3 = "bad" item
  bad_penalty_weight: 2.0               # bad_picks multiplied by this
```

---

## Checklist: Before You Train

- [ ] 40K+ scored (query, item) pairs from a strong LLM
- [ ] Manual audit of 100+ scored pairs for quality
- [ ] Score distribution covers full 0-100 range (check per-decile counts)
- [ ] Site/source identifiers stripped from item text
- [ ] Train/val/test split by query (not by example)
- [ ] At least 30% of queries are "hard" (low lexical overlap)
- [ ] Rubric features designed for your domain
- [ ] Feature correlation audit completed
- [ ] GPU with ≥40GB VRAM available for Stage 1

## Checklist: After You Train

- [ ] Satisficer score > 0.30 on test set
- [ ] Bad picks < 0.10 on test set
- [ ] Per-site metrics are consistent (no one site much worse)
- [ ] Feature contribution analysis shows BERT dominant, rubric features contributing
- [ ] Counterfactual tests pass (no site bias, length bias, keyword leakage)
- [ ] GAM normalization stats saved and used at inference
- [ ] End-to-end inference test produces reasonable scores

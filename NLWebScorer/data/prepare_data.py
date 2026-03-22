"""Convert ModelRouter GPT-4.1 scoring data into training format for NLWebScorer.

Reads:  ModelRouter/nlweb_router/data/scores_azure_oai_gpt-4.1.json
        ModelRouter/nlweb_router/data/retrieval_results.json
Writes: data/prepared/{train,val,test}.jsonl

Each training example includes rubric features that decompose GPT-4.1's
relevance assessment into measurable components:
  - Relevance: query term coverage, exact match, title overlap
  - Completeness: description length, schema field count, structured data
  - Quality: has rating, has date, content depth

Options:
  --difficulty 4,5    Only include queries at these difficulty levels
  --holdout-dir DIR   Mix in holdout data (retrieval + scores) from this directory
  --holdout-train-ratio 0.6  Fraction of holdout queries to use for training
  --output-dir DIR    Override output directory
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

import yaml


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = Path(__file__).resolve().parents[1] / "config" / "training_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


# ── Rubric feature extraction ─────────────────────────────────────────────────

# Schema types that match different query intents
RECIPE_TYPES = {"Recipe"}
PRODUCT_TYPES = {"Product", "ProductGroup", "ProductModel"}
MEDIA_TYPES = {"Movie", "TVSeries", "TVEpisode", "VideoObject", "PodcastEpisode"}
EVENT_TYPES = {"Event", "BusinessEvent", "EducationEvent", "MusicEvent",
               "SocialEvent", "SportsEvent", "Festival"}
ARTICLE_TYPES = {"Article", "NewsArticle", "BlogPosting", "ScholarlyArticle"}
PLACE_TYPES = {"LocalBusiness", "FoodEstablishment", "House",
               "SingleFamilyResidence", "RealEstateListing"}

# Query intent keywords
RECIPE_KEYWORDS = {"recipe", "cook", "bake", "make", "prepare", "ingredients"}
PRODUCT_KEYWORDS = {"buy", "price", "review", "best", "cheap", "compare", "vs"}
EVENT_KEYWORDS = {"event", "concert", "show", "festival", "conference", "meetup"}
HOW_TO_KEYWORDS = {"how", "tutorial", "guide", "steps", "learn", "beginner"}


def _parse_schema(schema_json_str: str) -> dict:
    """Parse schema.org JSON, handling lists and errors."""
    if not schema_json_str:
        return {}
    try:
        obj = json.loads(schema_json_str) if isinstance(schema_json_str, str) else schema_json_str
        if isinstance(obj, list):
            obj = obj[0] if obj else {}
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def extract_schema_type(schema_json_str: str) -> str:
    """Extract @type from schema.org JSON."""
    obj = _parse_schema(schema_json_str)
    return obj.get("@type", "Unknown")


def compute_rubric_features(query: str, name: str, schema_json_str: str) -> dict:
    """Compute rubric features that mirror GPT-4.1's relevance assessment.

    Returns a dict of float features, all cheap to compute from the schema JSON.
    """
    q_words = set(query.lower().split())
    schema = _parse_schema(schema_json_str)
    # Use readable text for coverage checks, not raw JSON with keys/URLs
    item_text = _extract_readable_text(schema_json_str, name) if schema_json_str else name
    item_text_lower = item_text.lower()
    name_lower = name.lower()
    n_words = set(name_lower.split())

    # ── 1. RELEVANCE: Does the item answer the query? ──────────────────────

    # Query term coverage: fraction of query words found in item text (directional)
    if q_words:
        query_term_coverage = sum(1 for w in q_words if w in item_text_lower) / len(q_words)
    else:
        query_term_coverage = 0.0

    # Title-query overlap: fraction of query words in the item's name/title
    if q_words and n_words:
        title_query_overlap = len(q_words & n_words) / len(q_words)
    else:
        title_query_overlap = 0.0

    # Exact query match: does the full query appear as substring?
    exact_query_match = 1.0 if query.lower() in item_text_lower else 0.0

    # Bidirectional Jaccard (original feature, kept for compatibility)
    if q_words and n_words:
        query_item_word_overlap = len(q_words & n_words) / len(q_words | n_words)
    else:
        query_item_word_overlap = 0.0

    # ── 2. TYPE MATCH: Is it the right kind of content? ────────────────────

    schema_type = schema.get("@type", "Unknown")
    if isinstance(schema_type, list):
        schema_type = schema_type[0] if schema_type else "Unknown"

    # Query-schema type alignment score
    type_match = 0.0
    if q_words & RECIPE_KEYWORDS and schema_type in RECIPE_TYPES:
        type_match = 1.0
    elif q_words & PRODUCT_KEYWORDS and schema_type in PRODUCT_TYPES:
        type_match = 1.0
    elif q_words & EVENT_KEYWORDS and schema_type in EVENT_TYPES:
        type_match = 1.0
    elif q_words & HOW_TO_KEYWORDS and schema_type in {"HowTo", "HowToStep"}:
        type_match = 1.0
    elif schema_type in ARTICLE_TYPES:
        type_match = 0.8  # articles are broadly useful for informational queries
    elif schema_type in PLACE_TYPES:
        type_match = 0.8 if q_words & {"near", "restaurant", "store", "shop", "place", "hotel", "where"} else 0.5
    elif schema_type != "Unknown":
        type_match = 0.5  # has a type, just not a strong match

    # ── 3. COMPLETENESS: Is the item comprehensive? ────────────────────────

    # Description length (chars)
    description = schema.get("description", "")
    if isinstance(description, list):
        description = " ".join(str(d) for d in description)
    description_length = len(str(description))

    # Schema field count (number of non-@ fields filled)
    schema_fields = [k for k in schema.keys() if not k.startswith("@")]
    schema_field_count = len(schema_fields)

    # Has structured data signals
    has_rating = 1.0 if "aggregateRating" in schema or "review" in schema else 0.0
    has_price = 1.0 if "offers" in schema or "price" in schema else 0.0
    has_image = 1.0 if "image" in schema or "thumbnailUrl" in schema else 0.0

    # ── 4. QUALITY: Is this a high-quality item? ───────────────────────────

    # Has date (freshness signal)
    has_date = 1.0 if any(k in schema for k in
                          ["datePublished", "dateModified", "uploadDate",
                           "startDate", "dateListed"]) else 0.0

    # Content depth: word count of description
    content_word_count = len(str(description).split())

    # Has author/publisher (authority signal)
    has_author = 1.0 if "author" in schema or "publisher" in schema or "creator" in schema else 0.0

    # ── 5. SPECIFICITY: Is the item at the right level of detail? ──────────

    # Query word count (proxy for query specificity)
    query_word_count = len(q_words)

    # Name length relative to query (very short names = generic items)
    name_word_count = len(n_words)

    return {
        # Relevance
        "query_term_coverage": query_term_coverage,
        "title_query_overlap": title_query_overlap,
        "exact_query_match": exact_query_match,
        "query_item_word_overlap": query_item_word_overlap,
        # Type match
        "type_match": type_match,
        # Completeness
        "description_length": float(description_length),
        "schema_field_count": float(schema_field_count),
        "has_rating": has_rating,
        "has_price": has_price,
        "has_image": has_image,
        # Quality
        "has_date": has_date,
        "content_word_count": float(content_word_count),
        "has_author": has_author,
        # Specificity
        "query_word_count": float(query_word_count),
        "name_word_count": float(name_word_count),
    }


# ── Data loading and preparation ──────────────────────────────────────────────

def _extract_readable_text(schema_json_str: str, name: str) -> str:
    """Extract human-readable text from schema JSON, avoiding noise like URLs and JSON syntax."""
    schema = _parse_schema(schema_json_str)
    if not schema:
        return name

    parts = []

    # Name / headline
    title = schema.get("name", schema.get("headline", ""))
    if title:
        parts.append(str(title))

    # Description
    desc = schema.get("description", "")
    if isinstance(desc, list):
        desc = " ".join(str(d) for d in desc)
    if desc:
        parts.append(str(desc))

    # Type
    stype = schema.get("@type", "")
    if stype and stype != "Unknown":
        parts.append(f"Type: {stype}")

    # Key content fields (text-heavy, skip URLs and nested objects)
    TEXT_FIELDS = [
        "articleBody", "text", "abstract", "reviewBody",
        "recipeInstructions", "recipeIngredient", "keywords",
        "about", "genre", "category", "brand",
    ]
    for field in TEXT_FIELDS:
        val = schema.get(field)
        if val is None:
            continue
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val if isinstance(v, (str, int, float)))
        if isinstance(val, str) and not val.startswith("http"):
            parts.append(str(val))

    # Author / publisher (just the name, not the full object)
    for field in ("author", "publisher", "creator"):
        val = schema.get(field)
        if isinstance(val, dict):
            aname = val.get("name", "")
            if aname:
                parts.append(f"{field}: {aname}")
        elif isinstance(val, str):
            parts.append(f"{field}: {val}")

    # Rating summary
    rating = schema.get("aggregateRating")
    if isinstance(rating, dict):
        rv = rating.get("ratingValue", "")
        rc = rating.get("ratingCount", rating.get("reviewCount", ""))
        if rv:
            parts.append(f"Rating: {rv}" + (f" ({rc} reviews)" if rc else ""))

    # Price
    offers = schema.get("offers")
    if isinstance(offers, dict):
        price = offers.get("price", "")
        currency = offers.get("priceCurrency", "")
        if price:
            parts.append(f"Price: {currency}{price}")
    elif isinstance(offers, list) and offers:
        price = offers[0].get("price", "")
        currency = offers[0].get("priceCurrency", "")
        if price:
            parts.append(f"Price: {currency}{price}")

    text = " | ".join(parts) if parts else name
    return text


import re

# Site name patterns to strip from queries for site-agnostic training.
# Order matters: longer patterns first to avoid partial matches.
SITE_NAME_PATTERNS = [
    r"\bcommon\s*sense\s*media\b",
    r"\bhebbar'?s?\s*kitchen\b",
    r"\bnew\s+york\s+times\b",
    r"\bmediterranean\s+dish\b",
    r"\bcrate\s*(?:and|&)\s*barrel\b",
    r"\bserious\s*eats\b",
    r"\btrip\s*advisor\b",
    r"\bthe\s+wirecutter\b",
    r"\bbackcountry(?:\.com)?\b",
    r"\beventbrite\b",
    r"\bwirecutter\b",
    r"\balltrails\b",
    r"\ball\s+trails\b",
    r"\bnyt\s+cooking\b",
    r"\bnytimes\b",
    r"\bzillow\b",
    r"\bhebbar\b",
    r"\bimdb\b",
    r"\bnpr\b",
    r"\bnyt\b",
]
_SITE_RE = re.compile("|".join(SITE_NAME_PATTERNS), re.IGNORECASE)


def strip_site_names(text: str) -> str:
    """Remove site name references, URLs, and publisher info for site-agnostic training."""
    result = _SITE_RE.sub("", text)
    # Remove URLs (https://..., http://...)
    result = re.sub(r"https?://[^\s,\")\]]+", "", result)
    # Remove "publisher: <anything>" fields
    result = re.sub(r"\bpublisher:\s*[^|]+", "", result, flags=re.IGNORECASE)
    # Clean up leftover artifacts: double spaces, leading "on ", "from ", etc.
    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"^(on|from|at|in|the)\s+", "", result, flags=re.IGNORECASE).strip()
    # Remove dangling prepositions at the end
    result = re.sub(r"\s+(on|from|at|in)$", "", result, flags=re.IGNORECASE).strip()
    return result


def build_item_text(query: str, item: dict, strip_sites: bool = False) -> str:
    """Build the text input for ModernBERT: [query] [SEP] [readable item text]."""
    schema_json = item.get("schema_json", "")
    name = item.get("name", "")
    description = _extract_readable_text(schema_json, name)
    if len(description) > 4000:
        description = description[:4000]
    if strip_sites:
        query = strip_site_names(query)
        description = strip_site_names(description)
    return f"{query} [SEP] {description}"


def load_scores(scores_path: str) -> list[dict]:
    with open(scores_path) as f:
        return json.load(f)


def load_retrieval(retrieval_path: str) -> dict:
    """Load retrieval results, indexed by (site, query, url) for schema_json lookup."""
    try:
        with open(retrieval_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}

    index = {}
    for entry in data:
        site = entry["site"]
        query = entry["query"]
        for item in entry.get("items", []):
            key = (site, query, item.get("url", ""))
            index[key] = item
    return index


def load_difficulty_mapping(retrieval_path: str) -> dict:
    try:
        with open(retrieval_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    return {(e["site"], e["query"]): e.get("difficulty", 0) for e in data}


def _build_example(query: str, name: str, schema_json: str, score: float,
                   schema_type: str, difficulty: int, site: str,
                   item: dict, normalize: bool) -> dict:
    """Build a single training example with all rubric features."""
    item_with_schema = {**item, "schema_json": schema_json}
    item_text = build_item_text(query, item_with_schema)
    normalized_score = score / 100.0 if normalize else float(score)

    rubric = compute_rubric_features(query, name, schema_json)

    example = {
        "query": query,
        "item_text": item_text,
        "score": normalized_score,
        "schema_type": schema_type,
        "difficulty": difficulty,
        "site": site,
        # Legacy features (kept for backward compat)
        "query_length": len(query),
        "item_name_length": len(name),
    }
    example.update(rubric)
    return example


def prepare_examples(scores_data: list[dict], retrieval_index: dict,
                     difficulty_map: dict = None,
                     normalize: bool = True) -> list[dict]:
    """Convert scoring data into flat training examples."""
    examples = []
    for entry in scores_data:
        site = entry["site"]
        query = entry["query"]

        if difficulty_map:
            difficulty = difficulty_map.get((site, query), entry.get("difficulty", 0))
        else:
            difficulty = entry.get("difficulty", 0)
        if difficulty is None:
            difficulty = 0

        for item in entry.get("items", []):
            score = item.get("score", -1)
            if score < 0:
                continue

            url = item.get("url", "")
            name = item.get("name", "")

            retrieval_item = retrieval_index.get((site, query, url), {})
            schema_json = retrieval_item.get("schema_json", "")
            schema_type = extract_schema_type(schema_json) if schema_json else "Unknown"

            examples.append(_build_example(
                query, name, schema_json, score,
                schema_type, difficulty, site, item, normalize))

    return examples


def prepare_holdout_examples(holdout_dir: Path, normalize: bool = True) -> list[dict]:
    """Prepare examples from holdout data (retrieval + scores files)."""
    retrieval_path = holdout_dir / "holdout_retrieval_west.json"
    scores_path = holdout_dir / "holdout_scores_west.json"

    if not retrieval_path.exists() or not scores_path.exists():
        print(f"  Holdout files not found in {holdout_dir}")
        return []

    with open(retrieval_path) as f:
        retrieval_data = json.load(f)
    with open(scores_path) as f:
        scores_data = json.load(f)

    schema_lookup = {}
    for entry in retrieval_data:
        for item in entry.get("items", []):
            schema_lookup[item["url"]] = item.get("schema_json", "")

    examples = []
    for entry in scores_data:
        site = entry["site"]
        query = entry["query"]
        difficulty = entry.get("difficulty", 0)
        if difficulty is None:
            difficulty = 0

        for item in entry.get("items", []):
            score = item.get("score", -1)
            if score < 0:
                continue

            url = item.get("url", "")
            name = item.get("name", "")
            schema_json = schema_lookup.get(url, "")
            schema_type = extract_schema_type(schema_json) if schema_json else "Unknown"

            examples.append(_build_example(
                query, name, schema_json, score,
                schema_type, difficulty, site, item, normalize))

    return examples


def prepare_hard_negative_examples(hard_neg_dir: Path,
                                   retrieval_index: dict = None,
                                   normalize: bool = True) -> list[dict]:
    """Prepare training examples from hard negative mining output.

    Hard negatives use the ORIGINAL query for scoring but items were retrieved
    via partial queries. The key is (site, original_query, url).
    """
    retrieval_path = hard_neg_dir / "hard_neg_retrieval.json"
    scores_path = hard_neg_dir / "hard_neg_scores.json"

    if not scores_path.exists():
        print(f"  Hard negative scores not found: {scores_path}")
        return []
    if not retrieval_path.exists():
        print(f"  Hard negative retrieval not found: {retrieval_path}")
        return []

    # Build schema_json lookup from retrieval file
    with open(retrieval_path) as f:
        retrieval_data = json.load(f)
    schema_lookup = {}
    for entry in retrieval_data:
        for item in entry.get("items", []):
            schema_lookup[item["url"]] = item.get("schema_json", "")

    with open(scores_path) as f:
        scores_data = json.load(f)

    examples = []
    for entry in scores_data:
        site = entry["site"]
        query = entry["original_query"]  # score against original, not partial
        difficulty = 0  # hard negatives don't have difficulty level

        for item in entry.get("items", []):
            score = item.get("score", -1)
            if score < 0:
                continue

            url = item.get("url", "")
            name = item.get("name", "")
            schema_json = schema_lookup.get(url, "")
            schema_type = extract_schema_type(schema_json) if schema_json else "Unknown"

            examples.append(_build_example(
                query, name, schema_json, score,
                schema_type, difficulty, site, item, normalize))

    return examples


def split_data(examples: list[dict], train_ratio: float, val_ratio: float,
               seed: int = 42) -> tuple[list, list, list]:
    """Split by query to avoid data leakage."""
    query_groups = {}
    for ex in examples:
        key = (ex["site"], ex["query"])
        query_groups.setdefault(key, []).append(ex)

    keys = sorted(query_groups.keys())
    random.seed(seed)
    random.shuffle(keys)

    n = len(keys)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    train_keys = keys[:n_train]
    val_keys = keys[n_train:n_train + n_val]
    test_keys = keys[n_train + n_val:]

    train = [ex for k in train_keys for ex in query_groups[k]]
    val = [ex for k in val_keys for ex in query_groups[k]]
    test = [ex for k in test_keys for ex in query_groups[k]]

    return train, val, test


def write_jsonl(data: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
    print(f"  Wrote {len(data)} examples to {path}")


def main():
    parser = argparse.ArgumentParser(description="Prepare NLWebScorer training data")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--scores-path", type=str, default=None)
    parser.add_argument("--retrieval-path", type=str, default=None)
    parser.add_argument("--difficulty", type=str, default=None,
                        help="Comma-separated difficulty levels (e.g., '4,5')")
    parser.add_argument("--holdout-dir", type=str, default=None)
    parser.add_argument("--holdout-sites", type=str, default=None)
    parser.add_argument("--holdout-train-ratio", type=float, default=0.6)
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--min-query-max-score", type=float, default=None,
                        help="Remove query-site pairs where max score < this threshold (e.g., 0.5)")
    parser.add_argument("--hard-negatives", type=str, default=None,
                        help="Path to hard_negatives dir (with hard_neg_retrieval.json and hard_neg_scores.json)")
    parser.add_argument("--balance", action="store_true",
                        help="Balance examples to have equal count per score decile (0-9, 10-19, ..., 90-100)")
    parser.add_argument("--bad-heavy", type=float, default=None,
                        help="Oversample low-score deciles (0-40) by this factor vs high-score. E.g., 3.0 means 3x more bad examples per decile than good.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    data_cfg = cfg["data"]
    bert_cfg = cfg["modernbert"]

    scores_path = args.scores_path or data_cfg["scores_path"]
    retrieval_path = args.retrieval_path or data_cfg["retrieval_path"]

    project_root = Path(__file__).resolve().parents[1]
    scores_path = (project_root / scores_path).resolve()
    retrieval_path = (project_root / retrieval_path).resolve()

    print(f"Loading difficulty mapping from {retrieval_path}")
    difficulty_map = load_difficulty_mapping(str(retrieval_path))
    print(f"  {len(difficulty_map)} query-difficulty mappings")

    print(f"Loading scores from {scores_path}")
    scores_data = load_scores(str(scores_path))

    print(f"Loading retrieval data from {retrieval_path}")
    retrieval_index = load_retrieval(str(retrieval_path))
    print(f"  Retrieval index: {len(retrieval_index)} items")

    print("Preparing training examples with rubric features...")
    examples = prepare_examples(scores_data, retrieval_index,
                                difficulty_map=difficulty_map,
                                normalize=bert_cfg.get("normalize_scores", True))
    print(f"  Total examples: {len(examples)}")

    if args.difficulty:
        levels = [int(d.strip()) for d in args.difficulty.split(",")]
        before = len(examples)
        examples = [ex for ex in examples if ex["difficulty"] in levels]
        print(f"  Filtered to difficulty {levels}: {len(examples)} examples (was {before})")

    if args.min_query_max_score is not None:
        threshold = args.min_query_max_score
        # Group by (site, query) and find max score per group
        query_max = {}
        for ex in examples:
            key = (ex["site"], ex["query"])
            query_max[key] = max(query_max.get(key, 0.0), ex["score"])
        answerable = {k for k, mx in query_max.items() if mx >= threshold}
        removed = {k for k, mx in query_max.items() if mx < threshold}
        before = len(examples)
        examples = [ex for ex in examples
                    if (ex["site"], ex["query"]) in answerable]
        print(f"  Filtered queries with max_score < {threshold}: "
              f"removed {len(removed)} queries, "
              f"{before - len(examples)} examples → {len(examples)} remaining")
        if removed:
            for site, query in sorted(removed):
                print(f"    dropped: {site} / {query[:60]} (max={query_max[(site, query)]:.2f})")

    holdout_eval_examples = []
    if args.holdout_dir:
        holdout_dir = Path(args.holdout_dir)
        print(f"Loading holdout data from {holdout_dir}")
        holdout_examples = prepare_holdout_examples(holdout_dir,
                                                     normalize=bert_cfg.get("normalize_scores", True))

        if args.holdout_sites:
            sites = [s.strip() for s in args.holdout_sites.split(",")]
            holdout_examples = [ex for ex in holdout_examples if ex["site"] in sites]
            print(f"  Filtered holdout to sites {sites}: {len(holdout_examples)} examples")

        holdout_groups = {}
        for ex in holdout_examples:
            key = (ex["site"], ex["query"])
            holdout_groups.setdefault(key, []).append(ex)

        holdout_keys = sorted(holdout_groups.keys())
        random.seed(42)
        random.shuffle(holdout_keys)

        n_train = int(len(holdout_keys) * args.holdout_train_ratio)
        train_keys = holdout_keys[:n_train]
        eval_keys = holdout_keys[n_train:]

        holdout_train = [ex for k in train_keys for ex in holdout_groups[k]]
        holdout_eval_examples = [ex for k in eval_keys for ex in holdout_groups[k]]

        print(f"  Holdout train queries: {len(train_keys)} ({len(holdout_train)} items)")
        print(f"  Holdout eval queries: {len(eval_keys)} ({len(holdout_eval_examples)} items)")

        examples.extend(holdout_train)
        print(f"  Total after mixing: {len(examples)} examples")

    # Merge hard negatives if provided
    if args.hard_negatives:
        hard_neg_dir = Path(args.hard_negatives)
        print(f"\nLoading hard negatives from {hard_neg_dir}")
        hard_neg_examples = prepare_hard_negative_examples(
            hard_neg_dir, normalize=bert_cfg.get("normalize_scores", True))
        if hard_neg_examples:
            # Show score distribution of hard negatives
            hn_scores = [ex["score"] for ex in hard_neg_examples]
            low = sum(1 for s in hn_scores if s < 0.5)
            mid = sum(1 for s in hn_scores if 0.5 <= s < 0.75)
            high = sum(1 for s in hn_scores if s >= 0.75)
            print(f"  Hard negatives: {len(hard_neg_examples)} examples")
            print(f"    Score < 50: {low} ({low/len(hn_scores)*100:.0f}%)")
            print(f"    Score 50-74: {mid} ({mid/len(hn_scores)*100:.0f}%)")
            print(f"    Score >= 75: {high} ({high/len(hn_scores)*100:.0f}%)")
            examples.extend(hard_neg_examples)
            print(f"  Total after adding hard negatives: {len(examples)} examples")

    # Balance examples to equal count per score decile
    if args.balance:
        deciles = {i: [] for i in range(10)}  # 0-9, 10-19, ..., 90-100
        for ex in examples:
            bucket = min(int(ex["score"] * 10), 9)  # scores are 0-1 normalized
            deciles[bucket].append(ex)

        print(f"\nDecile distribution before balancing:")
        for i in range(10):
            lo, hi = i * 10, (i + 1) * 10
            print(f"  {lo:>3}-{hi:<3}: {len(deciles[i]):>6}")

        min_count = min(len(v) for v in deciles.values() if v)
        print(f"\n  Smallest decile: {min_count} — sampling {min_count} per decile")

        random.seed(42)
        examples = []
        for i in range(10):
            if len(deciles[i]) <= min_count:
                examples.extend(deciles[i])
            else:
                examples.extend(random.sample(deciles[i], min_count))

        random.shuffle(examples)
        print(f"  Balanced total: {len(examples)} examples ({min_count} × 10 deciles)")

    if args.bad_heavy:
        factor = args.bad_heavy
        deciles = {i: [] for i in range(10)}
        for ex in examples:
            bucket = min(int(ex["score"] * 10), 9)
            deciles[bucket].append(ex)

        # Deciles 0-3 (score 0-40) get full factor, 4-5 get partial, 6-9 get 1x
        weights = {}
        for i in range(10):
            if i <= 3:
                weights[i] = factor
            elif i <= 5:
                weights[i] = (factor + 1) / 2  # midpoint
            else:
                weights[i] = 1.0

        # Find base count: smallest decile at 1x weight
        base_count = min(len(deciles[i]) for i in range(10) if deciles[i])
        random.seed(42)
        examples = []
        print(f"\nBad-heavy sampling (factor={factor}):")
        for i in range(10):
            target = min(int(base_count * weights[i]), len(deciles[i]))
            if target >= len(deciles[i]):
                sampled = deciles[i]
            else:
                sampled = random.sample(deciles[i], target)
            examples.extend(sampled)
            lo, hi = i * 10, (i + 1) * 10
            print(f"  {lo:>3}-{hi:<3}: {len(sampled):>6} (weight={weights[i]:.1f}x)")

        random.shuffle(examples)
        print(f"  Bad-heavy total: {len(examples)} examples")

    print("Splitting data...")
    train, val, test = split_data(
        examples, data_cfg["train_ratio"], data_cfg["val_ratio"])

    out_dir = Path(args.output_dir) if args.output_dir else project_root / data_cfg["prepared_dir"]
    write_jsonl(train, out_dir / "train.jsonl")
    write_jsonl(val, out_dir / "val.jsonl")
    write_jsonl(test, out_dir / "test.jsonl")

    if holdout_eval_examples:
        write_jsonl(holdout_eval_examples, out_dir / "holdout_eval.jsonl")

    # Schema type mapping
    for ex in examples:
        if isinstance(ex["schema_type"], list):
            ex["schema_type"] = ex["schema_type"][0] if ex["schema_type"] else "Unknown"
    schema_types = sorted(set(ex["schema_type"] for ex in examples))
    mapping = {t: i for i, t in enumerate(schema_types)}
    mapping_path = out_dir / "schema_type_mapping.json"
    with open(mapping_path, "w") as f:
        json.dump(mapping, f, indent=2)
    print(f"  Schema types ({len(mapping)}): {schema_types}")

    # Summary with rubric feature stats
    print("\n--- Summary ---")
    site_counts = {}
    diff_counts = {}
    for ex in examples:
        site_counts[ex["site"]] = site_counts.get(ex["site"], 0) + 1
        diff_counts[ex["difficulty"]] = diff_counts.get(ex["difficulty"], 0) + 1
    print("By site:")
    for s in sorted(site_counts.keys()):
        print(f"  {s}: {site_counts[s]}")
    print("By difficulty:")
    for d in sorted(diff_counts.keys()):
        print(f"  Level {d}: {diff_counts[d]}")

    # Rubric feature means
    rubric_keys = ["query_term_coverage", "title_query_overlap", "exact_query_match",
                   "type_match", "description_length", "schema_field_count",
                   "has_rating", "has_date", "has_author", "content_word_count"]
    print("Rubric feature means:")
    for k in rubric_keys:
        vals = [ex.get(k, 0) for ex in examples]
        print(f"  {k:25s}: {sum(vals)/len(vals):.3f}")

    print("Done.")


if __name__ == "__main__":
    main()

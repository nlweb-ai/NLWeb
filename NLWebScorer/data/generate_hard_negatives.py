"""Generate training data for NLWebScorer.

Two modes:
  1. Hard negatives (default): Takes existing complex queries, decomposes into
     partial queries for retrieval, scores against the original complex query.
     Items retrieved via partial queries often score low — teaching BERT what
     "not relevant despite surface similarity" looks like.

  2. Synthetic queries (--generate-queries N): GPT-4.1 generates N natural,
     complex queries per site (the kind a user would type into a chatbot).
     Items are retrieved and scored directly. Produces a natural distribution
     across all score ranges.

Features:
  - Auto-resumes: always picks up where it left off
  - Saves progress every query (safe to Ctrl-C anytime)

Usage:
    cd NLWebScorer
    source /path/to/set_keys.sh   # need Azure credentials

    # Hard negative mode (decompose existing queries):
    python -m data.generate_hard_negatives
    python -m data.generate_hard_negatives --total 100 --sites imdb

    # Synthetic query mode (generate new queries):
    python -m data.generate_hard_negatives --generate-queries 20
    python -m data.generate_hard_negatives --generate-queries 30 --sites seriouseats,imdb
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load env
load_dotenv(Path("/Users/rvguha/code/satisficer/.env"), override=True)

sys.stdout.reconfigure(line_buffering=True)

SEARCH_ENDPOINT = os.environ.get("NLWEB_WEST_ENDPOINT", "https://nlw-crawl-west.search.windows.net")
SEARCH_API_KEY  = os.environ.get("NLWEB_WEST_API_KEY", os.environ.get("AZURE_VECTOR_SEARCH_API_KEY", ""))
INDEX_NAME      = "embeddings1536"
AOAI_ENDPOINT   = os.environ["AZURE_OPENAI_ENDPOINT"]
AOAI_KEY        = os.environ["AZURE_OPENAI_API_KEY"]
AOAI_API_VER    = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
EMBEDDING_MODEL = "text-embedding-3-small"
SCORING_MODEL   = "gpt-4.1"
NUM_RESULTS     = 100  # items per partial query retrieval

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "hard_negatives"

# ── Scoring prompt (same as training data generation) ────────────────────────
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

# ── Aspect decomposition prompt ──────────────────────────────────────────────
DECOMPOSE_PROMPT = """\
Decompose this search query into its key aspects/requirements. Then generate \
partial queries that match SOME aspects but deliberately miss others.

Query: "{query}"
Site: {site}

Return a JSON object with:
- "aspects": list of 2-5 key aspects the query is looking for
- "partial_queries": list of 3-5 queries that each match only 1-2 aspects, \
  designed to retrieve items that are superficially similar but NOT truly relevant. \
  These should be plausible queries on the same site that would retrieve confusable items.

Example for "movies about cooking and food preferably asian" on imdb:
{{
  "aspects": ["movies", "about cooking/food", "asian"],
  "partial_queries": [
    "asian movies",
    "horror movies asia",
    "cooking competition tv shows",
    "japanese drama films",
    "documentary films about culture"
  ]
}}

Output only the JSON object, no other text.
"""


def trim_json(schema_json_str):
    """Trim unnecessary fields from schema.org JSON."""
    try:
        obj = json.loads(schema_json_str) if isinstance(schema_json_str, str) else schema_json_str
        if isinstance(obj, list):
            obj = obj[0] if obj else {}
        if not isinstance(obj, dict):
            return schema_json_str
        remove_keys = {"image", "datePublished", "dateModified", "author",
                       "publisher", "mainEntityOfPage", "thumbnailUrl"}
        schema_type = obj.get("@type", "")
        if schema_type in ("Movie", "TVSeries"):
            remove_keys.update({"trailer", "actor", "director", "creator"})
        return json.dumps({k: v for k, v in obj.items() if k not in remove_keys})
    except (json.JSONDecodeError, TypeError):
        return schema_json_str


def get_embedding(text, client):
    if len(text) > 20000:
        text = text[:20000]
    resp = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return resp.data[0].embedding


def search_index(query_embedding, site, search_client):
    results = search_client.search(
        search_text=None,
        vector_queries=[{
            "kind": "vector",
            "vector": query_embedding,
            "fields": "embedding",
            "k": NUM_RESULTS,
        }],
        filter=f"site eq '{site}'",
        top=NUM_RESULTS,
        select="url,name,site,schema_json",
    )
    return [{
        "url": r.get("url", ""),
        "name": r.get("name", ""),
        "site": r.get("site", ""),
        "schema_json": r.get("schema_json", ""),
        "search_score": r.get("@search.score", 0.0),
    } for r in results]


def score_item(query, item, aoai_client):
    """Score a single (query, item) pair with GPT-4.1."""
    description = trim_json(item.get("schema_json", item.get("name", "")))
    prompt = RANKING_PROMPT.format(query=query, description=description)
    try:
        resp = aoai_client.chat.completions.create(
            model=SCORING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
            timeout=15,
        )
        text = resp.choices[0].message.content.strip()
        result = json.loads(text)
        return {
            "url": item["url"],
            "name": item["name"],
            "score": int(result.get("score", -1)),
            "description": result.get("description", ""),
        }
    except Exception as e:
        return {
            "url": item["url"],
            "name": item["name"],
            "score": -1,
            "description": str(e),
        }


def decompose_query(query, site, aoai_client):
    """Use GPT-4.1 to decompose query into aspects and generate partial queries."""
    prompt = DECOMPOSE_PROMPT.format(query=query, site=site)
    try:
        resp = aoai_client.chat.completions.create(
            model=SCORING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
            timeout=15,
        )
        text = resp.choices[0].message.content.strip()
        return json.loads(text)
    except Exception as e:
        print(f"  WARNING: decompose failed: {e}")
        return None


# ── Synthetic query generation prompt ────────────────────────────────────────
GENERATE_QUERIES_PROMPT = """\
Generate {n} diverse, natural search queries that a real user would type into \
a chatbot when looking for items on {site}. {site_description}

Requirements:
- Each query must be at least 8 words long, complex and specific
- Queries should be the kind of thing a real person would ask, not keyword searches
- Include a mix: some that the site would answer well, some tangential, \
  some cross-domain (e.g. asking a recipe site about cookware, or a movie site about books)
- Vary the specificity: some very precise, some broader but still natural
- Do NOT repeat queries that are too similar to each other

Examples of good queries (for different sites):
- "cast iron pan for making waffles and pancakes on a campfire"
- "thriller movies similar to Gone Girl with unreliable narrator and plot twists"
- "easy vegetarian recipes that taste good reheated for meal prep lunches"
- "hiking trails near Portland Oregon that are good for dogs and have waterfalls"
- "noise canceling headphones that work well for conference calls and music"

Return a JSON object with:
- "queries": list of {n} query strings

Output only the JSON object, no other text.
"""

# Site descriptions to help GPT generate relevant queries
SITE_DESCRIPTIONS = {
    "alltrails": "A hiking and outdoor trails site with trail guides and reviews.",
    "backcountry": "An outdoor gear and equipment retailer.",
    "commonsensemedia": "A site with reviews and ratings of movies, TV, books, and games for families and kids.",
    "crateandbarrel": "A home furnishings and housewares retailer.",
    "eventbrite": "An events platform for concerts, workshops, conferences, and local events.",
    "hebbarskitchen": "An Indian vegetarian recipe site.",
    "imdb": "A movie and TV database with reviews and ratings.",
    "mediterranean_dish": "A Mediterranean cuisine recipe site.",
    "npr_podcasts": "NPR's podcast directory covering news, culture, and storytelling.",
    "nytimes": "The New York Times recipe collection.",
    "scifi_movies": "A science fiction movie database.",
    "seriouseats": "A food and cooking site with recipes, techniques, and equipment reviews.",
    "su_courses": "Stanford University's course catalog.",
    "tripadvisor": "A travel site with hotel, restaurant, and attraction reviews.",
    "wirecutter": "A product review and recommendation site.",
    "zillow": "A real estate listing site for homes and apartments.",
}


def generate_synthetic_queries(site, n, aoai_client):
    """Use GPT-4.1 to generate n natural, complex queries for a site."""
    desc = SITE_DESCRIPTIONS.get(site, f"A website called {site}.")
    prompt = GENERATE_QUERIES_PROMPT.format(n=n, site=site, site_description=desc)
    try:
        resp = aoai_client.chat.completions.create(
            model=SCORING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=2000,
            timeout=30,
        )
        text = resp.choices[0].message.content.strip()
        result = json.loads(text)
        return result.get("queries", [])
    except Exception as e:
        print(f"  WARNING: query generation failed for {site}: {e}")
        return []


def load_existing_urls(scores_path, retrieval_path):
    """Load URLs already in training data to avoid duplicates."""
    existing = set()
    for path in [scores_path, retrieval_path]:
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        for entry in data:
            for item in entry.get("items", []):
                existing.add((entry["site"], entry["query"], item["url"]))
    return existing


def save_progress(retrieval_path, scores_path, all_retrieval, all_scored):
    """Save current state to disk."""
    with open(retrieval_path, "w") as f:
        json.dump(all_retrieval, f, indent=2)
    with open(scores_path, "w") as f:
        json.dump(all_scored, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Generate hard negative training data")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only decompose queries, don't retrieve/score")
    parser.add_argument("--sites", type=str, default=None,
                        help="Comma-separated list of sites (default: all 16)")
    parser.add_argument("--total", type=int, default=500,
                        help="Total number of queries to process (default: 500)")
    parser.add_argument("--min-words", type=int, default=5,
                        help="Skip queries with fewer than this many words (default: 5)")
    parser.add_argument("--generate-queries", type=int, default=None,
                        help="Generate N synthetic queries per site instead of using existing queries")
    args = parser.parse_args()

    print("=" * 60)
    print("Hard Negative Mining for NLWebScorer")
    print("=" * 60)

    aoai = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_KEY,
        api_version=AOAI_API_VER,
    )
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_API_KEY),
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing training data URLs to deduplicate
    existing_urls = load_existing_urls(
        "/Users/rvguha/code/satisficer/nlweb_router/data/scores_azure_oai_gpt-4.1.json",
        "/Users/rvguha/code/satisficer/nlweb_router/data/retrieval_results.json",
    )
    print(f"Loaded {len(existing_urls)} existing (site, query, url) triples for dedup")

    # Determine target sites
    scores_file = "/Users/rvguha/code/satisficer/nlweb_router/data/scores_azure_oai_gpt-4.1.json"
    with open(scores_file) as f:
        all_scores = json.load(f)

    all_sites = sorted(set(e["site"] for e in all_scores))
    if args.sites:
        all_sites = [s for s in args.sites.split(",") if s in all_sites]

    # ── Build query list depending on mode ──
    if args.generate_queries:
        # Synthetic mode: generate new queries per site
        # Save generated queries to disk so resume works if script restarts
        gen_queries_path = OUT_DIR / f"generated_queries_{args.generate_queries}.json"

        if gen_queries_path.exists():
            print(f"\n--- Synthetic Query Mode (resuming from {gen_queries_path.name}) ---")
            with open(gen_queries_path) as f:
                saved = json.load(f)
            all_query_pairs = [(e["site"], e["query"]) for e in saved]
        else:
            print(f"\n--- Synthetic Query Mode ---")
            print(f"Generating {args.generate_queries} queries per site for {len(all_sites)} sites")

            all_query_pairs = []
            saved = []
            for site in all_sites:
                print(f"\n  Generating queries for {site}...")
                queries = generate_synthetic_queries(site, args.generate_queries, aoai)
                print(f"    Got {len(queries)} queries")
                for q in queries:
                    print(f"      {q[:80]}")
                for q in queries:
                    all_query_pairs.append((site, q))
                    saved.append({"site": site, "query": q})

            with open(gen_queries_path, "w") as f:
                json.dump(saved, f, indent=2)
            print(f"\nSaved generated queries to {gen_queries_path.name}")

        total_target = len(all_query_pairs)
        print(f"Total synthetic queries: {total_target}")
    else:
        # Hard negative mode: use existing complex queries
        site_queries = {}
        for entry in all_scores:
            site = entry["site"]
            query = entry["query"]
            if len(query.split()) >= args.min_words and site in all_sites:
                site_queries.setdefault(site, []).append(query)

        # Interleave queries across sites for balanced coverage
        all_query_pairs = []
        if site_queries:
            max_per_site = max(len(qs) for qs in site_queries.values())
            for i in range(max_per_site):
                for site in sorted(site_queries.keys()):
                    if i < len(site_queries[site]):
                        all_query_pairs.append((site, site_queries[site][i]))

        total_target = min(args.total, len(all_query_pairs))
        print(f"Total available queries (>={args.min_words} words): {len(all_query_pairs)} across {len(site_queries)} sites")
        print(f"Will process up to: {total_target}")

    # Output files
    retrieval_path = OUT_DIR / "hard_neg_retrieval.json"
    scores_out_path = OUT_DIR / "hard_neg_scores.json"

    # Always auto-resume from existing progress
    all_retrieval = []
    all_scored = []
    done_keys = set()
    if retrieval_path.exists():
        with open(retrieval_path) as f:
            all_retrieval = json.load(f)
    if scores_out_path.exists():
        with open(scores_out_path) as f:
            all_scored = json.load(f)
        done_keys = {(e["site"], e["original_query"]) for e in all_scored}

    if done_keys:
        print(f"Resuming: {len(done_keys)} queries already done")

    total_new_items = 0
    total_low_score = 0
    queries_done_this_run = 0

    for site, query in all_query_pairs:
        # Check if we've hit the limit
        if not args.generate_queries and len(done_keys) + queries_done_this_run >= args.total:
            break

        if (site, query) in done_keys:
            continue

        queries_done_this_run += 1
        n_done = len(done_keys) + queries_done_this_run
        print(f"\n[{n_done}/{total_target}] {site}: {query[:70]}...")

        if args.generate_queries:
            # Synthetic mode: retrieve directly with the query
            retrieval_queries = [query]
            aspects = []
        else:
            # Hard negative mode: decompose into partial queries
            decomp = decompose_query(query, site, aoai)
            if not decomp:
                continue
            aspects = decomp.get("aspects", [])
            retrieval_queries = decomp.get("partial_queries", [])
            print(f"  Aspects: {aspects}")
            print(f"  Partials: {retrieval_queries}")

        if args.dry_run:
            continue

        # Retrieve items
        new_items = {}  # url → item (deduplicated)
        for rq in retrieval_queries:
            try:
                emb = get_embedding(rq, aoai)
                items = search_index(emb, site, search_client)
            except Exception as e:
                print(f"  WARNING: retrieval failed for '{rq[:40]}': {e}")
                continue

            for item in items:
                url = item["url"]
                if not item.get("name", "").strip():
                    continue  # skip unnamed items — no useful signal
                if (site, query, url) in existing_urls:
                    continue
                if url not in new_items:
                    new_items[url] = item

        print(f"  Retrieved {len(new_items)} new unique items")

        if not new_items:
            all_scored.append({
                "site": site, "original_query": query,
                "aspects": aspects, "partial_queries": retrieval_queries,
                "model": SCORING_MODEL, "items": [],
            })
            save_progress(retrieval_path, scores_out_path, all_retrieval, all_scored)
            continue

        # Save retrieval
        all_retrieval.append({
            "site": site, "original_query": query,
            "aspects": aspects, "partial_queries": retrieval_queries,
            "items": list(new_items.values()),
        })

        # Score all items against the FULL query
        scored_items = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(score_item, query, item, aoai): item
                for item in new_items.values()
            }
            for fut in as_completed(futures):
                scored_items.append(fut.result())

        valid = [s for s in scored_items if s["score"] >= 0]
        low = [s for s in valid if s["score"] < 50]
        total_new_items += len(valid)
        total_low_score += len(low)

        print(f"  Scored: {len(valid)} valid, {len(low)} low (<50)")

        # Show a few examples across the range
        scored_items.sort(key=lambda x: x["score"])
        for item in scored_items[:3]:
            if item["score"] >= 0:
                print(f"    {item['score']:3d} - {item['name'][:60]}")

        all_scored.append({
            "site": site, "original_query": query,
            "aspects": aspects, "partial_queries": retrieval_queries,
            "model": SCORING_MODEL, "items": scored_items,
        })

        # Save after every query
        save_progress(retrieval_path, scores_out_path, all_retrieval, all_scored)

    # Final summary
    total_done = len(done_keys) + queries_done_this_run
    print(f"\n{'='*60}")
    print(f"DONE — {total_done} queries complete")
    print(f"{'='*60}")
    print(f"This run: {queries_done_this_run} queries, {total_new_items} items scored")
    if total_new_items:
        print(f"Low-score items (<50): {total_low_score} ({total_low_score/total_new_items*100:.0f}%)")

    # Show decile distribution of new scores
    if all_scored:
        all_item_scores = [item["score"] for e in all_scored for item in e.get("items", []) if item.get("score", -1) >= 0]
        if all_item_scores:
            print(f"\nScore distribution (all {len(all_item_scores)} items):")
            for lo in range(0, 100, 10):
                hi = lo + 10
                n = sum(1 for s in all_item_scores if lo <= s < hi)
                print(f"  {lo:>3}-{hi:<3}: {n:>6} ({n/len(all_item_scores)*100:>5.1f}%)")

    print(f"\nOutput: {OUT_DIR}/")
    print(f"  hard_neg_retrieval.json  ({len(all_retrieval)} entries)")
    print(f"  hard_neg_scores.json     ({len(all_scored)} entries)")


if __name__ == "__main__":
    main()

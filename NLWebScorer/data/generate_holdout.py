"""Generate holdout evaluation data for new sites not in training.

Retrieves items from Azure AI Search, scores them with GPT-4.1,
and saves in the same format as the training data.

Usage:
    cd NLWebScorer
    python -m data.generate_holdout

Requires Azure credentials in environment (same as satisficer/.env).
"""

import json
import os
import sys
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load env: source set_keys.sh for nlweb_west endpoint, then satisficer .env for AOAI
load_dotenv(Path("/Users/rvguha/code/satisficer/.env"), override=True)

sys.stdout.reconfigure(line_buffering=True)

# Use nlweb_west endpoint (has all sites including bon_appetit, empirepodcast)
SEARCH_ENDPOINT = os.environ.get("NLWEB_WEST_ENDPOINT", "https://nlw-crawl-west.search.windows.net")
SEARCH_API_KEY  = os.environ.get("NLWEB_WEST_API_KEY", os.environ.get("AZURE_VECTOR_SEARCH_API_KEY", ""))
INDEX_NAME      = "embeddings1536"
AOAI_ENDPOINT   = os.environ["AZURE_OPENAI_ENDPOINT"]
AOAI_KEY        = os.environ["AZURE_OPENAI_API_KEY"]
AOAI_API_VER    = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
EMBEDDING_MODEL = "text-embedding-3-small"
SCORING_MODEL   = "gpt-4.1"
NUM_RESULTS     = 100

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "holdout"

# ── Holdout site queries ─────────────────────────────────────────────────────
# 10 queries per difficulty level × 5 levels = 50 per site
HOLDOUT_QUERIES = {
    # ══════════════════════════════════════════════════════════════════════════
    # BON APPETIT - Food / recipes
    # ══════════════════════════════════════════════════════════════════════════
    "bon_appetit": [
        # Level 1 - Very Easy
        "pasta", "salad", "chicken", "soup", "cookies",
        "pizza", "steak", "cake", "tacos", "bread",
        # Level 2 - Easy
        "chocolate chip cookies", "grilled chicken", "tomato soup",
        "banana bread", "pasta carbonara", "green salad",
        "roast vegetables", "fish tacos", "lemon cake", "fried rice",
        # Level 3 - Medium
        "easy weeknight pasta dinner", "crispy baked chicken thighs",
        "creamy tomato soup from scratch", "homemade sourdough bread recipe",
        "best chocolate cake no mixer", "quick vegetarian dinner ideas",
        "grilled salmon with glaze", "one pot rice and beans",
        "sheet pan dinner vegetables protein", "simple birthday cake frosting",
        # Level 4 - Hard
        "weeknight dinner under 30 minutes using pantry staples for family of four",
        "gluten free dessert that tastes like real cake not dry or crumbly",
        "slow braise recipe for tough cuts of beef that falls apart tender",
        "fermented hot sauce recipe with fresh peppers step by step guide",
        "homemade fresh pasta dough without pasta machine using rolling pin",
        "meal prep lunches for work week that reheat well in microwave",
        "impressive dinner party appetizer that can be made ahead of time",
        "crispy fried chicken sandwich with pickles and spicy mayo sauce",
        "vegetarian thanksgiving main course that even meat eaters will love",
        "flaky buttery pie crust recipe tips for beginners who struggle with pastry",
        # Level 5 - Very Hard
        "multi-day fermented sourdough pizza dough with poolish and cold proof for Neapolitan style",
        "whole animal butchery guide breaking down a lamb into primal cuts for home cooking",
        "modernist cuisine technique for perfect soft scrambled eggs using bain-marie method",
        "restaurant quality French onion soup with deeply caramelized onions and gruyere croutons",
        "traditional mole negro recipe from Oaxaca with toasted chiles and chocolate from scratch",
        "japanese style milk bread shokupan with tangzhong method for ultra soft fluffy texture",
        "smoked brisket low and slow on offset smoker with oak wood for competition barbecue",
        "handmade fresh lamian pulled noodles technique for soup noodles from flour to bowl",
        "multi-component plated dessert with tempered chocolate tuile crème brûlée and fruit coulis",
        "dry aged ribeye steak at home using dedicated fridge setup and salt crust method",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # ALLBIRDS - Sustainable footwear/clothing
    # ══════════════════════════════════════════════════════════════════════════
    "allbirds": [
        # Level 1
        "shoes", "sneakers", "running", "wool", "slippers",
        "sandals", "boots", "socks", "shirt", "jacket",
        # Level 2
        "running shoes", "wool sneakers", "casual shoes",
        "slip on shoes", "hiking shoes", "winter boots",
        "cotton t-shirt", "rain jacket", "ankle socks", "loafers",
        # Level 3
        "comfortable shoes for standing all day", "lightweight running shoes cushioned",
        "sustainable wool sneakers casual wear", "waterproof shoes for rainy weather",
        "breathable summer shoes for walking", "warm winter boots for snow",
        "travel shoes packable lightweight", "office shoes smart casual men",
        "workout shoes for gym training", "everyday comfortable walking shoes",
        # Level 4
        "shoes for flat feet with good arch support for all day standing at work",
        "lightweight breathable running shoes for hot weather summer marathon training",
        "sustainable eco friendly shoes made from natural materials for everyday wear",
        "waterproof winter boots that are warm but not heavy for city commuting",
        "slip resistant shoes for restaurant work comfortable during long shifts",
        "minimalist travel shoes that pack flat and work for hiking and dinner",
        "wide toe box shoes for bunions that still look professional in office",
        "machine washable sneakers for messy activities that clean up easily",
        "shoes for plantar fasciitis with cushioned sole and heel support",
        "breathable wool shoes that don't smell after wearing without socks",
        # Level 5
        "complete sustainable wardrobe capsule with shoes and clothing all made from natural renewable materials",
        "shoes for nurse working 12 hour hospital shifts on hard floors with heel pain and wide feet",
        "comparison between merino wool and tree fiber shoes for hot humid climate daily walking commute",
        "vegan sustainable shoes with carbon neutral manufacturing for environmentally conscious consumer",
        "travel packing one pair of shoes that works for hiking beach dinner and long flights",
        "shoes that transition from morning run to office work without changing for busy professionals",
        "gift guide sustainable comfortable shoes for someone with foot problems who cares about environment",
        "cold weather layering system head to toe with sustainable materials for Pacific Northwest winter",
        "ultralight shoes for thru-hiking that provide enough support for carrying loaded backpack long distances",
        "orthopedic friendly shoes that don't look like orthopedic shoes for style conscious seniors",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # NEURIPS - AI/ML academic conference
    # ══════════════════════════════════════════════════════════════════════════
    "neurips": [
        # Level 1
        "transformer", "diffusion", "reinforcement learning", "GAN", "attention",
        "BERT", "optimization", "generalization", "fairness", "pruning",
        # Level 2
        "graph neural network", "federated learning", "language model",
        "contrastive learning", "neural architecture search", "meta learning",
        "causal inference", "knowledge distillation", "adversarial robustness", "self-supervised",
        # Level 3
        "efficient training large language models", "diffusion models for image generation",
        "reinforcement learning from human feedback", "vision transformer attention mechanism",
        "graph neural network message passing", "federated learning privacy preserving",
        "neural network pruning without accuracy loss", "causal discovery from observational data",
        "out of distribution generalization methods", "multi-task learning shared representations",
        # Level 4
        "scaling laws for large language models predicting loss from compute and data size",
        "sample efficient reinforcement learning for robotics with sim to real transfer",
        "differentially private training of deep neural networks with bounded sensitivity",
        "efficient inference for transformer models on edge devices with quantization and distillation",
        "theoretical analysis of generalization bounds for overparameterized neural networks",
        "multimodal foundation models combining vision and language with cross-attention mechanisms",
        "continual learning without catastrophic forgetting using memory replay and regularization",
        "equivariant neural networks for molecular property prediction with symmetry constraints",
        "fairness constraints in machine learning with multiple protected attributes simultaneously",
        "neural ODE and continuous depth models for time series and dynamical systems",
        # Level 5
        "provably efficient offline reinforcement learning under partial observability with function approximation and coverage assumptions",
        "unified theoretical framework connecting attention mechanisms in transformers to kernel methods and Hopfield networks",
        "compositional generalization in neural sequence models through modular architectures and systematic data augmentation",
        "convergence analysis of Adam optimizer variants in non-convex stochastic optimization with heavy-tailed gradient noise",
        "how to build AI systems that maintain alignment under distributional shift and adversarial manipulation in deployment",
        "mechanistic interpretability of large language models through circuit-level analysis of attention heads and MLP neurons",
        "training compute-optimal language models with data mixing strategies across multilingual and multimodal data sources",
        "theoretical foundations of in-context learning in transformers relating to meta-learning and Bayesian inference",
        "differentiable discrete optimization using continuous relaxations for combinatorial problems in graph and scheduling domains",
        "safe reinforcement learning with formal verification guarantees for safety-critical autonomous systems in continuous state spaces",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # EMPIREPODCAST - Podcast (film/entertainment)
    # ══════════════════════════════════════════════════════════════════════════
    "empirepodcast": [
        # Level 1
        "Marvel", "Star Wars", "Batman", "horror", "comedy",
        "Spielberg", "Nolan", "sequel", "Oscar", "Netflix",
        # Level 2
        "superhero movies", "movie review", "film podcast",
        "best director", "action movies", "science fiction",
        "movie soundtrack", "film festival", "box office", "movie trailer",
        # Level 3
        "Marvel cinematic universe phase four", "best horror movies of year",
        "Christopher Nolan filmography discussion", "Star Wars series review",
        "Oscar nominations predictions analysis", "indie film recommendations hidden gems",
        "movie franchise reboot vs original", "streaming vs theatrical release debate",
        "film score and composer spotlight", "behind the scenes movie making",
        # Level 4
        "episode discussing how practical effects compare to CGI in modern blockbusters",
        "interview with director about making independent film on small budget",
        "deep dive into why certain movie franchises fail after successful first installment",
        "discussion about representation and diversity in Hollywood casting and storytelling",
        "analysis of how streaming platforms changed the movie industry business model",
        "episode about the best movie performances that were overlooked for awards",
        "debate about whether superhero fatigue is real and what comes next",
        "retrospective on classic film that influenced an entire generation of filmmakers",
        "episode covering the most anticipated upcoming movies and what to expect",
        "discussion about how movie marketing and trailers can make or break films",
        # Level 5
        "comprehensive episode analyzing the entire arc of a major franchise from origin to current state with critical assessment",
        "in-depth discussion about how international box office is reshaping what Hollywood produces and cultural implications",
        "episode that breaks down the craft of film editing and how different editing styles create emotional responses",
        "multi-part series covering the history of a film genre from origins through golden age to modern reinvention",
        "conversation about the ethics of AI-generated content in film and how it affects actors writers and artists",
        "deep analysis of a controversial film that divided critics and audiences examining both perspectives fairly",
        "episode exploring how a specific cinematographer uses lighting and framing to tell stories visually",
        "discussion comparing film adaptations of books and when changes from source material work or fail",
        "retrospective covering an entire decade of cinema identifying the defining trends themes and breakthrough films",
        "episode about the future of cinema experience including IMAX Dolby premium formats versus home viewing",
    ],
}


# ── Ranking prompt (same as training data) ────────────────────────────────────
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


def trim_json(schema_json_str: str) -> str:
    """Trim unnecessary fields from schema.org JSON (matches satisficer/json_utils.py)."""
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


def get_embedding(text: str, client: AzureOpenAI) -> list[float]:
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
    t0 = time.time()
    try:
        resp = aoai_client.chat.completions.create(
            model=SCORING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
            timeout=15,
        )
        elapsed = int((time.time() - t0) * 1000)
        text = resp.choices[0].message.content.strip()
        # Parse JSON
        result = json.loads(text)
        return {
            "url": item["url"],
            "name": item["name"],
            "score": int(result.get("score", -1)),
            "description": result.get("description", ""),
            "response_time_ms": elapsed,
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
    except Exception as e:
        return {
            "url": item["url"],
            "name": item["name"],
            "score": -1,
            "description": str(e),
            "response_time_ms": int((time.time() - t0) * 1000),
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        }


def main():
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

    # Phase 1: Retrieve
    retrieval_path = OUT_DIR / "holdout_retrieval_west.json"
    if retrieval_path.exists():
        print(f"Loading existing retrieval results from {retrieval_path}")
        with open(retrieval_path) as f:
            all_retrieval = json.load(f)
    else:
        print("Phase 1: Retrieving items...")
        all_retrieval = []
        total = sum(len(qs) for qs in HOLDOUT_QUERIES.values())
        done = 0
        for site, queries in HOLDOUT_QUERIES.items():
            for qi, query in enumerate(queries):
                done += 1
                difficulty = min((qi // 10) + 1, 5)
                print(f"[{done}/{total}] {site} L{difficulty}: {query[:50]}...")
                emb = get_embedding(query, aoai)
                items = search_index(emb, site, search_client)
                all_retrieval.append({
                    "site": site, "query": query,
                    "query_length": len(query), "difficulty": difficulty,
                    "num_results": len(items), "items": items,
                })
        with open(retrieval_path, "w") as f:
            json.dump(all_retrieval, f, indent=2)
        print(f"Wrote {len(all_retrieval)} retrieval results")

    # Phase 2: Score with GPT-4.1
    scores_path = OUT_DIR / "holdout_scores_west.json"
    print(f"\nPhase 2: Scoring with {SCORING_MODEL}...")

    # Load progress if exists
    if scores_path.exists():
        with open(scores_path) as f:
            all_scores = json.load(f)
        done_keys = {(e["site"], e["query"]) for e in all_scores}
        print(f"  Resuming: {len(done_keys)} queries already scored")
    else:
        all_scores = []
        done_keys = set()

    total_queries = len(all_retrieval)
    for qi, entry in enumerate(all_retrieval):
        key = (entry["site"], entry["query"])
        if key in done_keys:
            continue

        print(f"[{qi+1}/{total_queries}] {entry['site']}: {entry['query'][:50]}...")

        scored_items = []
        # Score items in parallel (5 concurrent)
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(score_item, entry["query"], item, aoai): item
                for item in entry["items"]
            }
            for fut in as_completed(futures):
                scored_items.append(fut.result())

        valid = sum(1 for s in scored_items if s["score"] >= 0)
        print(f"  {valid}/{len(scored_items)} scored successfully")

        all_scores.append({
            "site": entry["site"],
            "query": entry["query"],
            "query_length": entry["query_length"],
            "difficulty": entry.get("difficulty", 0),
            "model": SCORING_MODEL,
            "items": scored_items,
        })

        # Save progress every 5 queries
        if (qi + 1) % 5 == 0:
            with open(scores_path, "w") as f:
                json.dump(all_scores, f, indent=2)

    # Final save
    with open(scores_path, "w") as f:
        json.dump(all_scores, f, indent=2)

    total_pairs = sum(len(e["items"]) for e in all_scores)
    valid_pairs = sum(1 for e in all_scores for i in e["items"] if i["score"] >= 0)
    print(f"\nDone. {len(all_scores)} queries, {total_pairs} pairs ({valid_pairs} valid)")
    print(f"Saved to {scores_path}")


if __name__ == "__main__":
    main()

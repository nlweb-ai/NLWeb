"""Retrieve Azure AI Search results for sample queries across NLWeb sites.

Uses the same pattern as NLWeb_Core:
  - Azure OpenAI  → text-embedding-3-small (1536-d)
  - Azure AI Search → vector search filtered by site

Writes all results to data/retrieval_results.json.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

# ── Azure config (matches NLWeb_Core/set_keys.sh env vars) ───────────────
SEARCH_ENDPOINT = os.environ["AZURE_VECTOR_SEARCH_ENDPOINT"]
SEARCH_API_KEY  = os.environ["AZURE_VECTOR_SEARCH_API_KEY"]
INDEX_NAME      = os.environ.get("AZURE_SEARCH_INDEX", "embeddings1536")

AOAI_ENDPOINT   = os.environ["AZURE_OPENAI_ENDPOINT"]
AOAI_KEY        = os.environ["AZURE_OPENAI_API_KEY"]
AOAI_API_VER    = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
EMBEDDING_MODEL = "text-embedding-3-small"

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "retrieval_results.json"

# ── Sample queries  (site → list of queries) ──────────────────────────────
# Structured by difficulty level (1=very easy, 5=very hard)
# Target: 10 queries per level × 5 levels × ~15 sites = ~750 queries

QUERIES = {
    # ══════════════════════════════════════════════════════════════════════════
    # BACKCOUNTRY - Outdoor gear retailer
    # ══════════════════════════════════════════════════════════════════════════
    "backcountry": [
        # Level 1 - Very Easy (1-2 words, basic keywords)
        "tent",
        "backpack",
        "hiking boots",
        "sleeping bag",
        "jacket",
        "skis",
        "bike helmet",
        "water bottle",
        "headlamp",
        "sunglasses",
        # Level 2 - Easy (2-3 words, basic descriptive)
        "waterproof rain jacket",
        "down sleeping bag",
        "trekking poles",
        "climbing harness",
        "bike lights",
        "wool base layer",
        "camp stove",
        "dry bag",
        "trail running shoes",
        "ski goggles",
        # Level 3 - Medium (4-6 words, more specific)
        "ultralight tent for backpacking",
        "waterproof hiking boots ankle support",
        "insulated jacket for cold weather",
        "carbon fiber trekking poles adjustable",
        "climbing rope for outdoor climbing",
        "panniers for bike touring",
        "merino wool hiking socks",
        "avalanche beacon and probe",
        "inflatable sleeping pad lightweight",
        "cycling jersey moisture wicking",
        # Level 4 - Hard (multi-constraint queries)
        "down sleeping bag rated for winter mountaineering below zero",
        "ultralight backpacking tent under 3 pounds for solo hiking",
        "waterproof trail running shoes with aggressive tread for technical terrain",
        "climbing shoes for intermediate boulderers with good edging performance",
        "backcountry ski touring setup with bindings for uphill travel",
        "bike panniers waterproof for grocery shopping and commuting",
        "softshell jacket breathable for active pursuits in variable weather",
        "camp stove that works with multiple fuel types for international travel",
        "GPS watch with long battery life for ultramarathon running",
        "kayak dry suit for cold water paddling in Pacific Northwest",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "ultralight camping gear for 100-mile thru-hike where total pack weight must stay under 15 pounds",
        "approach shoes that work for both scrambling on granite and light sport climbing at the crag",
        "four-season mountaineering tent that can handle high winds and heavy snow for Denali expedition",
        "wetsuit for surfing in Northern California winter that balances warmth and flexibility for duck diving",
        "bikepacking setup for multi-day gravel racing including frame bags that fit irregular triangle geometry",
        "avalanche safety gear for backcountry skiing novice who needs beacon probe shovel education bundle",
        "climbing quickdraws and carabiners for trad climbing on sandstone with soft rock considerations",
        "cycling shoes compatible with SPD cleats for commuting that also work for indoor spin classes",
        "bear canister that meets park regulations and fits inside ultralight pack for JMT thru-hike",
        "insulated boots for ice fishing that work in extreme cold but are light enough for walking long distances",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # HEBBARSKITCHEN - Indian vegetarian recipes
    # ══════════════════════════════════════════════════════════════════════════
    "hebbarskitchen": [
        # Level 1 - Very Easy (1-2 words)
        "dosa",
        "idli",
        "samosa",
        "biryani",
        "curry",
        "paneer",
        "naan",
        "raita",
        "chutney",
        "ladoo",
        # Level 2 - Easy (2-3 words)
        "masala dosa",
        "butter paneer",
        "dal makhani",
        "aloo paratha",
        "gulab jamun",
        "medu vada",
        "coconut chutney",
        "vegetable pulao",
        "rava upma",
        "pav bhaji",
        # Level 3 - Medium (4-6 words)
        "crispy masala dosa with potato",
        "soft fluffy idli recipe tips",
        "paneer butter masala restaurant style",
        "samosa crispy potato filled pastry",
        "naan bread without tandoor stovetop",
        "dal makhani slow cooked creamy",
        "chole bhature chickpea curry fried",
        "palak paneer spinach curry recipe",
        "rava kesari sweet semolina pudding",
        "bisi bele bath spicy rice",
        # Level 4 - Hard (multi-constraint)
        "South Indian breakfast recipes that are both diabetic friendly and high protein",
        "quick vegetarian dinner recipes under 30 minutes using minimal ingredients",
        "traditional festival sweets that can be made ahead and stored for weeks",
        "gluten free Indian dishes for someone with celiac disease",
        "low carb Indian recipes suitable for keto diet vegetarian",
        "kids friendly Indian snacks that are healthy and not fried",
        "authentic Udupi restaurant style recipes for home cooking",
        "pressure cooker Indian recipes for busy weeknight dinners",
        "vegan Indian food options that replace paneer with tofu",
        "high protein vegetarian meals for post workout recovery",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "diabetic friendly South Indian breakfast that tastes like regular dosa but uses alternative batters",
        "fusion recipe combining Udupi cooking techniques with Chinese flavors for Indo-Chinese dish",
        "traditional Mysore pak recipe with exact ghee measurements for authentic texture without being too oily",
        "street food recipes adapted for air fryer to reduce oil while maintaining authentic taste and texture",
        "complete thali menu for guests with mixed dietary needs including vegan gluten-free and nut-free options",
        "fermented batter recipes troubleshooting for cold climates where idli dosa batter fails to rise",
        "authentic filter coffee preparation method with right coffee-chicory ratio and decoction technique",
        "meal prep Indian recipes that reheat well and taste fresh after refrigeration for entire week",
        "traditional pickle recipes with proper oil infusion technique for year-long shelf stability",
        "recreating restaurant biryani dum cooking technique at home with layering and sealed pot method",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # MEDITERRANEAN_DISH - Mediterranean cuisine recipes
    # ══════════════════════════════════════════════════════════════════════════
    "mediterranean_dish": [
        # Level 1 - Very Easy (1-2 words)
        "hummus",
        "falafel",
        "tzatziki",
        "baklava",
        "shawarma",
        "pita",
        "tabbouleh",
        "moussaka",
        "gyro",
        "dolmas",
        # Level 2 - Easy (2-3 words)
        "Greek salad",
        "baba ganoush",
        "lamb kebab",
        "spanakopita recipe",
        "shakshuka eggs",
        "stuffed peppers",
        "lemon chicken",
        "grilled halloumi",
        "olive tapenade",
        "labneh dip",
        # Level 3 - Medium (4-6 words)
        "creamy hummus with tahini recipe",
        "crispy falafel from scratch",
        "grilled lamb chops with herbs",
        "chicken shawarma bowl homemade",
        "baked fish with lemon herbs",
        "roasted eggplant with tahini dressing",
        "Greek moussaka layered eggplant casserole",
        "stuffed grape leaves rice filling",
        "Mediterranean quinoa salad healthy",
        "seafood paella Spanish rice dish",
        # Level 4 - Hard (multi-constraint)
        "vegetarian moussaka without meat that still has rich hearty texture",
        "authentic Middle Eastern shawarma spice blend and marinade technique",
        "Mediterranean diet meal prep for heart healthy eating entire week",
        "grilled octopus Mediterranean style restaurant quality at home",
        "plant based Mediterranean dishes high in protein for vegan diet",
        "shakshuka eggs in tomato sauce perfect runny yolk technique",
        "traditional baklava with phyllo dough layering and honey syrup",
        "anti-inflammatory Mediterranean recipes for autoimmune conditions",
        "fish tagine Moroccan style with preserved lemons and olives",
        "homemade pita bread soft and puffy with proper pocket formation",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "complete mezze platter with multiple dips spreads and small plates for large dinner party",
        "traditional Lebanese kibbeh with proper bulgur meat ratio and football shape forming technique",
        "recreating restaurant-style grilled octopus tender texture with charred exterior at home grill",
        "low calorie Mediterranean recipes under 400 calories that still satisfy as complete meal",
        "adapting Mediterranean recipes for someone with nightshade allergy avoiding tomatoes peppers eggplant",
        "authentic Moroccan tagine cooking in traditional clay pot with proper heat distribution technique",
        "fermented labneh strained yogurt cheese with proper whey separation for thick spreadable consistency",
        "building Mediterranean flavor profile without olive oil for someone with olive allergy",
        "traditional Greek Easter lamb preparation with herb stuffing and slow roasting method",
        "complete Turkish breakfast spread with multiple dishes eggs cheeses vegetables breads for weekend brunch",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # NPR_PODCASTS - NPR podcast episodes
    # ══════════════════════════════════════════════════════════════════════════
    "npr_podcasts": [
        # Level 1 - Very Easy (1-2 words)
        "politics",
        "climate",
        "economy",
        "health",
        "technology",
        "books",
        "music",
        "science",
        "history",
        "education",
        # Level 2 - Easy (2-3 words)
        "election coverage",
        "climate change",
        "AI technology",
        "mental health",
        "book reviews",
        "music interviews",
        "space exploration",
        "healthcare policy",
        "immigration stories",
        "racial justice",
        # Level 3 - Medium (4-6 words)
        "episodes about artificial intelligence ethics",
        "climate change impact on communities",
        "economic policy analysis and debate",
        "mental health awareness conversations",
        "author interviews about new books",
        "music industry behind the scenes",
        "space exploration NASA discoveries",
        "Supreme Court decision analysis",
        "immigration personal stories and policy",
        "education system reform discussions",
        # Level 4 - Hard (multi-constraint)
        "in-depth investigative journalism episodes about corporate wrongdoing and accountability",
        "episodes featuring scientists discussing breakthrough research in accessible language",
        "political analysis episodes that present multiple perspectives without partisan bias",
        "episodes about intersection of technology and privacy civil liberties concerns",
        "long-form storytelling episodes about American history lesser known events",
        "interviews with authors discussing writing process and inspiration behind books",
        "episodes examining social media impact on democracy and public discourse",
        "healthcare system analysis comparing international approaches to US system",
        "episodes about criminal justice reform with perspectives from multiple stakeholders",
        "science communication episodes making complex topics accessible to general audience",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "investigative series about environmental justice in communities facing pollution from industrial facilities",
        "episodes exploring intersection of artificial intelligence machine learning and ethics in hiring algorithms",
        "multi-part series examining history of voting rights in America and current challenges to access",
        "in-depth economic analysis episodes suitable for listeners without finance background explaining recession indicators",
        "episodes featuring diverse voices on immigration reform including undocumented immigrants advocates and enforcement officials",
        "science episodes explaining climate modeling and prediction uncertainty for listeners skeptical of climate change",
        "political episodes from before 2020 election that predicted or analyzed factors leading to current polarization",
        "episodes about mental health in workplace featuring both employee experiences and employer policy perspectives",
        "long-form documentary episodes about overlooked moments in civil rights movement beyond famous events",
        "episodes examining technology industry practices on content moderation featuring platform employees and critics",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # SU_COURSES - Stanford University courses
    # ══════════════════════════════════════════════════════════════════════════
    "su_courses": [
        # Level 1 - Very Easy (1-2 words)
        "CS106A",
        "machine learning",
        "economics",
        "psychology",
        "physics",
        "biology",
        "statistics",
        "philosophy",
        "engineering",
        "calculus",
        # Level 2 - Easy (2-3 words)
        "artificial intelligence course",
        "data structures algorithms",
        "intro to programming",
        "financial accounting",
        "organic chemistry",
        "linear algebra",
        "computer vision",
        "entrepreneurship class",
        "political science",
        "creative writing",
        # Level 3 - Medium (4-6 words)
        "machine learning fundamentals course Stanford",
        "deep learning neural networks class",
        "natural language processing NLP course",
        "software engineering best practices",
        "data science and analytics",
        "finance and investment principles",
        "biomedical engineering introduction",
        "human computer interaction design",
        "probability and random processes",
        "modern physics quantum mechanics",
        # Level 4 - Hard (multi-constraint)
        "graduate level machine learning course with focus on theory and mathematics",
        "programming course suitable for complete beginners with no coding experience",
        "interdisciplinary course combining computer science and biology for computational biology",
        "business course teaching entrepreneurship with hands-on startup project component",
        "engineering course with significant laboratory or hands-on project work",
        "humanities course satisfying writing intensive requirement for undergraduates",
        "statistics course focused on applications in social sciences research methods",
        "computer science course covering both systems programming and software design",
        "economics course examining intersection of technology and market competition",
        "ethics course specifically addressing issues in artificial intelligence and technology",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "advanced graduate seminar on reinforcement learning with research paper reading and implementation components",
        "introductory programming course designed for humanities majors with emphasis on digital humanities applications",
        "cross-listed course between computer science and linguistics on computational approaches to language understanding",
        "MBA course on venture capital and startup financing with guest lectures from Silicon Valley investors",
        "capstone engineering design course with industry partnership on real-world sustainability problems",
        "course on ethics of emerging technologies covering AI biotechnology and surveillance for policy students",
        "advanced mathematics course on optimization theory with applications to machine learning algorithms",
        "interdisciplinary course examining climate change from science policy economics and engineering perspectives",
        "research methods course teaching qualitative and quantitative approaches for social science PhD students",
        "course on technology and society examining historical and current debates about automation and employment",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # CRATEANDBARREL - Home goods and furniture
    # ══════════════════════════════════════════════════════════════════════════
    "crateandbarrel": [
        # Level 1 - Very Easy (1-2 words)
        "sofa",
        "plates",
        "rug",
        "lamp",
        "vase",
        "bedding",
        "towels",
        "glasses",
        "table",
        "chairs",
        # Level 2 - Easy (2-3 words)
        "dining table",
        "wine glasses",
        "throw pillows",
        "coffee maker",
        "area rug",
        "table lamp",
        "bath towels",
        "cutting board",
        "bar stools",
        "desk chair",
        # Level 3 - Medium (4-6 words)
        "modern dining table for six",
        "crystal wine glasses set",
        "decorative throw pillows colorful",
        "stainless steel cookware set",
        "living room area rug large",
        "ceramic dinnerware set white",
        "outdoor patio furniture set",
        "bedding sheets high thread count",
        "kitchen utensils set complete",
        "sectional sofa with chaise",
        # Level 4 - Hard (multi-constraint)
        "mid-century modern dining table solid wood seats eight extendable",
        "hand-blown crystal wine glasses dishwasher safe stemless design",
        "outdoor patio furniture weather resistant wicker with cushions",
        "nonstick cookware set induction compatible oven safe to 500 degrees",
        "area rug for high traffic living room stain resistant pet friendly",
        "ergonomic office desk chair with lumbar support adjustable height",
        "king size bedding set organic cotton breathable for hot sleepers",
        "ceramic dinnerware set microwave and dishwasher safe modern design",
        "bar stools counter height swivel with back for kitchen island",
        "sectional sofa modular configuration with storage for small spaces",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "complete dining room set with extendable table chairs sideboard for formal entertaining twelve guests",
        "outdoor furniture that survives harsh winters without covers and doesn't fade in direct sun exposure",
        "kitchen organization system for small apartment maximizing vertical space with cabinet and drawer solutions",
        "nursery furniture set with convertible crib that grows with child to toddler bed and full size",
        "home office setup for two people sharing space with separate work zones and adequate storage",
        "wedding registry essentials covering kitchen dining bedroom for couple transitioning from apartment to house",
        "patio furniture for small urban balcony that functions as both dining area and lounge space",
        "complete guest room makeover with bed nightstands dresser under $2000 budget modern farmhouse style",
        "kitchen cookware for someone transitioning from nonstick to stainless steel needing complete replacement set",
        "apartment furnishing for recent graduate first place balancing quality with limited budget across all rooms",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # NYTIMES - New York Times Cooking recipes
    # ══════════════════════════════════════════════════════════════════════════
    "nytimes": [
        # Level 1 - Very Easy (1-2 words)
        "cookies",
        "pasta",
        "chicken",
        "salmon",
        "soup",
        "salad",
        "bread",
        "cake",
        "pizza",
        "steak",
        # Level 2 - Easy (2-3 words)
        "chocolate chip cookies",
        "chicken parmesan",
        "banana bread",
        "tomato soup",
        "caesar salad",
        "roast chicken",
        "apple pie",
        "beef stew",
        "grilled salmon",
        "pasta carbonara",
        # Level 3 - Medium (4-6 words)
        "easy weeknight pasta recipes",
        "crispy roast chicken with vegetables",
        "homemade sourdough bread starter",
        "classic chocolate chip cookies chewy",
        "one pot chicken and rice",
        "sheet pan dinner recipes simple",
        "creamy tomato soup from scratch",
        "best banana bread recipe moist",
        "Thai green curry with chicken",
        "perfect grilled steak medium rare",
        # Level 4 - Hard (multi-constraint)
        "weeknight dinner recipes ready in 30 minutes using pantry staples",
        "vegetarian main dishes that satisfy meat eaters at dinner party",
        "holiday dessert recipes that can be made day ahead and stored",
        "gluten free baking recipes that taste as good as regular version",
        "meal prep recipes that reheat well for lunches throughout week",
        "low carb dinner recipes under 500 calories that are filling",
        "authentic Italian pasta dishes using traditional techniques and ingredients",
        "Thanksgiving turkey recipe with both dry brine and herb butter",
        "birthday cake recipe impressive looking but achievable for home baker",
        "summer grilling recipes beyond burgers for backyard barbecue entertaining",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "complete dinner party menu for eight guests with make-ahead components and dietary accommodations for vegetarian and gluten-free",
        "adapting classic French recipes for American home kitchen without specialized equipment or hard-to-find ingredients",
        "holiday cookie recipes with precise timing guide for baking multiple batches over several days for gift boxes",
        "weeknight meals that work for family with picky kids while still being interesting for adults with different spice levels",
        "recreating restaurant-quality dishes at home covering technique tips for achieving professional results in home kitchen",
        "complete meal prep plan for week covering breakfast lunch dinner with shopping list and storage instructions",
        "baking at high altitude adjustments needed for cakes cookies and breads with specific ratio modifications",
        "dinner recipes using only ingredients available at typical suburban grocery store avoiding specialty markets",
        "traditional recipes from grandparents generation updated with modern techniques while preserving authentic flavors",
        "complete brunch menu for hosting including make-ahead items day-of preparation timeline and serving strategy",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # IMDB - Movie database
    # ══════════════════════════════════════════════════════════════════════════
    "imdb": [
        # Level 1 - Very Easy (1-2 words)
        "Inception",
        "comedies",
        "Tom Hanks",
        "Marvel",
        "horror",
        "drama",
        "animated",
        "documentary",
        "thriller",
        "romance",
        # Level 2 - Easy (2-3 words)
        "best thrillers",
        "Tom Hanks movies",
        "comedy films",
        "action movies",
        "horror films",
        "Christopher Nolan",
        "animated movies",
        "90s classics",
        "sci-fi movies",
        "Oscar winners",
        # Level 3 - Medium (4-6 words)
        "best thriller movies recent years",
        "family friendly comedy films",
        "action movies with explosions",
        "horror films genuinely scary",
        "award winning drama movies",
        "Christopher Nolan films ranked",
        "animated movies for adults",
        "documentary films about nature",
        "science fiction space movies",
        "classic romantic movies all time",
        # Level 4 - Hard (multi-constraint)
        "thriller movies with twist endings that keep you guessing until the end",
        "family movies appropriate for both young kids and teenagers to enjoy together",
        "action films with practical stunts minimal CGI from recent decade",
        "horror movies that rely on atmosphere tension rather than jump scares gore",
        "independent drama films that received critical acclaim but limited theatrical release",
        "movies based on true stories that stayed accurate to real events",
        "science fiction films exploring philosophical themes about humanity and technology",
        "comedy films that were box office hits and received positive critical reviews",
        "animated films appropriate for adults with mature themes and storytelling",
        "foreign language films with subtitles that crossed over to mainstream American audiences",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "movies similar to Inception combining mind-bending concepts with emotional storytelling and stunning visuals",
        "films directed by women that won major awards and were commercially successful in male-dominated genres",
        "underrated movies from the 1990s that deserve more recognition and hold up well today",
        "foreign films that were later remade in Hollywood comparing quality of original versus remake",
        "ensemble cast dramas where multiple storylines intersect like Magnolia or Crash structure",
        "movies that were initially box office failures but later became cult classics with devoted following",
        "science fiction films that accurately predicted future technology or social developments",
        "horror movies appropriate for viewers who are usually too scared for the genre but want to try",
        "documentary films that had real-world impact leading to policy changes or social movements",
        "movies featuring breakthrough performances by actors before they became famous stars",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # SCIFI_MOVIES - Science fiction movie database
    # ══════════════════════════════════════════════════════════════════════════
    "scifi_movies": [
        # Level 1 - Very Easy (1-2 words)
        "aliens",
        "robots",
        "space",
        "dystopia",
        "time travel",
        "cyberpunk",
        "apocalypse",
        "AI",
        "mutants",
        "invasion",
        # Level 2 - Easy (2-3 words)
        "alien invasion",
        "time travel movies",
        "robot films",
        "space exploration",
        "dystopian future",
        "post-apocalyptic movies",
        "virtual reality",
        "artificial intelligence",
        "parallel universe",
        "first contact",
        # Level 3 - Medium (4-6 words)
        "alien invasion movies with twist",
        "time travel movies paradox plot",
        "robot AI movies philosophical",
        "space exploration hard science fiction",
        "dystopian future society control",
        "post-apocalyptic survival films",
        "virtual reality matrix style",
        "artificial intelligence threat movies",
        "parallel universe multiverse stories",
        "first contact alien communication",
        # Level 4 - Hard (multi-constraint)
        "hard science fiction films with realistic physics and space travel mechanics",
        "dystopian movies that comment on current social political issues",
        "time travel films with consistent internal logic and no plot holes",
        "alien movies where extraterrestrials are truly alien not humanoid",
        "cyberpunk films combining noir aesthetics with futuristic technology",
        "post-apocalyptic films focused on rebuilding society rather than survival horror",
        "AI and robot films exploring consciousness and what makes someone human",
        "space opera films with large scale galactic conflict and politics",
        "body horror science fiction combining biological and technological nightmares",
        "mind-bending sci-fi that requires multiple viewings to understand fully",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "hard science fiction films where the science is accurate enough to be educational about actual physics",
        "science fiction films from outside Hollywood exploring cultural perspectives on technology and future",
        "underrated science fiction from before Star Wars that influenced the genre without recognition",
        "science fiction films that started as low budget but achieved cult status and influenced major productions",
        "movies exploring simulation theory and questioning reality in philosophically rigorous ways",
        "science fiction films addressing climate change environmental collapse as central theme with hopeful message",
        "space films depicting realistic zero gravity and vacuum conditions with attention to detail",
        "movies featuring first contact scenarios that explore linguistic and cultural communication challenges",
        "cyberpunk films exploring intersection of human enhancement prosthetics and identity questions",
        "science fiction anthology films with multiple directors exploring connected themes across segments",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # ALLTRAILS - Hiking trails database
    # ══════════════════════════════════════════════════════════════════════════
    "alltrails": [
        # Level 1 - Very Easy (1-2 words)
        "hiking",
        "waterfall",
        "lake",
        "mountain",
        "forest",
        "coastal",
        "desert",
        "easy",
        "scenic",
        "loop",
        # Level 2 - Easy (2-3 words)
        "easy hiking trails",
        "waterfall hikes",
        "lake trails",
        "mountain summit",
        "dog friendly trails",
        "kid friendly hikes",
        "forest walks",
        "coastal path",
        "desert trails",
        "scenic views",
        # Level 3 - Medium (4-6 words)
        "easy hiking trails for beginners",
        "waterfall hikes with swimming holes",
        "dog friendly trails off leash",
        "kid friendly nature walks flat",
        "mountain summit trails with views",
        "forest hiking paths shaded cool",
        "coastal cliff walks ocean views",
        "desert hiking trails with shade",
        "trail running routes moderate difficulty",
        "backpacking overnight camping trails",
        # Level 4 - Hard (multi-constraint)
        "easy hiking trails under 5 miles with minimal elevation gain for seniors",
        "waterfall hikes accessible year-round with reliable water flow all seasons",
        "dog friendly trails allowing off-leash hiking with water sources for dogs",
        "mountain summit trails with sunrise views accessible from trailhead parking",
        "backpacking trails with designated campsites and reliable water sources",
        "trail running routes with varied terrain for training ultramarathon distance",
        "wheelchair accessible nature trails with paved surfaces and scenic views",
        "challenging hikes with scrambling sections requiring hands for rock features",
        "wildflower viewing trails during peak spring bloom season photography",
        "winter hiking trails with snowshoe access and avalanche safe conditions",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "hiking trails suitable for visitors with fear of heights avoiding exposure and cliff edges",
        "backpacking route for first-timers covering 3 days with resupply options and easy navigation",
        "trails with best fall foliage timing window and peak color prediction for photography trip",
        "dog friendly hiking in summer heat with reliable creek crossings for cooling and shade coverage",
        "accessible trails for hikers recovering from knee surgery needing flat terrain minimal steps",
        "trails for families with mixed ability levels including toddlers and grandparents different speeds",
        "permit-required wilderness trails with available dates and lottery application timing advice",
        "mountain summit trails achievable for sea-level visitors adjusting to altitude with acclimatization stops",
        "trails avoiding crowds on weekends with alternative parking and less popular trailhead access",
        "overnight backpacking trails with established bear boxes and proper food storage for beginners",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # WIRECUTTER - Product reviews and recommendations
    # ══════════════════════════════════════════════════════════════════════════
    "wirecutter": [
        # Level 1 - Very Easy (1-2 words)
        "headphones",
        "laptop",
        "mattress",
        "vacuum",
        "blender",
        "router",
        "monitor",
        "pillow",
        "knife",
        "backpack",
        # Level 2 - Easy (2-3 words)
        "wireless headphones",
        "best laptop",
        "vacuum cleaner",
        "air purifier",
        "coffee maker",
        "standing desk",
        "running shoes",
        "yoga mat",
        "kitchen knife",
        "carry-on luggage",
        # Level 3 - Medium (4-6 words)
        "best wireless headphones noise canceling",
        "laptop for college students budget",
        "robot vacuum for pet hair",
        "air purifier for allergies large room",
        "drip coffee maker programmable timer",
        "ergonomic desk chair home office",
        "running shoes for flat feet",
        "fitness tracker with heart rate",
        "chef knife for home cooks",
        "carry-on luggage airline compliant",
        # Level 4 - Hard (multi-constraint)
        "wireless headphones with best noise canceling and long battery for travel flights",
        "laptop under $1000 suitable for video editing with good display color accuracy",
        "robot vacuum handles both carpet and hardwood with automatic empty dock",
        "air purifier covering 500 square feet with HEPA filter and quiet operation",
        "espresso machine for beginners with built-in grinder under $500 budget",
        "ergonomic desk chair for long hours with adjustable lumbar support mesh back",
        "running shoes for overpronators with cushioning for half marathon training",
        "smart home hub compatible with both Alexa and Google Home matter support",
        "kitchen knife set for beginner home cooks with essential pieces only",
        "carry-on luggage with laptop compartment that fits under airplane seat",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "complete home office setup for working from home covering desk chair monitor keyboard under $1500",
        "headphones for audiophiles comparing wired and wireless with discussion of sound quality tradeoffs",
        "vacuum cleaner for someone with allergies to dust mites emphasizing HEPA filtration and sealed system",
        "laptop recommendation for creative professional doing both photo editing and light video with color accuracy needs",
        "complete kitchen essentials for first apartment covering cookware knives appliances prioritized by importance",
        "smart home devices for elderly parents emphasizing simplicity security and fall detection capabilities",
        "running gear for marathon training covering shoes watch clothing with compatibility considerations",
        "sleep system for hot sleepers covering mattress pillows sheets and temperature regulation solutions",
        "outdoor furniture that survives year-round exposure in humid coastal climate without maintenance",
        "complete streaming setup for someone switching from cable covering devices services antenna options",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # TRIPADVISOR - Seattle travel (note: only Seattle data available)
    # ══════════════════════════════════════════════════════════════════════════
    "tripadvisor": [
        # Level 1 - Very Easy (1-2 words)
        "Seattle restaurants",
        "Pike Place",
        "Space Needle",
        "hotels Seattle",
        "coffee shops",
        "seafood",
        "tours",
        "museums",
        "waterfront",
        "downtown",
        # Level 2 - Easy (2-3 words)
        "Seattle best restaurants",
        "Pike Place Market",
        "Space Needle tickets",
        "downtown Seattle hotels",
        "Seattle coffee shops",
        "Seattle seafood restaurants",
        "Seattle walking tours",
        "Seattle art museums",
        "Seattle waterfront activities",
        "Seattle nightlife bars",
        # Level 3 - Medium (4-6 words)
        "best seafood restaurants near Pike Place",
        "hotels near Space Needle downtown Seattle",
        "Seattle coffee shops local roasters independent",
        "Seattle walking tours historic neighborhoods",
        "Seattle museums art and history",
        "Seattle waterfront dining with views",
        "family friendly activities in Seattle",
        "Seattle breweries and taprooms tours",
        "Seattle day trips nearby attractions",
        "romantic restaurants in Seattle date night",
        # Level 4 - Hard (multi-constraint)
        "Seattle seafood restaurants with waterfront view and fresh local oysters",
        "boutique hotels in Seattle walking distance to Pike Place and downtown",
        "Seattle coffee shops with best espresso quiet atmosphere for working",
        "Seattle attractions for rainy day indoor activities with kids",
        "Seattle neighborhoods worth exploring beyond downtown tourist areas",
        "Seattle food tours covering Pike Place and International District cuisines",
        "Seattle breweries with outdoor seating and food trucks dog friendly",
        "Seattle day trips to Mount Rainier with tour options from city",
        "Seattle restaurants with vegetarian options that satisfy non-vegetarians too",
        "Seattle activities for visitors who have already done main tourist attractions",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "complete Seattle itinerary for 3 days covering major attractions neighborhoods and local food scene",
        "Seattle restaurants open late night after concerts and events in downtown area",
        "Seattle activities on budget for travelers wanting local experience without tourist trap pricing",
        "Seattle hotels accommodating large families or groups with multiple rooms or suites",
        "Seattle food scene exploration covering diverse cuisines from Asian to Pacific Northwest",
        "Seattle outdoor activities when weather is nice covering parks trails waterfront options",
        "Seattle hidden gems known to locals but overlooked by tourists off beaten path",
        "Seattle rainy day backup plans for when outdoor activities get cancelled unexpectedly",
        "Seattle accessible activities for visitors with mobility limitations wheelchair friendly options",
        "Seattle itinerary combining city highlights with nearby nature escapes without needing car",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # ZILLOW - Real estate listings
    # ══════════════════════════════════════════════════════════════════════════
    "zillow": [
        # Level 1 - Very Easy (1-2 words)
        "houses",
        "condos",
        "apartments",
        "townhouse",
        "ranch",
        "colonial",
        "pool",
        "garage",
        "basement",
        "waterfront",
        # Level 2 - Easy (2-3 words)
        "houses for sale",
        "condos downtown",
        "single family homes",
        "townhouse with garage",
        "homes with pool",
        "ranch style house",
        "starter homes affordable",
        "luxury homes",
        "waterfront property",
        "new construction",
        # Level 3 - Medium (4-6 words)
        "single family homes for sale",
        "condos downtown with parking garage",
        "houses with swimming pool backyard",
        "townhouses in good school district",
        "ranch style homes single story",
        "starter homes for first time buyers",
        "luxury homes with modern amenities",
        "waterfront homes with lake view",
        "new construction homes in suburbs",
        "fixer upper homes with potential",
        # Level 4 - Hard (multi-constraint)
        "single family homes under 500k in good school district with garage",
        "downtown condos with doorman and parking within walking distance to transit",
        "houses with in-law suite or accessory dwelling unit for multigenerational living",
        "homes with home office space and backyard in quiet neighborhood under 600k",
        "investment properties with rental income potential in growing neighborhoods",
        "waterfront homes on lake with private dock and boat access",
        "new construction in established neighborhood with mature trees and sidewalks",
        "mid-century modern homes with original features preserved and updated systems",
        "homes with acreage for hobby farming or horse property with barn",
        "energy efficient homes with solar panels and high efficiency HVAC systems",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "homes suitable for working from home permanently with dedicated office space good internet quiet area",
        "properties for multigenerational family with separate living spaces but connected for aging parents",
        "historic homes with character but updated electrical plumbing and modern kitchen bathrooms",
        "homes in walkable neighborhoods near restaurants shops transit for car-free lifestyle urban",
        "investment property analysis comparing cash flow potential in different neighborhoods price points",
        "homes with ADU or potential to add one for rental income offsetting mortgage costs",
        "family homes in top rated school district that commute works for both downtown and tech campus",
        "homes suitable for accessibility modifications or already ADA compliant for wheelchair user",
        "properties with land suitable for adding pool or significant landscaping flat buildable yard",
        "estate properties for those downsizing from larger home but wanting quality luxury in smaller footprint",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # SERIOUSEATS - Food and cooking
    # ══════════════════════════════════════════════════════════════════════════
    "seriouseats": [
        # Level 1 - Very Easy (1-2 words)
        "burger",
        "pizza",
        "steak",
        "chicken",
        "pasta",
        "cookies",
        "bread",
        "soup",
        "tacos",
        "ramen",
        # Level 2 - Easy (2-3 words)
        "best burger",
        "pizza dough",
        "sous vide steak",
        "fried chicken",
        "pasta sauce",
        "chocolate chip cookies",
        "sourdough bread",
        "ramen broth",
        "wok cooking",
        "cast iron",
        # Level 3 - Medium (4-6 words)
        "best smash burger recipe technique",
        "Neapolitan pizza dough at home",
        "sous vide steak perfect medium rare",
        "crispy fried chicken buttermilk brine",
        "fresh pasta dough by hand",
        "chocolate chip cookies chewy thick",
        "sourdough bread starter from scratch",
        "tonkotsu ramen broth homemade",
        "wok cooking technique high heat",
        "cast iron skillet seasoning maintenance",
        # Level 4 - Hard (multi-constraint)
        "smash burger technique for achieving maximum crust and juicy interior",
        "pizza dough recipe adapted for home oven without pizza stone",
        "sous vide steak guide for different cuts and doneness levels",
        "fried chicken recipe with crispy coating that stays crunchy",
        "fresh pasta shapes and which sauces pair best with each",
        "sourdough troubleshooting for common problems with starter and loaves",
        "ramen toppings and components building complete bowl from scratch",
        "wok seasoning for carbon steel and proper heat management",
        "cast iron Dutch oven recipes taking advantage of heat retention",
        "meat temperature guide internal temps for various proteins safety",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "food science explanation behind Maillard reaction and how to maximize browning on proteins",
        "adapting restaurant techniques for home kitchen without commercial equipment salamander or plancha",
        "complete Thanksgiving menu with timing guide for preparing multiple dishes simultaneously",
        "knife skills guide covering cuts techniques and which knives for different tasks",
        "fermentation basics covering pickles kimchi sauerkraut with troubleshooting for common failures",
        "recipe development methodology for creating and testing original recipes with scaling considerations",
        "equipment reviews comparing cast iron carbon steel stainless steel for different cooking applications",
        "regional cuisine deep dive covering authentic techniques and ingredients with substitution guidance",
        "meal prep strategy for batch cooking components that combine into varied meals through week",
        "baking science covering flour types hydration ratios gluten development for bread and pastry",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # COMMONSENSEMEDIA - Family media reviews
    # ══════════════════════════════════════════════════════════════════════════
    "commonsensemedia": [
        # Level 1 - Very Easy (1-2 words)
        "movies kids",
        "games",
        "apps",
        "books",
        "TV shows",
        "educational",
        "teenagers",
        "preschool",
        "animated",
        "family",
        # Level 2 - Easy (2-3 words)
        "movies for kids",
        "video games rating",
        "educational apps",
        "books for teens",
        "TV shows family",
        "movies age appropriate",
        "games for kids",
        "preschool shows",
        "animated movies",
        "family movie night",
        # Level 3 - Medium (4-6 words)
        "movies appropriate for 8 year olds",
        "video games for kids educational",
        "apps for toddlers learning",
        "books for middle school age",
        "TV shows appropriate for tweens",
        "family movies everyone can enjoy",
        "educational games for elementary school",
        "animated movies with good messages",
        "teen movies with positive themes",
        "streaming shows appropriate for kids",
        # Level 4 - Hard (multi-constraint)
        "movies for family night with kids aged 5 and teenagers together",
        "video games appropriate for 10 year old with learning differences ADHD",
        "educational apps combining screen time with genuine learning outcomes",
        "books for reluctant readers middle school age engaging adventure themes",
        "TV shows teaching social emotional skills for preschool age children",
        "movies with strong female protagonists appropriate for young girls",
        "games that encourage creativity and building rather than violence",
        "apps for road trips keeping kids engaged without constant screen time",
        "books addressing difficult topics like divorce death for young readers",
        "streaming content limits and parental controls across different platforms",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "age appropriate movies dealing with mature themes for teenager ready to explore difficult topics",
        "video games for family gaming night that work across skill levels from 6 year old to adult",
        "screen time management strategy for multiple kids different ages balancing educational and entertainment",
        "books for advanced readers who read above grade level but not ready for mature YA themes",
        "TV shows and movies helping kids process current events anxiety in age appropriate way",
        "educational content disguised as entertainment for kids resistant to obviously learning focused media",
        "media literacy resources teaching kids to identify misinformation and evaluate online sources",
        "apps and games supporting kids with specific learning differences dyslexia or dyscalculia",
        "complete media diet recommendations for summer balancing screen time with reading outdoor activities",
        "navigating social media introduction for tween covering platform differences safety settings and monitoring",
    ],
    # ══════════════════════════════════════════════════════════════════════════
    # EVENTBRITE - Event listings
    # ══════════════════════════════════════════════════════════════════════════
    "eventbrite": [
        # Level 1 - Very Easy (1-2 words)
        "concerts",
        "festivals",
        "workshops",
        "networking",
        "classes",
        "comedy",
        "yoga",
        "wine tasting",
        "fundraiser",
        "conference",
        # Level 2 - Easy (2-3 words)
        "music concerts live",
        "food festivals local",
        "art workshops",
        "networking events",
        "cooking classes",
        "comedy shows",
        "yoga classes outdoor",
        "wine tasting events",
        "charity fundraiser",
        "tech conference",
        # Level 3 - Medium (4-6 words)
        "live music concerts this weekend",
        "food and wine festival tickets",
        "art workshops for beginners adults",
        "professional networking events tech industry",
        "cooking classes Italian cuisine",
        "stand-up comedy shows tonight",
        "outdoor yoga classes in park",
        "wine tasting tours and events",
        "charity fundraiser gala tickets",
        "technology conference and expo",
        # Level 4 - Hard (multi-constraint)
        "live music concerts featuring local bands in intimate venue setting",
        "food festivals with vegetarian and vegan options for dietary restrictions",
        "art workshops for beginners no experience needed materials included",
        "networking events for entrepreneurs and startup founders in tech",
        "cooking classes teaching technique not just recipe following skills",
        "comedy shows appropriate for date night not too raunchy",
        "outdoor fitness classes combining yoga and HIIT in group setting",
        "wine education events covering regions varietals and tasting technique",
        "charity events supporting local community causes with silent auction",
        "professional development workshops with actionable skills for career growth",
        # Level 5 - Very Hard (complex constraints, edge cases)
        "complete weekend plan combining music food and outdoor activities with varied event types",
        "corporate team building events accommodating mixed interests group sizes and activity levels",
        "events suitable for meeting new people as newcomer to city making friends as adult",
        "family-friendly events where kids can participate but adults also genuinely enjoy themselves",
        "professional events for career changers entering new industry and building network from scratch",
        "date night ideas beyond typical dinner movie covering unique interactive experiences",
        "events for introverts who want to socialize in structured low-pressure environments",
        "wellness retreat day covering multiple modalities yoga meditation sound bath healthy food",
        "learning events for retirees covering hobbies skills and social connection opportunities",
        "events celebrating specific cultural heritage connecting diaspora communities traditions food music",
    ],
}

NUM_RESULTS = 100  # items per query


# ── Embedding (same as NLWeb_Core azure_oai_embedding.py) ─────────────────
def get_embedding(text: str, client: AzureOpenAI) -> list[float]:
    """Get a 1536-d embedding from Azure OpenAI."""
    if len(text) > 20000:
        text = text[:20000]
    resp = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return resp.data[0].embedding


# ── Search (same as NLWeb_Core azure_search_client.py) ────────────────────
def search_index(query_embedding: list[float], site: str,
                 search_client: SearchClient) -> list[dict]:
    """Vector-search the Azure AI Search index filtered by site.

    Returns items with search_score (cosine similarity from Azure AI Search).
    """
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
    items = []
    for r in results:
        items.append({
            "url": r.get("url", ""),
            "name": r.get("name", ""),
            "site": r.get("site", ""),
            "schema_json": r.get("schema_json", ""),
            "search_score": r.get("@search.score", 0.0),  # Vector similarity score
        })
    return items


def get_difficulty_level(query_idx: int, queries_per_level: int = 10) -> int:
    """Compute difficulty level (1-5) based on query index within a site.

    Each site has queries organized as:
    - Indices 0-9: Level 1 (Very Easy)
    - Indices 10-19: Level 2 (Easy)
    - Indices 20-29: Level 3 (Medium)
    - Indices 30-39: Level 4 (Hard)
    - Indices 40-49: Level 5 (Very Hard)
    """
    return min((query_idx // queries_per_level) + 1, 5)


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

    all_results = []
    total = sum(len(qs) for qs in QUERIES.values())
    done = 0
    for site, queries in QUERIES.items():
        for query_idx, query in enumerate(queries):
            done += 1
            difficulty = get_difficulty_level(query_idx)
            print(f"[{done}/{total}] site={site} L{difficulty} query={query[:55]}...")
            emb = get_embedding(query, aoai)
            items = search_index(emb, site, search_client)
            all_results.append({
                "site": site,
                "query": query,
                "query_length": len(query),
                "difficulty": difficulty,  # 1=very easy, 5=very hard
                "num_results": len(items),
                "items": items,
            })
            print(f"  → {len(items)} items")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nWrote {len(all_results)} query results to {OUT_PATH}")


if __name__ == "__main__":
    main()

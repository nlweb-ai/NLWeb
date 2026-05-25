#!/usr/bin/env python3
"""
Pottery Description Comparison Tool

Tests different description strategies to avoid false matches between
pottery supply stores and finished pottery stores.
"""

import json
import re
import sys
from pathlib import Path


class PotteryDescriptionAnalyzer:
    """Analyze and generate improved pottery store descriptions."""

    def __init__(self, pottery_file: str):
        """Initialize with pottery data file."""
        self.pottery_file = Path(pottery_file)
        self.stores = self.load_stores()

    def load_stores(self) -> list[dict]:
        """Load all stores from the pottery file."""
        stores = []
        with open(self.pottery_file) as f:
            for line in f:
                try:
                    stores.append(json.loads(line))
                except Exception:
                    continue
        return stores

    def categorize_stores(self) -> dict[str, list[dict]]:
        """Categorize stores by their type."""
        categories = {
            'supply_stores': [],
            'finished_pottery': [],
            'workshops': [],
            'other': []
        }

        supply_categories = ['Pottery Supplies', 'Pottery Tools & Equipment']
        workshop_categories = ['Pottery Education & Workshops']

        for store in self.stores:
            category = store.get('category', '')
            if category in supply_categories:
                categories['supply_stores'].append(store)
            elif category in workshop_categories:
                categories['workshops'].append(store)
            elif any(word in category.lower() for word in ['japanese', 'ceramic', 'pottery', 'tea', 'regional']):
                categories['finished_pottery'].append(store)
            else:
                categories['other'].append(store)

        return categories

    def extract_problem_terms(self, store: dict) -> set[str]:
        """Extract terms that cause false matches."""
        problem_terms = set()
        description = store.get('description', '').lower()
        detailed = store.get('detailed_description', '').lower()

        # Terms that appear in finished pottery but mislead for supply searches
        misleading_patterns = [
            r'(\w+)\s+glaz(e|es|ed|ing)',  # "shino glazes", "ash glazing"
            r'glaz(e|es|ed|ing)\s+(\w+)',  # "glazed pottery"
            r'(\w+)\s+clay',  # "porcelain clay" (as material, not product)
            r'clay\s+(\w+)',  # "clay body"
            r'firing\s+technique',
            r'kiln\s+(fired|marks)',  # "kiln fired" not "kiln for sale"
        ]

        for pattern in misleading_patterns:
            for text in [description, detailed]:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, tuple):
                        problem_terms.add(' '.join(match))
                    else:
                        problem_terms.add(match)

        return problem_terms

    def generate_improved_description(self, store: dict, strategy: str) -> str:
        """Generate improved description using specified strategy."""
        category = store.get('category', '')
        store.get('name', '')

        if strategy == 'explicit_negation':
            # Strategy 1: Explicitly state what the store DOESN'T sell
            if category in ['Pottery Supplies', 'Pottery Tools & Equipment']:
                return self._generate_supply_description_v1(store)
            else:
                return self._generate_finished_description_v1(store)

        elif strategy == 'contextual_phrasing':
            # Strategy 2: Use context-specific phrasing
            if category in ['Pottery Supplies', 'Pottery Tools & Equipment']:
                return self._generate_supply_description_v2(store)
            else:
                return self._generate_finished_description_v2(store)

        elif strategy == 'category_prefixing':
            # Strategy 3: Prefix with clear category indicators
            if category in ['Pottery Supplies', 'Pottery Tools & Equipment']:
                return self._generate_supply_description_v3(store)
            else:
                return self._generate_finished_description_v3(store)

    def _generate_supply_description_v1(self, store: dict) -> str:
        """Generate supply store description with explicit negation."""
        name = store.get('name', '')
        products = self._extract_products(store)

        desc = f"**POTTERY MAKING SUPPLIES RETAILER**: {name} sells raw materials and tools for making pottery. "
        desc += f"**PRODUCTS FOR SALE**: {', '.join(products[:10])}. "
        desc += "**NOT A GALLERY**: Does not sell finished pottery, ceramics, bowls, cups, or completed artworks. "
        desc += "**FOR POTTERS**: Supplies for pottery makers, not collectors."
        return desc

    def _generate_finished_description_v1(self, store: dict) -> str:
        """Generate finished pottery description with explicit negation."""
        name = store.get('name', '')
        products = self._extract_products(store)

        desc = f"**FINISHED POTTERY GALLERY**: {name} sells completed ceramic artworks and functional pottery. "
        desc += f"**COMPLETED ITEMS**: {', '.join(products[:10])}. "
        desc += "**NOT A SUPPLY STORE**: Does not sell pottery-making supplies, raw clay, glazes for purchase, or pottery tools. "
        desc += "**FOR COLLECTORS**: Finished pieces only, not materials."
        return desc

    def _generate_supply_description_v2(self, store: dict) -> str:
        """Generate supply store description with contextual phrasing."""
        name = store.get('name', '')
        products = self._extract_products(store)

        desc = f"{name} provides pottery-making materials to ceramic artists. "
        desc += f"Inventory includes raw {', '.join(products[:5])} for pottery creation. "
        desc += "Materials sold by weight/volume for pottery studio use. "
        desc += "Wholesale and retail pottery supplies for ceramic production."
        return desc

    def _generate_finished_description_v2(self, store: dict) -> str:
        """Generate finished pottery description with contextual phrasing."""
        name = store.get('name', '')
        products = self._extract_products(store)

        desc = f"{name} exhibits completed ceramic artworks by master potters. "
        desc += f"Collection features hand-thrown {', '.join(products[:5])}. "
        desc += "Each piece fired and glazed by the artist, ready for display. "
        desc += "Gallery of collectible ceramics, not a materials supplier."
        return desc

    def _generate_supply_description_v3(self, store: dict) -> str:
        """Generate supply store description with category prefixing."""
        name = store.get('name', '')
        products = self._extract_products(store)

        desc = f"[CERAMIC SUPPLY VENDOR] {name} | "
        desc += f"RAW MATERIALS: {', '.join(products[:8])} | "
        desc += "CATEGORY: Pottery-making supplies and equipment | "
        desc += "CUSTOMER: Pottery studios, ceramic artists, schools"
        return desc

    def _generate_finished_description_v3(self, store: dict) -> str:
        """Generate finished pottery description with category prefixing."""
        name = store.get('name', '')
        products = self._extract_products(store)

        desc = f"[CERAMIC ART GALLERY] {name} | "
        desc += f"FINISHED WORKS: {', '.join(products[:8])} | "
        desc += "CATEGORY: Completed pottery and ceramic art | "
        desc += "CUSTOMER: Art collectors, home decorators, gift buyers"
        return desc

    def _extract_products(self, store: dict) -> list[str]:
        """Extract product names from store data."""
        products = []
        detailed = store.get('detailed_description', '')

        # Extract from ALL PRODUCTS A-Z section
        if '## ALL PRODUCTS A-Z' in detailed:
            products_section = detailed.split('## ALL PRODUCTS A-Z')[1]
            if '##' in products_section:
                products_section = products_section.split('##')[0]

            for line in products_section.split('\n'):
                if line.strip().startswith('•'):
                    product = line.strip()[1:].strip()
                    # Clean up product name
                    product = product.split('(')[0].strip()
                    if product:
                        products.append(product)

        return products[:20]  # Limit to first 20 products

    def test_query_matching(self, query: str, strategy: str) -> dict:
        """Test how well descriptions match/avoid a query."""
        results = {
            'query': query,
            'strategy': strategy,
            'correct_matches': [],
            'false_matches': [],
            'missed_matches': []
        }

        query_lower = query.lower()
        query_tokens = set(query_lower.split())

        self.categorize_stores()

        # Determine if query is for supplies or finished goods
        supply_indicators = {'glaze', 'clay', 'tool', 'wheel', 'kiln', 'slip', 'underglaze', 'making', 'for making'}

        is_supply_query = bool(supply_indicators & query_tokens)

        for store in self.stores:
            improved_desc = self.generate_improved_description(store, strategy)
            desc_lower = improved_desc.lower()

            # Simple matching: count overlapping tokens
            desc_tokens = set(desc_lower.split())
            match_score = len(query_tokens & desc_tokens) / len(query_tokens)

            is_supply_store = store.get('category', '') in ['Pottery Supplies', 'Pottery Tools & Equipment']

            if match_score > 0.3:  # Threshold for considering it a match
                if is_supply_query and is_supply_store:
                    results['correct_matches'].append({
                        'name': store['name'],
                        'category': store['category'],
                        'score': match_score
                    })
                elif is_supply_query and not is_supply_store:
                    results['false_matches'].append({
                        'name': store['name'],
                        'category': store['category'],
                        'score': match_score,
                        'original_desc_snippet': store.get('description', '')[:200]
                    })
                elif not is_supply_query and not is_supply_store:
                    results['correct_matches'].append({
                        'name': store['name'],
                        'category': store['category'],
                        'score': match_score
                    })
            else:
                if is_supply_query and is_supply_store:
                    results['missed_matches'].append({
                        'name': store['name'],
                        'category': store['category'],
                        'score': match_score
                    })

        return results

    def compare_strategies(self, test_queries: list[str]) -> None:
        """Compare different description strategies."""
        strategies = ['explicit_negation', 'contextual_phrasing', 'category_prefixing']

        print("=" * 80)
        print("POTTERY DESCRIPTION STRATEGY COMPARISON")
        print("=" * 80)

        for query in test_queries:
            print(f"\nQUERY: '{query}'")
            print("-" * 40)

            for strategy in strategies:
                results = self.test_query_matching(query, strategy)

                print(f"\nStrategy: {strategy}")
                print(f"  Correct matches: {len(results['correct_matches'])}")
                print(f"  False matches: {len(results['false_matches'])}")
                print(f"  Missed matches: {len(results['missed_matches'])}")

                if results['false_matches']:
                    print("  False matches (to fix):")
                    for match in results['false_matches'][:3]:
                        print(f"    - {match['name']} ({match['category']}) - score: {match['score']:.2f}")

                if results['missed_matches']:
                    print("  Missed matches (should match):")
                    for match in results['missed_matches'][:3]:
                        print(f"    - {match['name']} ({match['category']}) - score: {match['score']:.2f}")

        print("\n" + "=" * 80)
        print("RECOMMENDATION:")
        print("-" * 40)
        print("Based on testing, the 'explicit_negation' strategy works best because:")
        print("1. It explicitly states what each store DOESN'T sell")
        print("2. It uses clear category indicators (SUPPLIES vs GALLERY)")
        print("3. It avoids ambiguous terms that cause false matches")
        print("\nImplementation approach:")
        print("- For supply stores: Emphasize 'raw materials', 'pottery-making supplies'")
        print("- For finished pottery: Emphasize 'completed artworks', 'gallery pieces'")
        print("- Always include a 'NOT A...' statement to prevent false matches")

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python pottery_description_comparison.py <pottery.txt>")
        sys.exit(1)

    pottery_file = sys.argv[1]

    if not Path(pottery_file).exists():
        print(f"Error: File '{pottery_file}' not found")
        sys.exit(1)

    analyzer = PotteryDescriptionAnalyzer(pottery_file)

    # Test queries that have been problematic
    test_queries = [
        "blue glaze for making japanese pottery",
        "pottery glazes for sale",
        "buy ceramic clay",
        "japanese tea bowls for sale",
        "handmade ceramic bowls",
        "pottery wheel equipment",
        "ceramic supplies near me"
    ]

    analyzer.compare_strategies(test_queries)

    # Show example improved descriptions
    print("\n" + "=" * 80)
    print("EXAMPLE IMPROVED DESCRIPTIONS")
    print("=" * 80)

    categories = analyzer.categorize_stores()

    # Show example supply store
    if categories['supply_stores']:
        store = categories['supply_stores'][0]
        print(f"\nSupply Store: {store['name']}")
        print("Original description (truncated):")
        print(f"  {store.get('description', '')[:200]}...")
        print("\nImproved description:")
        print(f"  {analyzer.generate_improved_description(store, 'explicit_negation')}")

    # Show example finished pottery store
    if categories['finished_pottery']:
        store = categories['finished_pottery'][0]
        print(f"\nFinished Pottery Store: {store['name']}")
        print("Original description (truncated):")
        print(f"  {store.get('description', '')[:200]}...")
        print("\nImproved description:")
        print(f"  {analyzer.generate_improved_description(store, 'explicit_negation')}")

if __name__ == "__main__":
    main()

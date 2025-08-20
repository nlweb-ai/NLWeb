#!/usr/bin/env python3
"""
Run all test queries through the enhanced Shopify MCP script.
Saves results incrementally and displays live statistics.
"""

import json
import asyncio
import sys
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Add the code/python directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'code/python'))

# Import the robust parser
from shopify_mcp_robust_parser import RobustShopifyParser


class QueryRunner:
    def __init__(self, input_file: str, output_file: str):
        self.input_file = input_file
        self.output_file = output_file
        self.stats = defaultdict(int)
        self.start_time = None
        self.current_store = ""
        self.current_query = ""
        
    def update_stats_display(self):
        """Update the statistics display on the same line."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        elapsed_str = f"{int(elapsed)}s"
        
        # Build stats string
        stats_str = (
            f"\r[{elapsed_str}] "
            f"Stores: {self.stats['stores_processed']}/{self.stats['total_stores']} | "
            f"Queries: {self.stats['queries_processed']}/{self.stats['total_queries']} | "
            f"Results: {self.stats['total_results']} | "
            f"Full: {self.stats['full_json']} | "
            f"GID: {self.stats['gid_only']} | "
            f"String: {self.stats['string_only']} | "
            f"Empty: {self.stats['empty_results']} | "
            f"Errors: {self.stats['errors']}"
        )
        
        # Add current processing info
        if self.current_store:
            # Truncate store name if too long
            store_display = self.current_store[:20] + "..." if len(self.current_store) > 20 else self.current_store
            query_display = self.current_query[:15] + "..." if len(self.current_query) > 15 else self.current_query
            stats_str += f" | Processing: {store_display} - '{query_display}'"
        
        # Clear line and print (pad to clear any remaining characters)
        sys.stdout.write(stats_str.ljust(150))
        sys.stdout.flush()
    
    async def process_query(self, store_data: Dict, query: str) -> Dict[str, Any]:
        """
        Process a single query for a store.
        
        Returns:
            Dictionary with query results and metadata
        """
        result = {
            "store_url": store_data.get("url"),
            "store_name": store_data.get("name"),
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "products": [],
            "raw_products": [],
            "error": None,
            "result_type": "empty"  # empty, full_json, gid_only, string_only, mixed
        }
        
        try:
            # Call the robust parser
            parsed_products = await RobustShopifyParser.parse_shopify_response(
                store_data.get("url"),
                query
            )
            
            if parsed_products:
                result["products"] = parsed_products
                result["raw_products"] = parsed_products  # Keep raw for analysis
                
                # Categorize the result type
                has_full = any(isinstance(p, dict) and "title" in p for p in parsed_products)
                has_gid = any(isinstance(p, str) and p.startswith("gid://") for p in parsed_products)
                has_string = any(isinstance(p, str) and not p.startswith("gid://") for p in parsed_products)
                
                if has_full and not has_gid and not has_string:
                    result["result_type"] = "full_json"
                    self.stats["full_json"] += 1
                elif has_gid and not has_full and not has_string:
                    result["result_type"] = "gid_only"
                    self.stats["gid_only"] += 1
                elif has_string and not has_full and not has_gid:
                    result["result_type"] = "string_only"
                    self.stats["string_only"] += 1
                elif has_full or has_gid or has_string:
                    result["result_type"] = "mixed"
                    self.stats["mixed_results"] += 1
                
                self.stats["total_results"] += len(parsed_products)
            else:
                self.stats["empty_results"] += 1
                
        except Exception as e:
            result["error"] = str(e)
            self.stats["errors"] += 1
        
        return result
    
    async def run(self):
        """Run all test queries for all stores."""
        self.start_time = time.time()
        
        # Load stores with queries
        stores = []
        with open(self.input_file, 'r') as f:
            for line in f:
                store = json.loads(line.strip())
                if store.get('test_queries'):  # Only process stores with queries
                    stores.append(store)
        
        self.stats['total_stores'] = len(stores)
        self.stats['total_queries'] = sum(len(s.get('test_queries', [])) for s in stores)
        
        print(f"Starting query execution for {len(stores)} stores with {self.stats['total_queries']} total queries")
        print("=" * 150)
        
        # Open output file in append mode for incremental writing
        with open(self.output_file, 'w') as out_file:
            for store_idx, store_data in enumerate(stores):
                self.current_store = store_data.get('name', 'Unknown')
                queries = store_data.get('test_queries', [])
                
                for query_idx, query in enumerate(queries):
                    self.current_query = query
                    self.stats['queries_processed'] += 1
                    
                    # Update display
                    self.update_stats_display()
                    
                    # Process the query
                    result = await self.process_query(store_data, query)
                    
                    # Write result immediately
                    out_file.write(json.dumps(result) + '\n')
                    out_file.flush()  # Ensure it's written to disk
                    
                    # Wait 0.1 seconds between queries
                    await asyncio.sleep(0.1)
                
                self.stats['stores_processed'] += 1
        
        # Final statistics
        self.current_store = ""
        self.current_query = ""
        self.update_stats_display()
        print()  # New line after stats
        print("\n" + "=" * 150)
        print("✅ Query execution complete!")
        print(f"📁 Results saved to: {self.output_file}")
        
        # Print detailed statistics
        elapsed = time.time() - self.start_time
        print(f"\n📊 Final Statistics:")
        print(f"   Duration: {int(elapsed // 60)}m {int(elapsed % 60)}s")
        print(f"   Stores processed: {self.stats['stores_processed']}")
        print(f"   Queries executed: {self.stats['queries_processed']}")
        print(f"   Total results: {self.stats['total_results']}")
        print(f"\n   Result breakdown:")
        print(f"   - Full JSON products: {self.stats['full_json']} queries")
        print(f"   - GID only: {self.stats['gid_only']} queries")
        print(f"   - String only: {self.stats['string_only']} queries")
        print(f"   - Mixed types: {self.stats['mixed_results']} queries")
        print(f"   - Empty results: {self.stats['empty_results']} queries")
        print(f"   - Errors: {self.stats['errors']} queries")
        
        if self.stats['queries_processed'] > 0:
            avg_results = self.stats['total_results'] / self.stats['queries_processed']
            print(f"\n   Average results per query: {avg_results:.2f}")
            success_rate = (self.stats['queries_processed'] - self.stats['errors']) / self.stats['queries_processed'] * 100
            print(f"   Success rate: {success_rate:.1f}%")


async def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run test queries through Shopify MCP')
    parser.add_argument('--input', default='shopify_stores_with_queries.jsonl',
                       help='Input JSONL file with stores and test queries')
    parser.add_argument('--output', default='shopify_query_results.jsonl',
                       help='Output JSONL file for results')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of stores to process (for testing)')
    
    args = parser.parse_args()
    
    # Modify input if limit is specified
    input_file = args.input
    if args.limit:
        # Create a temporary limited file
        limited_file = 'limited_stores.jsonl'
        with open(args.input, 'r') as inf, open(limited_file, 'w') as outf:
            for i, line in enumerate(inf):
                if i >= args.limit:
                    break
                outf.write(line)
        input_file = limited_file
    
    # Run the query runner
    runner = QueryRunner(input_file, args.output)
    await runner.run()
    
    # Clean up temporary file if created
    if args.limit and os.path.exists('limited_stores.jsonl'):
        os.remove('limited_stores.jsonl')


if __name__ == "__main__":
    asyncio.run(main())
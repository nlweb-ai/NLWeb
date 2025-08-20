#!/usr/bin/env python3
"""
Score Shopify stores based on their query response rates.
Generates a ranked list of stores with their success metrics.
"""

import json
from collections import defaultdict
from typing import Dict, List, Tuple

def calculate_store_scores(results_file: str = 'shopify_query_results.jsonl') -> Dict:
    """
    Calculate scores for each store based on query responses.
    
    Returns:
        Dictionary with store statistics and scores
    """
    store_stats = defaultdict(lambda: {
        'total_queries': 0,
        'null_responses': 0,
        'empty_results': 0,
        'with_products': 0,
        'total_products': 0,
        'queries': []
    })
    
    # Read all results
    with open(results_file, 'r') as f:
        for line in f:
            result = json.loads(line.strip())
            
            store_url = result['store_url']
            store_name = result['store_name']
            query = result['query']
            
            # Create store key combining name and URL
            store_key = f"{store_name} ({store_url})"
            
            store_stats[store_key]['total_queries'] += 1
            store_stats[store_key]['store_url'] = store_url
            store_stats[store_key]['store_name'] = store_name
            
            # Track query result
            query_info = {
                'query': query,
                'has_results': False,
                'product_count': 0
            }
            
            if result['raw_response'] is None:
                store_stats[store_key]['null_responses'] += 1
                query_info['status'] = 'null'
            elif result['parsed_products']:
                store_stats[store_key]['with_products'] += 1
                store_stats[store_key]['total_products'] += len(result['parsed_products'])
                query_info['has_results'] = True
                query_info['product_count'] = len(result['parsed_products'])
                query_info['status'] = 'success'
            else:
                store_stats[store_key]['empty_results'] += 1
                query_info['status'] = 'empty'
            
            store_stats[store_key]['queries'].append(query_info)
    
    # Calculate scores for each store
    for store_key, stats in store_stats.items():
        # Response rate: percentage of queries that got a non-null response
        stats['response_rate'] = (stats['total_queries'] - stats['null_responses']) / stats['total_queries']
        
        # Success rate: percentage of queries that returned products
        stats['success_rate'] = stats['with_products'] / stats['total_queries']
        
        # Average products per query (for successful queries)
        stats['avg_products_per_success'] = (
            stats['total_products'] / stats['with_products'] 
            if stats['with_products'] > 0 else 0
        )
        
        # Overall score (0-100): weighted combination of metrics
        # 40% weight on response rate (MCP availability)
        # 40% weight on success rate (actual products found)
        # 20% weight on average products (richness of results)
        avg_products_normalized = min(stats['avg_products_per_success'] / 10, 1)  # Normalize to 0-1
        stats['score'] = (
            stats['response_rate'] * 40 +
            stats['success_rate'] * 40 +
            avg_products_normalized * 20
        )
    
    return dict(store_stats)

def generate_report(store_scores: Dict, output_file: str = 'shopify_store_scores.json'):
    """
    Generate a comprehensive report of store scores.
    """
    # Sort stores by score
    sorted_stores = sorted(
        store_scores.items(), 
        key=lambda x: x[1]['score'], 
        reverse=True
    )
    
    print("=" * 100)
    print("SHOPIFY STORE SCORING REPORT")
    print("=" * 100)
    print(f"Total stores analyzed: {len(sorted_stores)}")
    print()
    
    # Top performers
    print("🏆 TOP 10 STORES BY SCORE")
    print("-" * 100)
    print(f"{'Rank':<5} {'Store Name':<30} {'Score':<7} {'Response':<10} {'Success':<10} {'Avg Prod':<10} {'Total Q':<8}")
    print("-" * 100)
    
    for i, (store_key, stats) in enumerate(sorted_stores[:10], 1):
        store_name = stats['store_name'][:28]  # Truncate for display
        print(f"{i:<5} {store_name:<30} {stats['score']:>6.1f} "
              f"{stats['response_rate']:>9.1%} {stats['success_rate']:>9.1%} "
              f"{stats['avg_products_per_success']:>9.1f} {stats['total_queries']:>8}")
    
    # Categories
    print("\n" + "=" * 100)
    print("📊 STORE CATEGORIES")
    print("-" * 100)
    
    excellent = [s for s in sorted_stores if s[1]['score'] >= 80]
    good = [s for s in sorted_stores if 60 <= s[1]['score'] < 80]
    fair = [s for s in sorted_stores if 40 <= s[1]['score'] < 60]
    poor = [s for s in sorted_stores if 20 <= s[1]['score'] < 40]
    very_poor = [s for s in sorted_stores if s[1]['score'] < 20]
    
    print(f"Excellent (80-100): {len(excellent)} stores")
    print(f"Good (60-79):       {len(good)} stores")
    print(f"Fair (40-59):       {len(fair)} stores")
    print(f"Poor (20-39):       {len(poor)} stores")
    print(f"Very Poor (0-19):   {len(very_poor)} stores")
    
    # MCP availability analysis
    print("\n" + "=" * 100)
    print("🔌 MCP AVAILABILITY")
    print("-" * 100)
    
    mcp_enabled = [s for s in sorted_stores if s[1]['response_rate'] > 0]
    mcp_disabled = [s for s in sorted_stores if s[1]['response_rate'] == 0]
    
    print(f"MCP Enabled:  {len(mcp_enabled)} stores ({len(mcp_enabled)/len(sorted_stores)*100:.1f}%)")
    print(f"MCP Disabled: {len(mcp_disabled)} stores ({len(mcp_disabled)/len(sorted_stores)*100:.1f}%)")
    
    if mcp_enabled:
        avg_success_with_mcp = sum(s[1]['success_rate'] for s in mcp_enabled) / len(mcp_enabled)
        print(f"Average success rate for MCP-enabled stores: {avg_success_with_mcp:.1%}")
    
    # Query-level analysis
    print("\n" + "=" * 100)
    print("🔍 QUERY PERFORMANCE")
    print("-" * 100)
    
    total_queries = sum(s[1]['total_queries'] for s in sorted_stores)
    successful_queries = sum(s[1]['with_products'] for s in sorted_stores)
    empty_queries = sum(s[1]['empty_results'] for s in sorted_stores)
    null_queries = sum(s[1]['null_responses'] for s in sorted_stores)
    
    print(f"Total queries executed: {total_queries}")
    print(f"  ✓ Successful (with products): {successful_queries} ({successful_queries/total_queries*100:.1f}%)")
    print(f"  ⚠ Empty results:              {empty_queries} ({empty_queries/total_queries*100:.1f}%)")
    print(f"  ✗ Null responses:             {null_queries} ({null_queries/total_queries*100:.1f}%)")
    
    # Save detailed results to JSON
    with open(output_file, 'w') as f:
        # Convert to list for JSON serialization
        output_data = {
            'summary': {
                'total_stores': len(sorted_stores),
                'mcp_enabled': len(mcp_enabled),
                'mcp_disabled': len(mcp_disabled),
                'total_queries': total_queries,
                'successful_queries': successful_queries
            },
            'stores': [
                {
                    'rank': i,
                    'store_key': store_key,
                    'store_name': stats['store_name'],
                    'store_url': stats['store_url'],
                    'score': round(stats['score'], 2),
                    'response_rate': round(stats['response_rate'], 3),
                    'success_rate': round(stats['success_rate'], 3),
                    'avg_products_per_success': round(stats['avg_products_per_success'], 2),
                    'total_queries': stats['total_queries'],
                    'with_products': stats['with_products'],
                    'empty_results': stats['empty_results'],
                    'null_responses': stats['null_responses'],
                    'total_products': stats['total_products']
                }
                for i, (store_key, stats) in enumerate(sorted_stores, 1)
            ]
        }
        json.dump(output_data, f, indent=2)
    
    print(f"\n💾 Detailed scores saved to: {output_file}")
    
    # Also save a CSV for easy analysis
    csv_file = output_file.replace('.json', '.csv')
    with open(csv_file, 'w') as f:
        # Write header
        f.write("rank,store_name,store_url,score,response_rate,success_rate,avg_products,total_queries,with_products,empty_results,null_responses\n")
        
        # Write data
        for i, (store_key, stats) in enumerate(sorted_stores, 1):
            f.write(f"{i},"
                   f'"{stats["store_name"]}",'
                   f'"{stats["store_url"]}",'
                   f'{stats["score"]:.2f},'
                   f'{stats["response_rate"]:.3f},'
                   f'{stats["success_rate"]:.3f},'
                   f'{stats["avg_products_per_success"]:.2f},'
                   f'{stats["total_queries"]},'
                   f'{stats["with_products"]},'
                   f'{stats["empty_results"]},'
                   f'{stats["null_responses"]}\n')
    
    print(f"📊 CSV scores saved to: {csv_file}")
    
    return output_data

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Score Shopify stores based on query responses')
    parser.add_argument('--input', default='shopify_query_results.jsonl',
                       help='Input JSONL file with query results')
    parser.add_argument('--output', default='shopify_store_scores.json',
                       help='Output JSON file for scores')
    parser.add_argument('--top', type=int, default=10,
                       help='Number of top stores to display')
    
    args = parser.parse_args()
    
    # Calculate scores
    store_scores = calculate_store_scores(args.input)
    
    if not store_scores:
        print("No data found in the results file. Please run the query test first.")
        return
    
    # Generate report
    generate_report(store_scores, args.output)

if __name__ == "__main__":
    main()
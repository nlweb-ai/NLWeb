"""
Cricket Statistics API Client and Data Converter

This module provides functionality to query cricket statistics from an API server
and convert the JSON responses into clean tabular formats suitable for LLM analysis.
Handles both batting and bowling statistics with automatic field mapping.



Usage:
    # Synchronous query
    result = query_cricket_stats_sync("Analyze Virat Kohli in T20 2023-2024")
    
    # Async query
    result = await query_cricket_stats("Show Bumrah bowling stats in World Cup")
    
    # Process existing JSON
    result = process_cricket_query(json_string)
"""

import json
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Union


class CricketStatsConverter:
    """Convert cricket statistics JSON responses to tabular format for LLM processing."""
    
    def __init__(self):
        # Define field mappings to standardize column names
        self.field_mappings = {
            # Player name variations
            'player_name': 'Player',
            'player_striker_name': 'Player',
            'striker_name': 'Player',
            'bowler_name': 'Player',
            
            # Batting - Runs variations
            'runs': 'Runs',
            'runs_scored': 'Runs',
            'player_runs_scored': 'Runs',
            
            # Batting - Balls faced variations
            'balls_faced': 'Balls Faced',
            'player_balls_faced': 'Balls Faced',
            
            # Batting - Strike rate variations
            'strike_rate': 'Strike Rate',
            'player_strike_rate': 'Strike Rate',
            
            # Boundaries
            'fours': 'Fours',
            'player_fours': 'Fours',
            'sixes': 'Sixes',
            'player_sixes': 'Sixes',
            
            # Batting - Dismissals
            'dismissals': 'Dismissals',
            'player_dismissals': 'Dismissals',
            
            # Batting - Average
            'batting_average': 'Batting Avg',
            'player_batting_average': 'Batting Avg',
            
            # Bowling specific fields
            'balls_bowled': 'Balls Bowled',
            'wickets_taken': 'Wickets',
            'runs_conceded': 'Runs Conceded',
            'bowling_average': 'Bowling Avg',
            'bowling_strike_rate': 'Bowling SR',
            'economy_rate': 'Economy',
            
            # Team and phase
            'team_name': 'Team',
            'phase': 'Phase',
            
            # Comparison fields
            'others_avg_runs_scored': 'Others Avg Runs',
            'others_avg_balls_faced': 'Others Avg Balls',
            'others_avg_fours': 'Others Avg Fours',
            'others_avg_sixes': 'Others Avg Sixes',
            'others_avg_dismissals': 'Others Avg Dismissals',
            'others_batter_count': 'Others Count'
        }
    
    def parse_response(self, json_response: str) -> Dict[str, Any]:
        """Parse JSON response string."""
        try:
            return json.loads(json_response)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return {}
    
    def extract_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from the response."""
        metadata = {
            'query_type': data.get('query_type', 'Unknown'),
            'total_records': data.get('count', 0),
            'filters_applied': [],
            'metrics_calculated': []
        }
        
        # Extract filter information
        if 'summary' in data:
            summary = data['summary']
            metadata['filters_applied'] = summary.get('filters_applied', [])
            metadata['metrics_calculated'] = summary.get('metrics_calculated', [])
            
            # Extract bowling-specific summary data if present
            if 'bowler_analyzed' in summary:
                metadata['bowler_analyzed'] = summary['bowler_analyzed']
            if 'analysis_focus' in summary:
                metadata['analysis_focus'] = summary['analysis_focus']
            if 'key_metrics' in summary:
                metadata['key_metrics'] = summary['key_metrics']
        
        # Extract tournament/format info if present
        if 'dsl_used' in data and 'filters' in data['dsl_used']:
            filters = data['dsl_used']['filters']
            if 'tournament' in filters:
                metadata['tournament'] = filters['tournament'][0] if filters['tournament'] else None
            if 'format' in filters:
                metadata['format'] = filters['format'][0] if filters['format'] else None
            if 'match_date' in filters:
                metadata['date_range'] = filters['match_date']
            if 'bowler_name' in filters:
                metadata['bowler'] = filters['bowler_name'][0] if filters['bowler_name'] else None
        
        return metadata
    
    def standardize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize field names in a single row."""
        standardized = {}
        for key, value in row.items():
            # Use mapped name if available, otherwise use original
            mapped_key = self.field_mappings.get(key, key)
            # Avoid duplicate columns - if we already have this key, skip
            if mapped_key not in standardized:
                standardized[mapped_key] = value
        return standardized
    
    def convert_to_number(self, value: Any) -> Union[float, int, str]:
        """Convert string numbers to proper numeric types."""
        if value is None:
            return ""
        
        # If already a number, return it
        if isinstance(value, (int, float)):
            return value
        
        # Try to convert string to number
        if isinstance(value, str):
            try:
                # Check if it's an integer
                if '.' not in value:
                    return int(value)
                else:
                    # It's a float
                    float_val = float(value)
                    # Round to 2 decimal places for display
                    return round(float_val, 2)
            except ValueError:
                return value
        
        return value
    
    def format_table(self, rows: List[Dict[str, Any]]) -> str:
        """Format rows as a text table."""
        if not rows:
            return "No data available"
        
        # Standardize all rows
        standardized_rows = [self.standardize_row(row) for row in rows]
        
        # Get all unique columns across all rows
        all_columns = []
        seen_columns = set()
        for row in standardized_rows:
            for col in row.keys():
                if col not in seen_columns:
                    all_columns.append(col)
                    seen_columns.add(col)
        
        # Define column order preference
        column_order = ['Player', 'Team', 'Phase', 'Runs', 'Balls Faced', 
                       'Strike Rate', 'Batting Avg', 'Fours', 'Sixes', 'Dismissals',
                       'Wickets', 'Balls Bowled', 'Runs Conceded', 'Bowling Avg',
                       'Bowling SR', 'Economy']
        
        # Sort columns with preference
        ordered_columns = []
        for col in column_order:
            if col in all_columns:
                ordered_columns.append(col)
        
        # Add remaining columns
        for col in all_columns:
            if col not in ordered_columns:
                ordered_columns.append(col)
        
        # Convert numeric values
        for row in standardized_rows:
            for col in ordered_columns:
                if col in row:
                    row[col] = self.convert_to_number(row[col])
        
        # Calculate column widths
        col_widths = {}
        for col in ordered_columns:
            # Start with header width
            col_widths[col] = len(str(col))
            # Check all row values
            for row in standardized_rows:
                value = str(row.get(col, ""))
                col_widths[col] = max(col_widths[col], len(value))
        
        # Build the table
        lines = []
        
        # Header
        header_parts = []
        for col in ordered_columns:
            header_parts.append(str(col).ljust(col_widths[col]))
        lines.append(" | ".join(header_parts))
        
        # Separator
        separator_parts = []
        for col in ordered_columns:
            separator_parts.append("-" * col_widths[col])
        lines.append("-+-".join(separator_parts))
        
        # Data rows
        for row in standardized_rows:
            row_parts = []
            for col in ordered_columns:
                value = str(row.get(col, ""))
                # Right-align numeric columns
                if col in ['Runs', 'Balls Faced', 'Strike Rate', 'Batting Avg', 
                          'Fours', 'Sixes', 'Dismissals', 'Others Avg Runs', 
                          'Others Avg Balls', 'Others Count', 'Wickets', 
                          'Balls Bowled', 'Runs Conceded', 'Bowling Avg', 
                          'Bowling SR', 'Economy']:
                    row_parts.append(value.rjust(col_widths[col]))
                else:
                    row_parts.append(value.ljust(col_widths[col]))
            lines.append(" | ".join(row_parts))
        
        return "\n".join(lines)
    
    def format_for_llm(self, rows: List[Dict[str, Any]], metadata: Dict[str, Any]) -> str:
        """Format rows and metadata for LLM consumption."""
        output = []
        
        # Add metadata header
        output.append("=== CRICKET STATISTICS ANALYSIS ===\n")
        output.append(f"Query Type: {metadata['query_type']}")
        output.append(f"Total Records: {metadata['total_records']}")
        
        if 'analysis_focus' in metadata:
            output.append(f"Analysis Focus: {metadata['analysis_focus']}")
        if 'bowler_analyzed' in metadata:
            output.append(f"Bowler Analyzed: {metadata['bowler_analyzed']}")
        if 'bowler' in metadata:
            output.append(f"Bowler: {metadata['bowler']}")
        if 'tournament' in metadata:
            output.append(f"Tournament: {metadata['tournament']}")
        if 'format' in metadata:
            output.append(f"Format: {metadata['format']}")
        if 'date_range' in metadata:
            output.append(f"Date Range: {metadata['date_range']}")
        if 'key_metrics' in metadata:
            output.append(f"Key Metrics: {metadata['key_metrics']}")
        
        output.append("\n=== DATA TABLE ===\n")
        
        # Add the table
        table = self.format_table(rows)
        output.append(table)
        
        output.append("\n=== KEY INSIGHTS TO ANALYZE ===")
        
        # Determine if this is bowling or batting analysis
        is_bowling = metadata.get('query_type') == 'bowler_analysis' or metadata.get('analysis_focus') == 'bowler'
        
        if is_bowling:
            output.append("1. Bowling economy and strike rates")
            output.append("2. Wicket-taking ability (bowling average)")
            output.append("3. Control metrics (runs conceded, boundaries given)")
            output.append("4. Performance comparison between bowlers (if multiple)")
            output.append("5. Notable trends or exceptional performances")
        else:
            output.append("1. Performance comparison between players (if multiple)")
            output.append("2. Strike rates and scoring patterns")
            output.append("3. Phase-wise performance (if grouped by phase)")
            output.append("4. Comparison with peer averages (if available)")
            output.append("5. Notable trends or outliers in the data")
        
        return "\n".join(output)
    
    def process_cricket_response(self, json_response: str) -> str:
        """Main method to process cricket JSON response and return formatted output."""
        # Parse JSON
        data = self.parse_response(json_response)
        
        if not data:
            return "Error: Unable to parse JSON response"
        
        # Extract metadata
        metadata = self.extract_metadata(data)
        
        # Get results
        results = data.get('results', [])
        
        # Check for comparative analysis data
        if not results and 'comparative_analysis' in data:
            comp_analysis = data.get('comparative_analysis', {})
            if comp_analysis and 'player_performance' in comp_analysis:
                player_data = comp_analysis.get('player_performance', {})
                if 'data' in player_data:
                    results = player_data['data']
        
        # Format for LLM
        return self.format_for_llm(results, metadata)


# Convenience function
def process_cricket_query(json_response: str) -> str:
    """
    Process a cricket statistics JSON response and return formatted table.
    
    Args:
        json_response: JSON string from cricket statistics API
    
    Returns:
        Formatted string suitable for LLM summarization
    """
    converter = CricketStatsConverter()
    return converter.process_cricket_response(json_response)


# Async function to query the cricket API
async def query_cricket_stats(query: str, timeout: int = 30) -> str:
    """
    Asynchronously query the cricket statistics API and return formatted results.
    
    Args:
        query: Natural language query for cricket statistics
        timeout: Request timeout in seconds (default: 30)
    
    Returns:
        Formatted table string suitable for LLM summarization
    
    Example:
        result = await query_cricket_stats(
            "Analyze Yashasvi Jaiswal's batting by phase in T20 since 2022-01-01"
        )
    """
    url = "http://shrutivishal.synology.me:6996/api/query"
    headers = {"Content-Type": "application/json"}
    payload = {"query": query}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, 
                json=payload, 
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    json_response = await response.text()
                    # Process the response using our converter
                    converter = CricketStatsConverter()
                    return converter.process_cricket_response(json_response)
                else:
                    return f"Error: Server returned status {response.status}\n{await response.text()}"
    
    except asyncio.TimeoutError:
        return f"Error: Request timed out after {timeout} seconds"
    except aiohttp.ClientError as e:
        return f"Error: Network error - {str(e)}"
    except Exception as e:
        return f"Error: Unexpected error - {str(e)}"


# Convenience function for synchronous usage
def query_cricket_stats_sync(query: str, timeout: int = 30) -> str:
    """
    Synchronous wrapper for query_cricket_stats.
    
    Args:
        query: Natural language query for cricket statistics
        timeout: Request timeout in seconds (default: 30)
    
    Returns:
        Formatted table string suitable for LLM summarization
    
    Example:
        result = query_cricket_stats_sync(
            "Compare the performance of Virat Kohli versus Hashim Amla in Test Cricket"
        )
    """
    return asyncio.run(query_cricket_stats(query, timeout))


# Main async function for batch queries
async def batch_query_cricket_stats(queries: List[str]) -> List[str]:
    """
    Process multiple cricket queries concurrently.
    
    Args:
        queries: List of natural language queries
    
    Returns:
        List of formatted table strings
    
    Example:
        queries = [
            "Analyze Virat Kohli in T20 2023-2024",
            "Compare Rohit Sharma and Virat Kohli in 2022 World Cup",
            "Show batting performance of Mumbai Indians in IPL 2024"
        ]
        results = await batch_query_cricket_stats(queries)
    """
    tasks = [query_cricket_stats(query) for query in queries]
    return await asyncio.gather(*tasks)


# Example with one of your responses
if __name__ == "__main__":
    # Example 1: Process a batting JSON response
    batting_json = '''
    {
      "count": 2,
      "query_type": "stats",
      "results": [
        {
          "balls_faced": 222,
          "fours": 25,
          "player_name": "Virat Kohli",
          "runs": 296,
          "sixes": 8,
          "strike_rate": "133.33",
          "team_name": "India"
        },
        {
          "balls_faced": 111,
          "fours": 11,
          "player_name": "Rohit Sharma",
          "runs": 116,
          "sixes": 4,
          "strike_rate": "104.50",
          "team_name": "India"
        }
      ],
      "summary": {
        "aggregate_stats": {"total_runs": 412},
        "context": {"tournament": "ICC Mens T20 World Cup 2022"},
        "filters_applied": ["tournament", "striker_name"],
        "metrics_calculated": ["runs", "balls_faced"],
        "total_records": 2
      },
      "dsl_used": {
        "filters": {
          "tournament": ["ICC Mens T20 World Cup 2022"],
          "striker_name": ["Rohit Sharma", "Virat Kohli"]
        }
      }
    }
    '''
    
    # Example 2: Process a bowling JSON response
    bowling_json = '''
    {
      "count": 1,
      "query_type": "bowler_analysis",
      "results": [
        {
          "balls_bowled": 178,
          "bowling_average": "9.20",
          "bowling_strike_rate": "11.87",
          "economy_rate": "4.65",
          "fours": 10,
          "player_name": "Jasprit Bumrah",
          "runs_conceded": 138,
          "sixes": 2,
          "team_name": "India",
          "wickets_taken": 15
        }
      ],
      "summary": {
        "analysis_focus": "bowler",
        "bowler_analyzed": "Jasprit Bumrah",
        "context": "Tournament: T20 World Cup",
        "filters_applied": ["bowler_name", "tournament"],
        "key_metrics": {
          "bowling_average": "9.20",
          "economy_rate": "4.65",
          "wickets_taken": 15
        },
        "query_type": "bowler_analysis",
        "total_records": 1
      },
      "dsl_used": {
        "filters": {
          "bowler_name": ["Jasprit Bumrah"],
          "tournament": ["ICC Mens T20 World Cup"]
        }
      }
    }
    '''
    
    print("Example 1: Processing Batting Data")
    print("=" * 50)
    result = process_cricket_query(batting_json)
    print(result)
    print("\n" + "=" * 50 + "\n")
    
    print("Example 2: Processing Bowling Data")
    print("=" * 50)
    result = process_cricket_query(bowling_json)
    print(result)
    print("\n" + "=" * 50 + "\n")
    
    # Example 3: Synchronous API query
    print("Example 3: Synchronous API Query")
    print("=" * 50)
    query = "Analyze the performance of Bumrah in World cup T20, including wickets taken"
    # Uncomment to run (requires server to be available):
    # result = query_cricket_stats_sync(query)
    # print(result)
    print(f"Query: {query}")
    print("(Uncomment code to run actual query)")
    print("\n" + "=" * 50 + "\n")
    
    # Example 4: Async API queries
    print("Example 4: Async API Queries")
    print("=" * 50)
    
    async def run_async_examples():
        # Single query for batting
        query1 = "Analyze Yashasvi Jaiswal's batting by phase in T20 since 2022-01-01"
        print(f"Running batting query: {query1}")
        result1 = await query_cricket_stats(query1)
        print(result1[:500] + "..." if len(result1) > 500 else result1)
        
        # Single query for bowling
        query2 = "Show Jadeja bowling performance in T20 World Cup"
        print(f"\nRunning bowling query: {query2}")
        result2 = await query_cricket_stats(query2)
        print(result2[:500] + "..." if len(result2) > 500 else result2)
        
        # Multiple queries in parallel
        queries = [
            "Analyze Virat Kohli in T20 2023-2024",
            "Show bowling performance of Jasprit Bumrah in IPL"
        ]
        print(f"\nRunning {len(queries)} queries in parallel...")
        results = await batch_query_cricket_stats(queries)
        for i, result in enumerate(results):
            print(f"\nQuery {i+1} Result:")
            print(result[:300] + "..." if len(result) > 300 else result)
    
    # Uncomment to run async examples (requires server):
    # asyncio.run(run_async_examples())
    print("(Uncomment asyncio.run() to execute async queries)")
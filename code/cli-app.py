#!/usr/bin/env python3
# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Command-line interface for NLWeb.

This provides a direct CLI for querying the NLWeb vector database and getting
JSON results without the web interface overhead.

Usage:
    python cli-app.py -q "find python tutorials" 
    python cli-app.py -q "machine learning articles" --site example.com
    python cli-app.py -q "recipe for pasta" --num-results 10 --format json
    python cli-app.py -q "climate change research" --sites site1.com,site2.com --output results.json

    python cli-app.py -q  "I am a software developer who wants to contribute to open source projects and stay updated with technology news. I'm looking for interesting GitHub repositories to contribute to, checking NASA's latest space discoveries for inspiration, reading tech news, and finding books about space exploration. First, I search for repositories in my organization to see what projects are available for contribution. Then, I check NASA's Astronomy Picture of the Day to get inspired by space discoveries. Next, I read the latest technology news to stay informed about industry trends. Finally, I search for books about astronomy and space exploration to deepen my knowledge." --num-results 10 --format json --output results.json --quiet
"""

from utils.logging_config_helper import get_configured_logger
from retrieval.retriever import get_vector_db_client, search
from config.config import CONFIG
import asyncio
import argparse
import json
import sys
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


logger = get_configured_logger("cli_app")


class NLWebCLI:
    """Command-line interface for NLWeb queries."""

    def __init__(self, verbose: bool = False):
        """Initialize the CLI with configuration."""
        # Load environment variables
        load_dotenv()

        # Initialize components (similar to app-file.py)
        self._init_components(verbose)

    def _init_components(self, verbose: bool = False):
        """Initialize NLWeb components."""
        try:
            # Set logging to ERROR level to suppress initialization output
            if not verbose:
                self._suppress_logging()

            # Initialize router
            import core.router as router
            router.init()

            # Initialize LLM providers
            import llm.llm as llm
            llm.init()

            # Initialize retrieval clients
            import retrieval.retriever as retriever
            retriever.init()

            if verbose:
                print("+ NLWeb components initialized successfully")
        except Exception as e:
            print(f"- Error initializing NLWeb components: {e}")
            sys.exit(1)

    def _suppress_logging(self):
        """Suppress logging output by setting all loggers to ERROR level."""
        import os

        # Set all logging environment variables to ERROR level
        log_env_vars = [
            "LLM_LOG_LEVEL", "AZURE_OPENAI_LOG_LEVEL", "NLWEB_HANDLER_LOG_LEVEL",
            "RANKING_LOG_LEVEL", "FASTTRACK_LOG_LEVEL", "PROMPT_RUNNER_LOG_LEVEL",
            "PROMPTS_LOG_LEVEL", "DECONTEXTUALIZER_LOG_LEVEL", "MEMORY_LOG_LEVEL",
            "ANALYZE_QUERY_LOG_LEVEL", "REQUIRED_INFO_LOG_LEVEL", "WEBSERVER_LOG_LEVEL"
        ]

        for env_var in log_env_vars:
            os.environ[env_var] = "ERROR"

        # Also set the global logging profile to production (less verbose)
        os.environ["NLWEB_LOGGING_PROFILE"] = "production"

    async def query_database(self, query: str, sites: Optional[List[str]] = None,
                             num_results: int = 10, database: Optional[str] = None,
                             verbose: bool = False) -> List[Dict[str, Any]]:
        """
        Query the vector database directly.

        Args:
            query: Natural language query
            sites: List of sites to search (None for all sites)
            num_results: Maximum number of results to return
            database: Specific database endpoint to use

        Returns:
            List of search results as dictionaries
        """
        try:
            # Determine site parameter
            if sites:
                site_param = sites if len(sites) > 1 else sites[0]
            else:
                # Use configured sites or "all"
                site_param = CONFIG.nlweb.sites if hasattr(
                    CONFIG, 'nlweb') and CONFIG.nlweb.sites else "all"

            if verbose:
                print(f"Searching for: '{query}'")
                if sites:
                    print(f"Sites: {site_param}")
                print(f"Max results: {num_results}")
                if database:
                    print(f"Database: {database}")

            # Create query parameters
            query_params = {}
            if database:
                query_params['db'] = database

            # Perform the search
            raw_results = await search(
                query=query,
                site=site_param,
                num_results=num_results,
                query_params=query_params
            )

            # Convert raw results to structured format
            results = []
            for item in raw_results:
                if len(item) >= 4:
                    url, json_str, name, site = item[0], item[1], item[2], item[3]

                    # Parse JSON data
                    try:
                        schema_data = json.loads(json_str) if isinstance(
                            json_str, str) else json_str
                    except (json.JSONDecodeError, TypeError):
                        schema_data = {"raw_content": str(json_str)}

                    result = {
                        "url": url,
                        "name": name,
                        "site": site,
                        "schema_data": schema_data
                    }
                    results.append(result)

            if verbose:
                print(f"+ Found {len(results)} results")
            return results

        except Exception as e:
            if verbose:
                print(f"- Error during search: {e}")
                logger.exception(f"Search error: {e}")
            return []

    async def get_available_sites(self, database: Optional[str] = None, verbose: bool = False) -> List[str]:
        """Get list of available sites in the database."""
        try:
            query_params = {}
            if database:
                query_params['db'] = database

            client = get_vector_db_client(query_params=query_params)
            sites = await client.get_sites()
            return sites or []
        except Exception as e:
            if verbose:
                print(f"- Error getting sites: {e}")
            return []

    def format_results(self, results: List[Dict[str, Any]], output_format: str = "table") -> str:
        """Format results for display."""
        if not results:
            return "No results found."

        if output_format == "json":
            return json.dumps(results, indent=2, ensure_ascii=False)

        elif output_format == "compact":
            output = []
            for i, result in enumerate(results, 1):
                output.append(f"{i}. {result['name']} ({result['site']})")
                output.append(f"   URL: {result['url']}")
                if result.get('schema_data', {}).get('description'):
                    desc = result['schema_data']['description'][:100]
                    output.append(f"   Description: {desc}...")
                output.append("")
            return "\n".join(output)

        elif output_format == "table":
            # Simple table format using ASCII characters for Windows compatibility
            output = []
            output.append(
                "+-----+------------------------------------------------------------------------------+")
            output.append(
                "| #   | Result                                                                       |")
            output.append(
                "+-----+------------------------------------------------------------------------------+")

            for i, result in enumerate(results, 1):
                name = result['name'][:60] + \
                    "..." if len(result['name']) > 60 else result['name']
                site = result['site'][:15] + \
                    "..." if len(result['site']) > 15 else result['site']
                line = f"| {i:3} | {name:<40} | {site:<15} | {result['url'][:20]:<20} |"
                if len(line) > 82:
                    line = line[:79] + "...|"
                output.append(line)

            output.append(
                "+-----+------------------------------------------------------------------------------+")
            return "\n".join(output)

        else:  # detailed
            output = []
            for i, result in enumerate(results, 1):
                output.append(f"=== Result {i} ===")
                output.append(f"Name: {result['name']}")
                output.append(f"Site: {result['site']}")
                output.append(f"URL:  {result['url']}")

                schema_data = result.get('schema_data', {})
                if schema_data:
                    output.append("Schema Data:")
                    for key, value in schema_data.items():
                        if key in ['description', 'summary', 'text']:
                            # Truncate long text fields
                            if isinstance(value, str) and len(value) > 200:
                                value = value[:200] + "..."
                        output.append(f"  {key}: {value}")
                output.append("")
            return "\n".join(output)


async def main():
    """Main CLI function."""
    # Set console encoding to UTF-8 for Windows compatibility
    import sys
    import os
    if os.name == 'nt':  # Windows
        try:
            # Try to set console to UTF-8
            os.system('chcp 65001 > nul 2>&1')
            # Reconfigure stdout with UTF-8 encoding
            import io
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception:
            # If that fails, we'll handle encoding errors in the output sections
            pass

    parser = argparse.ArgumentParser(
        description="NLWeb Command Line Interface - Query vector databases with natural language",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic query
  python cli-app.py -q "python tutorials"
  
  # Query specific site
  python cli-app.py -q "machine learning" --site example.com
  
  # Query multiple sites with more results
  python cli-app.py -q "recipes" --sites site1.com,site2.com --num-results 20
  
  # Output to JSON file
  python cli-app.py -q "climate research" --format json --output results.json
  
  # List available sites
  python cli-app.py --list-sites
  
  # Use specific database endpoint
  python cli-app.py -q "search term" --database qdrant_local
        """
    )

    # Main arguments
    parser.add_argument('-q', '--query', type=str,
                        help='Natural language query to search for')

    # Site filtering
    parser.add_argument('--site', type=str, help='Single site to search in')
    parser.add_argument('--sites', type=str,
                        help='Comma-separated list of sites to search')

    # Result control
    parser.add_argument('-n', '--num-results', type=int, default=10,
                        help='Maximum number of results to return (default: 10)')

    # Output control
    parser.add_argument('-f', '--format', choices=['table', 'json', 'compact', 'detailed'],
                        default='table', help='Output format (default: table)')
    parser.add_argument('-o', '--output', type=str,
                        help='Output file path (default: stdout)')

    # Database selection
    parser.add_argument('-d', '--database', type=str,
                        help='Specific database endpoint to use')

    # Utility commands
    parser.add_argument('--list-sites', action='store_true',
                        help='List all available sites in the database')
    parser.add_argument('--list-databases', action='store_true',
                        help='List all configured database endpoints')

    # Verbose output
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output and logging')

    # Quiet mode (opposite of verbose)
    parser.add_argument('--quiet', action='store_true',
                        help='Suppress all output except results (overrides --verbose)')

    args = parser.parse_args()

    # Validate arguments
    if not args.query and not args.list_sites and not args.list_databases:
        parser.error(
            "Must provide either --query, --list-sites, or --list-databases")

    if args.site and args.sites:
        parser.error("Cannot specify both --site and --sites")

    # Handle quiet mode
    if args.quiet:
        args.verbose = False

    try:
        # Initialize CLI
        cli = NLWebCLI(verbose=args.verbose)

        # Handle utility commands
        if args.list_databases:
            if not args.quiet:
                print("Available database endpoints:")
            for name, config in CONFIG.retrieval_endpoints.items():
                status = "+ enabled" if config.enabled else "- disabled"
                if args.quiet:
                    print(name)
                else:
                    print(f"  {name} ({config.db_type}) - {status}")
            return

        if args.list_sites:
            if not args.quiet:
                print("Fetching available sites...")
            sites = await cli.get_available_sites(args.database, verbose=args.verbose)
            if sites:
                if not args.quiet:
                    print(f"\nFound {len(sites)} sites:")
                for site in sorted(sites):
                    if args.quiet:
                        print(site)
                    else:
                        print(f"  * {site}")
            else:
                if not args.quiet:
                    print("No sites found or sites query not supported by backend.")
            return

        # Process site arguments
        sites = None
        if args.sites:
            sites = [s.strip() for s in args.sites.split(',')]
        elif args.site:
            sites = [args.site]

        # Execute query
        results = await cli.query_database(
            query=args.query,
            sites=sites,
            num_results=args.num_results,
            database=args.database,
            verbose=args.verbose
        )

        # Format output
        formatted_output = cli.format_results(results, args.format)

        # Write output
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(formatted_output)
            if not args.quiet:
                try:
                    print(f"+ Results written to {args.output}")
                except UnicodeEncodeError:
                    print(f"Results written to {args.output}")
        else:
            try:
                print(formatted_output)
            except UnicodeEncodeError:
                # Fallback: write with errors='replace' to handle encoding issues
                import sys
                sys.stdout.buffer.write(
                    formatted_output.encode('utf-8', errors='replace'))
                sys.stdout.buffer.write(b'\n')

    except KeyboardInterrupt:
        try:
            print("\n- Operation cancelled by user")
        except UnicodeEncodeError:
            print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        try:
            print(f"- Error: {e}")
        except UnicodeEncodeError:
            print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

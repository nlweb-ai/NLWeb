#!/usr/bin/env python3
"""
Enterprise Semantic Layer POC - Demo CLI

Architecture: Template-Based Semantic Query
  NL → Template Match → Value Map → Execute Plan → Assembly → Results

Usage: python demo.py "which deals are at risk based on support tickets?"
"""

import sys
import json
from translator.templates import TEMPLATES, match_template, get_template
from translator.value_mapper import map_values
from translator.plan_executor import PlanExecutor

MAPPINGS_DIR = "mappings"
DATABASES_DIR = "databases"


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else input("Ask a question: ")

    # Phase 1a: Template Matching (LLM)
    print("\n--- Phase 1a: Template Matching ---")
    match = match_template(question)
    print(f"Matched: {match['template_id']} (score: {match['score']})")
    print(f"Extracted slots: {json.dumps(match.get('slots', {}), indent=2)}")

    if match["template_id"] == "none" or match["score"] < 50:
        print("\nNo template matched. Falling back to direct LLM query planning.")
        _fallback(question)
        return

    template = get_template(match["template_id"])
    if not template:
        print(f"\nTemplate '{match['template_id']}' not found. Falling back.")
        _fallback(question)
        return

    # Phase 1b: Value Mapping (lookup + LLM fallback)
    print("\n--- Phase 1b: Value Mapping ---")
    mapped_values = map_values(match.get("slots", {}), template)
    print(f"Mapped filters: {json.dumps(mapped_values, indent=2, default=str)}")

    # Phase 2: Execute Plan (retrieval + assembly)
    print("\n--- Phase 2: Executing Plan ---")
    executor = PlanExecutor(MAPPINGS_DIR, DATABASES_DIR)
    output = executor.execute(question, template, mapped_values)

    # Show SQL for transparency
    for step_id, sql in output.get("sql_queries", []):
        print(f"\n  [{step_id}] SQL:")
        for line in sql.split("\n"):
            print(f"    {line}")

    # Display results
    results = output["results"]
    print(f"\nFound {len(results)} results")
    for r in results[:10]:
        print(f"  {dict(r)}")
    if len(results) > 10:
        print(f"  ... and {len(results) - 10} more")

    if output.get("summary"):
        print(f"\n--- Summary ---\n{output['summary']}")


def _fallback(question: str):
    """Fall back to the original LLM-as-query-planner approach."""
    from translator.nl_to_semantic import translate_to_semantic
    from translator.semantic_to_sql import SemanticToSQLCompiler
    from translator.execute import run_query
    from translator.summarize_results import summarize

    semantic_query = translate_to_semantic(question)
    print(json.dumps(semantic_query, indent=2))

    compiler = SemanticToSQLCompiler(MAPPINGS_DIR, DATABASES_DIR)
    sql, db_config = compiler.compile(semantic_query)
    print(sql)

    results = run_query(sql, db_config)
    print(f"Found {len(results)} results")
    for r in results[:5]:
        print(f"  {dict(r)}")

    summary = summarize(question, results)
    print(f"\n{summary}")


if __name__ == "__main__":
    main()

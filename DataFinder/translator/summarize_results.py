"""
Result summarizer: takes query results and produces a natural language summary.
Uses the LLM abstraction layer for multi-provider support.
"""

from typing import List, Dict, Any
from .llm_client import chat


def summarize(question: str, results: List[Dict[str, Any]]) -> str:
    """Summarize query results into natural language."""
    if not results:
        return "No results found for your query."

    # Format results as a readable table
    headers = list(results[0].keys())
    rows = []
    for r in results[:50]:  # Cap at 50 rows for the prompt
        rows.append([str(r.get(h, "")) for h in headers])

    table_lines = [" | ".join(headers)]
    table_lines.append(" | ".join(["---"] * len(headers)))
    for row in rows:
        table_lines.append(" | ".join(row))
    results_table = "\n".join(table_lines)

    system = "You are a business analyst summarizing query results."
    user = f"""The user asked: "{question}"

The query found {len(results)} results:

{results_table}

Provide a concise, actionable summary. Highlight the most important findings.
If there are concerning patterns (e.g., high-value deals with many support issues),
call them out explicitly. Use specific numbers and names from the data.
Keep it to 2-4 paragraphs."""

    return chat(system=system, user=user, temperature=0.3, max_tokens=1000)

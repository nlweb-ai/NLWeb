"""
Value mapping: converts extracted NL slot values to ontology filter expressions.
Uses a lookup table with LLM fallback for fuzzy matching.
"""

import json
from .llm_client import chat

# Lookup table: NL terms → ontology filter specs
VALUE_MAPPINGS = {
    # Deal value filters
    "big deals": [{"property": "ent:estimatedValue", "operator": "gt", "value": 100000}],
    "high value": [{"property": "ent:estimatedValue", "operator": "gt", "value": 100000}],
    "high-value": [{"property": "ent:estimatedValue", "operator": "gt", "value": 100000}],
    "enterprise deals": [{"property": "ent:estimatedValue", "operator": "gt", "value": 200000}],
    "small deals": [{"property": "ent:estimatedValue", "operator": "lt", "value": 50000}],
    # Deal timing filters
    "closing soon": [{"property": "ent:estimatedCloseDate", "operator": "lte", "value": "2026-03-31"}],
    "closing this quarter": [
        {"property": "ent:estimatedCloseDate", "operator": "gte", "value": "2026-01-01"},
        {"property": "ent:estimatedCloseDate", "operator": "lte", "value": "2026-03-31"},
    ],
    # Ticket status filters
    "open tickets": [{"property": "ent:ticketStatus", "operator": "in", "value": ["Open", "InProgress"]}],
    "escalated tickets": [{"property": "ent:ticketStatus", "operator": "eq", "value": "Escalated"}],
    "escalations": [{"property": "ent:ticketStatus", "operator": "eq", "value": "Escalated"}],
    "unresolved": [{"property": "ent:ticketStatus", "operator": "in",
                    "value": ["Open", "InProgress", "Escalated"]}],
    "unresolved tickets": [{"property": "ent:ticketStatus", "operator": "in",
                            "value": ["Open", "InProgress", "Escalated"]}],
    # Ticket priority filters
    "high priority": [{"property": "ent:ticketPriority", "operator": "in", "value": ["Highest", "High"]}],
    "critical tickets": [{"property": "ent:ticketPriority", "operator": "eq", "value": "Highest"}],
    "critical": [{"property": "ent:ticketPriority", "operator": "eq", "value": "Highest"}],
    # Opportunity status
    "open": [{"property": "ent:opportunityStatus", "operator": "eq", "value": "Open"}],
    "won": [{"property": "ent:opportunityStatus", "operator": "eq", "value": "Won"}],
    "lost": [{"property": "ent:opportunityStatus", "operator": "eq", "value": "Lost"}],
}


def map_values(slots: dict, template: dict) -> dict:
    """Map extracted NL slot values to ontology filter specs.

    Returns dict of slot_name → list of filter specs.
    """
    mapped = {}
    unmapped = {}

    for slot_name, nl_value in slots.items():
        if not nl_value or nl_value == "none":
            continue

        nl_lower = nl_value.lower().strip()

        # Direct lookup
        if nl_lower in VALUE_MAPPINGS:
            mapped[slot_name] = VALUE_MAPPINGS[nl_lower]
            continue

        # Partial match
        found = False
        for key, filters in VALUE_MAPPINGS.items():
            if key in nl_lower or nl_lower in key:
                mapped[slot_name] = filters
                found = True
                break

        if not found:
            unmapped[slot_name] = nl_value

    # LLM fallback for unmapped values
    if unmapped:
        mapped.update(_llm_map_values(unmapped))

    return mapped


def _llm_map_values(unmapped: dict) -> dict:
    """Use LLM to map unknown NL values to ontology filter specs."""
    system = (
        "Convert natural language filter descriptions to ontology filter specs.\n\n"
        "Available filter properties:\n"
        "- ent:estimatedValue (number): Deal value in dollars\n"
        "- ent:estimatedCloseDate (date): Expected close date YYYY-MM-DD\n"
        "- ent:opportunityStatus (enum): Open, Won, Lost\n"
        "- ent:pipelineStage (enum): Qualify, Develop, Propose, Close\n"
        "- ent:ticketStatus (enum): Open, InProgress, WaitingOnCustomer, Escalated, Resolved, Closed\n"
        "- ent:ticketPriority (enum): Highest, High, Medium, Low\n"
        "- ent:annualRevenue (number): Customer annual revenue\n"
        "- schema:name (text): Entity name\n\n"
        "Operators: eq, neq, gt, lt, gte, lte, in, like\n\n"
        'Respond with JSON: {"slot_name": [{"property": "...", "operator": "...", "value": ...}]}\n'
        "Return empty list for a slot if it doesn't map to any filter."
    )
    user = f"Map these values to filters:\n{json.dumps(unmapped)}"

    response = chat(system=system, user=user, temperature=0, max_tokens=500)
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}

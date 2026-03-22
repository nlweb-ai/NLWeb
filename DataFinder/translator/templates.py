"""
Template library for the template-based semantic query architecture.

Templates encode domain expertise about meaningful cross-system query patterns.
Each template has: a natural language pattern, slot extraction spec, retrieval
steps (as semantic queries), and assembly stages (join/map/reduce/synthesize).
"""

import json
from .llm_client import chat

TEMPLATES = [
    {
        "id": "deals_at_risk_support",
        "template": "Which deals are at risk because of support issues",
        "description": "Find deals at risk due to customer support problems",
        "extract": {
            "deal_filter": "any specific filter on deals (e.g., 'big deals', 'high value', 'closing soon')",
            "support_signal": "what kind of support issues (e.g., 'open tickets', 'escalations')"
        },
        "steps": [
            {
                "id": "deals",
                "query": {
                    "primary_entity": "ent:SalesOpportunity",
                    "select": [
                        "ent:opportunityName", "ent:estimatedValue",
                        "ent:estimatedCloseDate", "ent:customer.schema:name",
                        "ent:pipelineStage"
                    ],
                    "filters": [
                        {"property": "ent:opportunityStatus", "operator": "eq", "value": "Open"}
                    ],
                    "order_by": [{"property": "ent:estimatedValue", "direction": "desc"}]
                }
            },
            {
                "id": "tickets",
                "query": {
                    "primary_entity": "ent:SupportTicket",
                    "select": [
                        "ent:ticketSummary", "ent:ticketPriority",
                        "ent:ticketStatus", "ent:dateCreated",
                        "ent:affectedCustomer.schema:name"
                    ],
                    "filters": []
                }
            }
        ],
        "slot_to_step": {
            "deal_filter": "deals",
            "support_signal": "tickets"
        },
        "assemble": {
            "join": {
                "left": "deals",
                "right": "tickets",
                "left_key": "ent_customer_schema_name",
                "right_key": "ent_affectedCustomer_schema_name"
            },
            "map": {
                "over": "deals",
                "with": ["tickets"],
                "extract": {
                    "risk_level": {"type": "enum", "values": ["high", "medium", "low"]},
                    "reason": {"type": "string"},
                    "ticket_count": {"type": "integer"}
                },
                "prompt": (
                    "Assess the risk level for this deal based on its associated support tickets.\n"
                    "Consider: number of tickets, their priority/severity, status, and recency.\n\n"
                    "Deal: {deal_info}\n\nSupport Tickets:\n{ticket_info}\n\n"
                    "Respond with JSON only: "
                    '{{\"risk_level\": \"high|medium|low\", \"reason\": \"brief explanation\", \"ticket_count\": N}}'
                )
            },
            "reduce": {
                "sort": "-risk_level_rank,-ent_estimatedValue",
                "limit": 15
            },
            "synthesize": {
                "prompt": "Summarize the risk landscape across these deals. Which are most at risk and why? Are there patterns?"
            }
        }
    },
    {
        "id": "deal_pipeline",
        "template": "Show the sales pipeline or deal overview",
        "description": "Overview of deals in the pipeline",
        "extract": {
            "deal_filter": "any specific filter (e.g., 'high value', 'closing this quarter')"
        },
        "steps": [
            {
                "id": "results",
                "query": {
                    "primary_entity": "ent:SalesOpportunity",
                    "select": [
                        "ent:opportunityName", "ent:estimatedValue",
                        "ent:estimatedCloseDate", "ent:customer.schema:name",
                        "ent:pipelineStage", "ent:opportunityStatus"
                    ],
                    "order_by": [{"property": "ent:estimatedValue", "direction": "desc"}]
                }
            }
        ],
        "slot_to_step": {"deal_filter": "results"},
        "assemble": {"type": "direct"}
    },
    {
        "id": "customer_ticket_ranking",
        "template": "Which customers have the most support tickets",
        "description": "Rank customers by support ticket volume",
        "extract": {
            "ticket_filter": "type of tickets to count (e.g., 'open', 'escalated', 'all')"
        },
        "steps": [
            {
                "id": "results",
                "query": {
                    "primary_entity": "schema:Organization",
                    "select": ["schema:name"],
                    "joins": [
                        {
                            "entity": "ent:SupportTicket",
                            "on": {
                                "left": "schema:Organization.identifier",
                                "right": "ent:SupportTicket.ent:affectedCustomer"
                            },
                            "type": "inner"
                        }
                    ],
                    "aggregations": [
                        {
                            "function": "count",
                            "entity": "ent:SupportTicket",
                            "alias": "ticket_count",
                            "filters": [
                                {"property": "ent:ticketStatus", "operator": "in",
                                 "value": ["Open", "InProgress", "Escalated"]}
                            ]
                        }
                    ],
                    "order_by": [{"property": "ticket_count", "direction": "desc"}],
                    "limit": 20
                }
            }
        ],
        "slot_to_step": {"ticket_filter": "results"},
        "assemble": {"type": "direct"}
    },
    {
        "id": "open_deals",
        "template": "Show open deals or opportunities",
        "description": "List open sales opportunities",
        "extract": {
            "deal_filter": "any specific filter (e.g., 'high value', 'for customer X')"
        },
        "steps": [
            {
                "id": "results",
                "query": {
                    "primary_entity": "ent:SalesOpportunity",
                    "select": [
                        "ent:opportunityName", "ent:estimatedValue",
                        "ent:estimatedCloseDate", "ent:customer.schema:name",
                        "ent:pipelineStage"
                    ],
                    "filters": [
                        {"property": "ent:opportunityStatus", "operator": "eq", "value": "Open"}
                    ],
                    "order_by": [{"property": "ent:estimatedValue", "direction": "desc"}]
                }
            }
        ],
        "slot_to_step": {"deal_filter": "results"},
        "assemble": {"type": "direct"}
    },
    {
        "id": "support_tickets",
        "template": "Show or list support tickets",
        "description": "List support tickets with optional filters",
        "extract": {
            "ticket_filter": "filter on tickets (e.g., 'open', 'high priority', 'escalated')",
            "customer_filter": "specific customer name if mentioned"
        },
        "steps": [
            {
                "id": "results",
                "query": {
                    "primary_entity": "ent:SupportTicket",
                    "select": [
                        "ent:ticketSummary", "ent:ticketPriority",
                        "ent:ticketStatus", "ent:dateCreated",
                        "ent:affectedCustomer.schema:name"
                    ],
                    "order_by": [{"property": "ent:dateCreated", "direction": "desc"}]
                }
            }
        ],
        "slot_to_step": {"ticket_filter": "results", "customer_filter": "results"},
        "assemble": {"type": "direct"}
    },
    {
        "id": "deals_with_tickets",
        "template": "Show top deals by revenue with support tickets",
        "description": "List high-value deals with support tickets (using inner join - only deals WITH tickets)",
        "extract": {},
        "steps": [
            {
                "id": "results",
                "query": {
                    "primary_entity": "ent:SalesOpportunity",
                    "select": [
                        "ent:opportunityName", "ent:estimatedValue",
                        "ent:customer.schema:name", "ent:pipelineStage"
                    ],
                    "filters": [
                        {"property": "ent:opportunityStatus", "operator": "eq", "value": "Open"}
                    ],
                    "joins": [
                        {
                            "entity": "ent:SupportTicket",
                            "on": {
                                "left": "ent:SalesOpportunity.ent:customer",
                                "right": "ent:SupportTicket.ent:affectedCustomer"
                            },
                            "type": "inner"
                        }
                    ],
                    "aggregations": [
                        {
                            "function": "count",
                            "entity": "ent:SupportTicket",
                            "alias": "ticket_count",
                            "filters": []
                        }
                    ],
                    "order_by": [{"property": "ent:estimatedValue", "direction": "desc"}],
                    "limit": 5
                }
            }
        ],
        "slot_to_step": {},
        "assemble": {"type": "direct"}
    },
    {
        "id": "pipeline_by_dimension",
        "template": "What is the pipeline value by <dimension>",
        "description": "Pipeline value grouped by a dimension (stage, customer, industry)",
        "extract": {
            "dimension": "how to group (e.g., 'by stage', 'by customer', 'by industry')"
        },
        "steps": [
            {
                "id": "results",
                "query": {
                    "primary_entity": "ent:SalesOpportunity",
                    "select": ["ent:pipelineStage"],
                    "filters": [
                        {"property": "ent:opportunityStatus", "operator": "eq", "value": "Open"}
                    ],
                    "aggregations": [
                        {
                            "function": "sum",
                            "entity": "ent:SalesOpportunity",
                            "property": "ent:estimatedValue",
                            "alias": "total_pipeline_value"
                        },
                        {
                            "function": "count",
                            "entity": "ent:SalesOpportunity",
                            "alias": "deal_count"
                        }
                    ],
                    "order_by": [{"property": "total_pipeline_value", "direction": "desc"}]
                }
            }
        ],
        "slot_to_step": {},
        "dimension_select_map": {
            "stage": "ent:pipelineStage",
            "customer": "ent:customer.schema:name",
            "industry": "ent:customer.ent:industry"
        },
        "assemble": {"type": "direct"}
    }
]


def get_template(template_id: str) -> dict:
    """Look up a template by ID."""
    for t in TEMPLATES:
        if t["id"] == template_id:
            return t
    return None


def match_template(question: str) -> dict:
    """Match a natural language question to the best template.

    Returns dict with: template_id, score, slots (extracted values).
    """
    template_descs = []
    for i, t in enumerate(TEMPLATES):
        template_descs.append(
            f"{i + 1}. ID: {t['id']}\n"
            f"   Pattern: {t['template']}\n"
            f"   Description: {t['description']}\n"
            f"   Extract: {json.dumps(t['extract'])}"
        )

    system = (
        "You are a template matcher. Given a user's business question, "
        "score it against each template and extract slot values from the best match.\n\n"
        "Respond with JSON only:\n"
        '{"best_match": {"template_id": "...", "score": 0-100, "slots": {"slot_name": "extracted value"}}}\n\n'
        "Score guidelines:\n"
        "- 90-100: Near-exact match to the template pattern\n"
        "- 70-89: Clear match with some variation\n"
        "- 50-69: Partial match, could work\n"
        "- 0-49: Poor match\n\n"
        'If no template scores above 50, set template_id to "none".\n'
        'For slots, extract the value from the question. Use "none" if not mentioned.'
    )
    user = f'User question: "{question}"\n\nAvailable templates:\n' + "\n".join(template_descs)

    response = chat(system=system, user=user, temperature=0, max_tokens=500)

    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)

    result = json.loads(text)
    return result["best_match"]

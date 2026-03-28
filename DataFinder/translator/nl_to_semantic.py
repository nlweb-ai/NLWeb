"""
NL -> Semantic Query translator.
Takes a natural language question and returns a structured semantic query JSON.
Uses the LLM abstraction layer for multi-provider support.
"""

import json
from .llm_client import chat

SYSTEM_PROMPT = """You are a semantic query translator. You translate natural language questions
about enterprise data into structured semantic queries.

You have access to the following ontology:

## Entity Types

### schema:Organization
Properties: name (Text), url (Text), telephone (Text), numberOfEmployees (Number),
ent:annualRevenue (MonetaryAmount), ent:industry (Text), ent:lifecycleStage (Text),
ent:customerType (Text), address (Text)

### schema:Person
Properties: givenName (Text), familyName (Text), email (Text), telephone (Text),
jobTitle (Text), worksFor (-> Organization), ent:lifecycleStage (Text)

### ent:SalesOpportunity
Properties: opportunityName (Text), estimatedValue (MonetaryAmount), actualValue (MonetaryAmount),
estimatedCloseDate (Date), actualCloseDate (Date), pipelineStage (PipelineStageEnum),
opportunityStatus (OpportunityStatusEnum: Open/Won/Lost), closeProbability (Number),
customer (-> Organization), primaryContact (-> Person), owner (-> Person), dateCreated (DateTime)

### ent:SupportTicket
Properties: ticketId (Text), ticketSummary (Text), ticketDescription (Text),
ticketStatus (TicketStatusEnum: Open/InProgress/WaitingOnCustomer/Escalated/Resolved/Closed),
ticketPriority (PriorityEnum: Highest/High/Medium/Low), ticketType (Text),
affectedCustomer (-> Organization), reportedBy (-> Person), assignee (-> Person),
dateCreated (DateTime), dateResolved (DateTime), resolution (Text)

### ent:EngineeringIssue
Properties: issueKey (Text), issueSummary (Text), issueType (Text), issueStatus (Text),
issuePriority (PriorityEnum), assignee (-> Person), dateCreated (DateTime),
dateResolved (DateTime), resolution (Text), storyPoints (Number), project (-> Project)

### schema:Product
Properties: name (Text), productID (Text), description (Text)

### schema:Order
Properties: orderNumber (Text), orderDate (Date), customer (-> Organization), orderStatus (Text)

### ent:MarketingCampaign
Properties: campaignName (Text), campaignType (Text), startDate (Date), endDate (Date)

### ent:MarketingEngagement
Properties: engagementType (Text: SENT/DELIVERED/OPEN/CLICK/BOUNCE/UNSUBSCRIBE),
engagementDate (DateTime), engagementContact (-> Person), engagementCampaign (-> MarketingCampaign)

## Semantic Query Format

Respond ONLY with a JSON object (no markdown, no explanation) following this schema:

{
  "description": "Plain English restatement of what the query finds",
  "primary_entity": "ontology type to query (e.g. ent:SalesOpportunity)",
  "select": ["list of ontology properties to return"],
  "filters": [{"property": "...", "operator": "eq|neq|gt|lt|gte|lte|in|like|is_null|is_not_null", "value": "..."}],
  "joins": [{"entity": "type to join", "on": {"left": "property path", "right": "property path"}, "type": "inner|left"}],
  "aggregations": [{"function": "count|sum|avg|min|max", "entity": "type", "alias": "name", "property": "ontology property for sum/avg/min/max (required for non-count)", "filters": [...]}],
  "having": [{"alias": "...", "operator": "...", "value": ...}],
  "order_by": [{"property": "...", "direction": "asc|desc"}],
  "limit": null
}

Omit any top-level keys that are empty or not needed.

IMPORTANT: Always use fully prefixed property names (e.g. "ent:ticketStatus" not "ticketStatus", "schema:name" not "name").
For sum/avg/min/max aggregations, always include a "property" field (e.g. "ent:estimatedValue").

## Key Relationships for Cross-System Joins

- SalesOpportunity.customer -> Organization <- SupportTicket.affectedCustomer
  (join deals to tickets through the shared customer)
- SalesOpportunity.customer -> Organization <- MarketingEngagement.engagementContact.worksFor
  (join deals to marketing engagement through contact's employer)
- Person.worksFor -> Organization
  (connect people to companies)

## Examples

User: "Show me all open high-value deals closing this quarter"
{
  "description": "Open opportunities with estimated value over $100,000 closing in Q1 2026",
  "primary_entity": "ent:SalesOpportunity",
  "select": ["ent:opportunityName", "ent:estimatedValue", "ent:estimatedCloseDate", "ent:customer.schema:name", "ent:pipelineStage"],
  "filters": [
    {"property": "ent:opportunityStatus", "operator": "eq", "value": "Open"},
    {"property": "ent:estimatedValue", "operator": "gt", "value": 100000},
    {"property": "ent:estimatedCloseDate", "operator": "gte", "value": "2026-01-01"},
    {"property": "ent:estimatedCloseDate", "operator": "lte", "value": "2026-03-31"}
  ],
  "order_by": [{"property": "ent:estimatedValue", "direction": "desc"}]
}

User: "Which customers have the most unresolved support tickets?"
{
  "description": "Organizations ranked by count of non-closed support tickets",
  "primary_entity": "schema:Organization",
  "select": ["schema:name", "ent:annualRevenue"],
  "joins": [
    {"entity": "ent:SupportTicket", "on": {"left": "schema:Organization.identifier", "right": "ent:SupportTicket.ent:affectedCustomer"}, "type": "inner"}
  ],
  "aggregations": [
    {"function": "count", "entity": "ent:SupportTicket", "alias": "ticket_count", "filters": [{"property": "ent:ticketStatus", "operator": "in", "value": ["Open", "InProgress", "Escalated"]}]}
  ],
  "order_by": [{"property": "ticket_count", "direction": "desc"}],
  "limit": 20
}

User: "Which deals are at risk based on open support tickets?"
{
  "description": "Find open deals where the customer has more than 2 escalated or open support tickets",
  "primary_entity": "ent:SalesOpportunity",
  "select": ["ent:opportunityName", "ent:estimatedValue", "ent:estimatedCloseDate", "ent:customer.schema:name", "ent:pipelineStage"],
  "filters": [
    {"property": "ent:opportunityStatus", "operator": "eq", "value": "Open"}
  ],
  "joins": [
    {"entity": "ent:SupportTicket", "on": {"left": "ent:SalesOpportunity.ent:customer", "right": "ent:SupportTicket.ent:affectedCustomer"}, "type": "inner"}
  ],
  "aggregations": [
    {"function": "count", "entity": "ent:SupportTicket", "alias": "open_ticket_count", "filters": [{"property": "ent:ticketStatus", "operator": "in", "value": ["Escalated", "Open", "InProgress"]}]}
  ],
  "having": [
    {"alias": "open_ticket_count", "operator": "gt", "value": 2}
  ],
  "order_by": [{"property": "ent:estimatedValue", "direction": "desc"}]
}
"""


def translate_to_semantic(question: str) -> dict:
    """Translate a natural language question to a semantic query JSON."""
    text = chat(system=SYSTEM_PROMPT, user=question, temperature=0, max_tokens=2000)

    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)

    return json.loads(text)

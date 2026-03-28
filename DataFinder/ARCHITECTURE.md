# Template-Based Semantic Query Architecture

**From Natural Language to Execution Plans over Heterogeneous Enterprise Data**

## 1. The Problem

Enterprise data lives in dozens of systems — CRMs, ticketing platforms, document stores, marketing tools, ERP systems — each with its own schema, query language, and data model. When a business user asks "Which of our big deals are at risk because customers are unhappy with support?", answering that question requires:

* Querying structured data from a sales system (open deals, deal values)
* Querying structured data from a support system (ticket counts, severities, statuses)
* Searching unstructured data (ticket descriptions, customer communications)
* Joining these across systems that share no common keys
* Applying judgment to assess "risk" from the combined signals

Today's approaches fall into two camps. Connector-based systems (MCP, etc.) give AI agents access to each data source but no understanding of what the data means or how it relates across sources. The agent must figure out joins, mappings, and semantics from scratch on every query. Text-to-SQL systems dump schema definitions into an LLM prompt and ask it to generate queries, which fails at scale — real enterprise schemas have hundreds of tables, and the LLM has no way to know which joins are meaningful versus merely possible.

This document describes a third approach: a template-based architecture that decomposes the problem into layers, using LLMs only where they add value and deterministic machinery everywhere else.

## 2. Architecture Overview

The system has two major phases, each with distinct sub-layers:

```
PHASE 1: Natural Language → Query in Vendor-Neutral Ontology

    User's question (natural language)
            │
            ▼
    ┌─────────────────────────┐
    │  Template Matching       │  LLM scores query against template
    │  (LLM, parallel)        │  library, extracts slot values
    └─────────────────────────┘
            │
            ▼
    ┌─────────────────────────┐
    │  Value Mapping           │  Maps extracted NL terms to
    │  (lookup + LLM fallback) │  ontology vocabulary
    └─────────────────────────┘
            │
            ▼
    Query expressed in ontology language + execution plan

PHASE 2: Ontology Query → Execution over Heterogeneous Sources

    Query in ontology + execution plan
            │
            ▼
    ┌─────────────────────────┐
    │  Retrieval Steps         │  SQL, search, API calls —
    │  (parallel, per source)  │  grounded via TMCF/FCT
    └─────────────────────────┘
            │
            ▼
    ┌─────────────────────────┐
    │  Assembly                │  Deterministic joins, then
    │  (join → map → reduce)  │  parallel per-entity LLM calls
    └─────────────────────────┘
            │
            ▼
    Structured results + optional narrative
```

The key property: LLMs are used strategically at specific points — template matching, value mapping, per-entity classification, optional synthesis — never as a general-purpose query planner navigating an entire schema.

## 3. The Core Enterprise Ontology

The system operates over a shared ontology — a vendor-neutral vocabulary for common business concepts. This is not a massive enterprise data model. It is a deliberately small set of types and properties that capture the entities and relationships that appear across enterprise systems.

Example types:

| Ontology Type | Represents | Common Sources |
|---|---|---|
| schema:Organization | Customer/account | D365, Salesforce, HubSpot |
| ent:SalesOpportunity | Deal/opportunity | D365, Salesforce, Pipedrive |
| ent:SupportTicket | Support case | Jira, ServiceNow, Zendesk |
| ent:MarketingCampaign | Campaign/engagement | HubSpot, Marketo |
| ent:Contract | Agreement/subscription | DocuSign, custom systems |
| schema:Person | Contact/user | Any CRM |

The ontology defines properties in vendor-neutral terms:

```
ent:SalesOpportunity
    ent:opportunityName      → string
    ent:estimatedValue       → currency
    ent:estimatedCloseDate   → date
    ent:opportunityStatus    → enum(Open, Won, Lost)
    ent:customer             → schema:Organization

ent:SupportTicket
    ent:ticketSummary        → string
    ent:ticketPriority       → enum(Highest, High, Medium, Low)
    ent:ticketStatus         → enum(Open, In Progress, Resolved, Closed)
    ent:affectedCustomer     → schema:Organization
    ent:createdDate          → date
```

The critical relationship: `SalesOpportunity.customer` and `SupportTicket.affectedCustomer` both point to `schema:Organization`. This shared reference is what makes cross-system queries possible without hardcoded joins.

## 4. Phase 1: Natural Language to Ontology Query

### 4.1 Template Matching

A template is a natural language pattern representing a query shape that people actually ask about. Templates are not SQL. They are not ontology expressions. They are business questions with slots.

```json
[
  {
    "id": "deals_at_risk_support",
    "template": "Which <deals> are at risk because of <support_signal>",
    "extract": {
      "score": "0-100 match confidence",
      "deal_filter": "any specific filter on deals (e.g., 'big deals', 'Q4 deals')",
      "support_signal": "what kind of support issues concern the user"
    },
    "plan": { "..." }
  },
  {
    "id": "metric_by_dimension",
    "template": "What is <metric> by <dimension>",
    "extract": {
      "score": "0-100 match confidence",
      "metric": "what to measure (e.g., 'total pipeline value', 'average deal size')",
      "dimension": "how to group (e.g., 'by industry', 'by region', 'by quarter')"
    },
    "plan": { "..." }
  },
  {
    "id": "account_health",
    "template": "Health check on <accounts>",
    "extract": {
      "score": "0-100 match confidence",
      "account_filter": "which accounts (e.g., 'top 20', 'enterprise tier', 'EMEA')"
    },
    "plan": { "..." }
  },
  {
    "id": "competitive_losses",
    "template": "Which lost deals mentioned <competitor_or_reason>",
    "extract": {
      "score": "0-100 match confidence",
      "competitor_filter": "specific competitor or 'any competitor'",
      "time_range": "time period if specified"
    },
    "plan": { "..." }
  },
  {
    "id": "entity_comparison",
    "template": "Compare <metric> between <entity1> and <entity2>",
    "extract": {
      "score": "0-100 match confidence",
      "metric": "what to compare",
      "entity1": "first entity",
      "entity2": "second entity"
    },
    "plan": { "..." }
  }
]
```

When a user asks a question, the system sends the query to the LLM in parallel against every template. Each call is small and independent:

```
Prompt to LLM (one per template, all in parallel):

    The user asked: "Which of our big deals are at risk because
    customers are unhappy with support?"

    Does this template match?
    Template: "Which <deals> are at risk because of <support_signal>"

    Score 0-100 for match quality. If score > 75, extract:
    - deal_filter: any specific filter on deals
    - support_signal: what kind of support issues
```

The LLM returns:

```json
{
  "score": 92,
  "deal_filter": "big deals / high value",
  "support_signal": "customer unhappiness with support"
}
```

This is what LLMs are reliable at: pattern matching and slot filling against a clear template. The LLM never sees the ontology, never sees table schemas, never reasons about joins. It just matches a business question to a business question pattern and extracts the variable parts.

The system takes the top-scoring template(s) and proceeds with the attached execution plan.

**Why templates and not free-form query planning?** Templates encode domain expertise about which cross-system queries are meaningful. "Deals at risk from support" is a known, valuable query pattern. An unconstrained planner would have to discover this pattern from raw schemas — that it should join opportunities to tickets via customer, that ticket severity and recency matter for risk, that unstructured ticket descriptions carry signal. Templates encode all of this. The template library is the system's knowledge of what questions are worth asking.

An enterprise might have 50–100 templates covering the vast majority of analytical questions. This is manageable because the templates correspond to questions people actually ask, not to the combinatorial space of possible joins.

### 4.2 Value Mapping

The extracted slot values are natural language: "big deals," "customer unhappiness with support." These need to become ontology terms.

This uses a mapping table — a lookup from natural language terms to ontology expressions — with LLM fallback for fuzzy matching:

```json
{
  "value_mappings": {
    "big deals":         "ent:SalesOpportunity WHERE ent:estimatedValue > 100000",
    "enterprise deals":  "ent:SalesOpportunity WHERE ent:dealTier = 'Enterprise'",
    "open opportunities":"ent:SalesOpportunity WHERE ent:opportunityStatus = 'Open'",
    "escalated tickets": "ent:SupportTicket WHERE ent:ticketPriority IN ('Highest','High')",
    "overdue tickets":   "ent:SupportTicket WHERE ent:ticketStatus = 'Open' AND ent:slaBreached = true",
    "Q4 pipeline":       "ent:SalesOpportunity WHERE ent:estimatedCloseDate BETWEEN '2025-10-01' AND '2025-12-31'"
  }
}
```

Direct lookup handles known terms. For novel phrasings ("customers who keep filing complaints"), the LLM maps to the closest ontology expression using the available vocabulary — but this is a small, focused call with just the value mapping table as context, not the entire schema.

After value mapping, the query is fully expressed in ontology language. The natural language has been consumed. Everything downstream is deterministic or structured.

### 4.3 The Field-Code Mapping Table (TMCF/FCT)

The final grounding step maps ontology terms to actual data source schemas. This is a deterministic lookup table — no LLM involved.

The concept originates from Guha's 1999 patent (US 5,943,665A) on enabling queries across databases that share no common schema. The key mechanism is a Field-Code Mapping Table (FCT) that records, for each source field, what ontological concept it represents. Different databases can use different column names, different value encodings, different ID schemes — the FCT captures the semantic equivalence.

In this system, the FCT is expressed as TMCF mappings (Template MCF, from the Data Commons tradition):

```
# Dynamics 365 Sales
Node: D365_Opportunity
  typeOf: ent:SalesOpportunity
  ent:opportunityName:   C:d365_opps.name
  ent:estimatedValue:    C:d365_opps.estimatedvalue
  ent:customer:          E:d365_opps.customerid -> schema:Organization
  ent:opportunityStatus: C:d365_opps.statuscode
  ent:estimatedCloseDate: C:d365_opps.estimatedclosedate

# Jira Service Management
Node: Jira_Ticket
  typeOf: ent:SupportTicket
  ent:ticketSummary:      C:jira_issues.summary
  ent:affectedCustomer:   E:jira_issues.org_id -> schema:Organization
  ent:ticketPriority:     C:jira_issues.priority
  ent:ticketStatus:       C:jira_issues.status
  ent:createdDate:        C:jira_issues.created

# Entity resolution for Organization
Node: D365_Account
  typeOf: schema:Organization
  schema:name:       C:d365_accounts.name
  schema:identifier: C:d365_accounts.accountid

Node: Jira_Org
  typeOf: schema:Organization
  schema:name:       C:jira_orgs.name
  schema:identifier: C:jira_orgs.org_id
```

The TMCF also includes enum mappings — translating vendor-specific status codes to ontology values:

```json
{
  "d365_opps.statuscode": {
    "1": "Open", "2": "Won", "3": "Lost"
  },
  "jira_issues.priority": {
    "1": "Highest", "2": "High", "3": "Medium", "4": "Low"
  }
}
```

When the system needs to query `ent:SalesOpportunity WHERE ent:estimatedValue > 100000`, the TMCF tells it: go to table `d365_opps`, column `estimatedvalue`, apply the filter. When it needs to join `SalesOpportunity.customer` to `SupportTicket.affectedCustomer`, the TMCF tells it: both map to `schema:Organization`, and the join path is `d365_opps.customerid ↔ d365_accounts.accountid ↔ jira_orgs.org_id ↔ jira_issues.org_id`. This join path is deterministic — it follows the ontology links through the FCT.

## 5. Phase 2: Execution Plans

Each template carries an execution plan — a specification of what data to retrieve and how to assemble it. The plan is the template's theory of what data sources and reasoning steps are needed to answer the query pattern it represents.

### 5.1 Retrieval Steps

A plan specifies retrieval steps, each targeting a different data source. Steps run in parallel.

**SQL steps** query structured/relational data. They are expressed in ontology language and grounded to actual SQL via the TMCF/FCT:

```json
{
  "id": "deals",
  "type": "sql",
  "entity": "ent:SalesOpportunity",
  "filters": {"ent:opportunityStatus": "Open", "ent:estimatedValue": ">100000"},
  "select": ["ent:opportunityName", "ent:estimatedValue",
             "ent:customer", "ent:estimatedCloseDate"]
}
```

The TMCF grounds this to:

```sql
SELECT name, estimatedvalue, customerid, estimatedclosedate
FROM d365_opps
WHERE statuscode = 1 AND estimatedvalue > 100000
```

**Search steps** query unstructured data — document stores, vector databases, full-text indexes:

```json
{
  "id": "ticket_details",
  "type": "search",
  "source": "support_tickets",
  "query": "customer complaints escalation",
  "fields": ["description", "comments", "resolution"]
}
```

**Search-per-entity steps** run a search query for each entity from a prior step, in parallel:

```json
{
  "id": "meeting_notes",
  "type": "search_per_entity",
  "over": "accounts",
  "query": "recent concerns for {name}",
  "source": "meeting_notes",
  "limit": 3
}
```

If there are 20 accounts, this fires 20 parallel searches. Each returns a small, focused result set.

**API steps** call external services:

```json
{
  "id": "usage_metrics",
  "type": "api",
  "service": "telemetry",
  "call": "getUsageTrend",
  "params": {"customer_id": "from:accounts", "period": "90d"}
}
```

### 5.2 Assembly: Join → Map → Reduce → Synthesize

Assembly combines retrieval results into a final answer. It has four composable stages. Each is optional. A given template uses only the stages it needs.

**Stage 1: Join (deterministic)**

The deterministic join uses the TMCF/FCT to connect results from different steps via shared ontology types. No LLM involved.

```json
"join": {
  "left": "deals",
  "right": "tickets",
  "on": "customer",
  "method": "ontology"
}
```

`method: "ontology"` means: both deals and tickets have a property pointing to `schema:Organization`. The TMCF resolves the concrete join path. The output is deals grouped with their associated tickets.

`method: "key"` means a direct key match — when two steps share an explicit identifier.

The join narrows the cross-product. Instead of 50 deals × 300 tickets, you get each deal paired with only its own tickets. This is critical for the next stage.

**Stage 2: Map (parallel per-entity LLM calls)**

This is the key architectural insight: decompose LLM work into independent per-entity calls that run in parallel.

Instead of sending all 50 deals and all 300 tickets into one massive LLM call, each deal gets its own small call with only its own associated data:

```json
"map": {
  "over": "deals",
  "with": ["tickets"],
  "model": "small",
  "extract": {
    "risk_level": {"type": "enum", "values": ["high", "medium", "low"]},
    "reason": {"type": "string", "max_tokens": 100},
    "escalation_needed": {"type": "boolean"}
  },
  "prompt": "Given this deal and its associated support tickets,
    assess the risk level. Consider ticket severity, recency,
    and whether issues suggest systemic problems."
}
```

What this does:

* Deal 1 + its 6 tickets → small LLM call → `{risk: "high", reason: "7 escalated tickets in 30 days, 3 unresolved", escalation_needed: true}`
* Deal 2 + its 3 tickets → small LLM call → `{risk: "low", reason: "minor issues, all resolved", escalation_needed: false}`
* Deal 3 + its 12 tickets → small LLM call → `{risk: "high", reason: "SLA breaches on critical features", escalation_needed: true}`
* ... all 50 in parallel ...

Each call has a few hundred tokens of context. A small, cheap, fast model handles it. No single call approaches context limits. The total wall-clock time is the time for one call, not fifty.

The `extract` specification forces structured output — the LLM must return JSON with those fields. This is what makes the next stage possible.

**Stage 3: Reduce (pure code, no LLM)**

Filter, sort, and limit the mapped results. This is deterministic computation over the structured output from the map stage.

```json
"reduce": {
  "filter": "risk_level == 'high'",
  "sort": "-estimatedValue",
  "limit": 10
}
```

From 50 assessed deals, extract the 10 highest-value high-risk ones. No LLM needed. The structured output from the map stage makes this possible — you cannot sort a narrative, but you can sort a `risk_level` field.

**Stage 4: Synthesize (optional, small context)**

An optional final LLM call that produces narrative from the reduced result set. Because the reduce stage has already narrowed to the most relevant entities, the context is small.

```json
"synthesize": {
  "model": "small",
  "prompt": "Summarize the top risks across these high-value deals.
    What patterns do you see? Are there systemic issues?"
}
```

This call receives 10 deals with pre-extracted risk assessments and reasons — not 50 deals with 300 raw tickets. The context is manageable. The quality is high.

For many queries, this stage is skipped entirely. The user just wants the table of results from the reduce stage.

## 6. Worked Examples

### Example 1: Deals at Risk from Support Issues

User asks: *"Which of our big deals are at risk because customers are unhappy with support?"*

**Phase 1** — Template matching identifies the `deals_at_risk_support` template with high confidence. Extracted values: `deal_filter = "big deals / high value"`, `support_signal = "customer unhappiness with support"`.

Value mapping resolves: "big deals" → `ent:estimatedValue > 100000`, "unhappiness with support" → `ent:ticketPriority IN ('Highest', 'High')`.

**Full execution plan:**

```json
{
  "template": "deals_at_risk_support",
  "steps": [
    {
      "id": "deals",
      "type": "sql",
      "entity": "ent:SalesOpportunity",
      "filters": {"ent:opportunityStatus": "Open", "ent:estimatedValue": ">100000"},
      "select": ["ent:opportunityName", "ent:estimatedValue",
                  "ent:customer", "ent:estimatedCloseDate"]
    },
    {
      "id": "tickets",
      "type": "sql",
      "entity": "ent:SupportTicket",
      "filters": {"ent:ticketPriority": ["Highest", "High"]},
      "select": ["ent:ticketSummary", "ent:affectedCustomer",
                  "ent:ticketStatus", "ent:ticketPriority", "ent:createdDate"]
    }
  ],
  "assemble": {
    "join": {
      "left": "deals", "right": "tickets",
      "on": "customer", "method": "ontology"
    },
    "map": {
      "over": "deals",
      "with": ["tickets"],
      "model": "small",
      "extract": {
        "risk_level": {"type": "enum", "values": ["high", "medium", "low"]},
        "reason": {"type": "string", "max_tokens": 100},
        "ticket_count": {"type": "integer"},
        "most_severe_issue": {"type": "string", "max_tokens": 50}
      },
      "prompt": "Assess risk to this deal based on the associated support tickets. Consider ticket count, severity, recency, and whether issues suggest systemic problems."
    },
    "reduce": {
      "filter": "risk_level IN ('high', 'medium')",
      "sort": "-estimatedValue",
      "limit": 15
    },
    "synthesize": {
      "model": "small",
      "prompt": "Summarize the risk landscape. What patterns emerge? Are multiple high-value deals affected by the same underlying issues?"
    }
  }
}
```

**Execution trace:**

1. Two SQL steps run in parallel. TMCF grounds them to actual tables.
   * `deals` returns 47 open opportunities over $100K.
   * `tickets` returns 183 high/highest priority tickets.
2. Deterministic join groups tickets under their deals via `schema:Organization`. Deal #12 (Acme Corp) gets 9 tickets. Deal #31 (Globex) gets 2. Some deals get 0.
3. Map runs 47 parallel LLM calls. Each gets one deal + its tickets (a few hundred tokens). Small model. Sub-second.
4. Reduce filters to high/medium risk, sorts by deal value, takes top 15.
5. Synthesize reads 15 pre-assessed deals and produces a narrative summary.

Total LLM calls: 1 for template matching + 47 for map + 1 for synthesis = 49 calls, all small, 47 of them parallel.

### Example 2: Simple Factual Query

User asks: *"What's our total pipeline value by industry?"*

Template matching selects `metric_by_dimension`. Extracted: `metric = "total pipeline value"`, `dimension = "industry"`.

**Execution plan:**

```json
{
  "template": "metric_by_dimension",
  "steps": [
    {
      "id": "pipeline",
      "type": "sql",
      "entity": "ent:SalesOpportunity",
      "filters": {"ent:opportunityStatus": "Open"},
      "select": ["ent:estimatedValue", "ent:customer.ent:industry"],
      "aggregate": {
        "group_by": ["ent:customer.ent:industry"],
        "measures": [{"function": "SUM", "field": "ent:estimatedValue", "alias": "total_value"}]
      }
    }
  ],
  "assemble": {
    "type": "direct",
    "format": "table"
  }
}
```

Execution: One SQL step. TMCF grounds it. Result set passes directly to the user as a table. No LLM in assembly at all.

| Industry | Total Pipeline Value |
|---|---|
| Technology | $12.4M |
| Healthcare | $8.7M |
| Financial Services | $6.2M |
| Manufacturing | $4.1M |

Total LLM calls: 1 (template matching only).

This example matters because it shows the system doesn't over-engineer simple queries. When the answer is a GROUP BY + SUM, the template knows that and specifies `"type": "direct"` assembly.

### Example 3: Account Health Check (Multi-Source)

User asks: *"Give me a health check on our top 20 accounts"*

This is the most complex query pattern — it pulls from every system and requires per-account assessment.

**Execution plan:**

```json
{
  "template": "account_health",
  "steps": [
    {
      "id": "accounts",
      "type": "sql",
      "entity": "schema:Organization",
      "filters": {"ent:accountTier": "Enterprise"},
      "select": ["schema:name", "ent:annualRevenue", "ent:renewalDate"],
      "sort": "-ent:annualRevenue",
      "limit": 20
    },
    {
      "id": "deals",
      "type": "sql",
      "entity": "ent:SalesOpportunity",
      "select": ["ent:opportunityName", "ent:estimatedValue",
                  "ent:opportunityStatus", "ent:customer"]
    },
    {
      "id": "tickets",
      "type": "sql",
      "entity": "ent:SupportTicket",
      "select": ["ent:ticketSummary", "ent:ticketPriority",
                  "ent:ticketStatus", "ent:affectedCustomer", "ent:createdDate"]
    },
    {
      "id": "engagement",
      "type": "sql",
      "entity": "ent:MarketingEngagement",
      "select": ["ent:engagementType", "ent:engagementDate",
                  "ent:associatedAccount"]
    },
    {
      "id": "notes",
      "type": "search_per_entity",
      "over": "accounts",
      "query": "recent concerns or issues for {schema:name}",
      "source": "meeting_notes",
      "limit": 3
    }
  ],
  "assemble": {
    "join": [
      {"left": "accounts", "right": "deals", "on": "customer", "method": "ontology"},
      {"left": "accounts", "right": "tickets", "on": "customer", "method": "ontology"},
      {"left": "accounts", "right": "engagement", "on": "customer", "method": "ontology"},
      {"left": "accounts", "right": "notes", "on": "entity_id", "method": "key"}
    ],
    "map": {
      "over": "accounts",
      "with": ["deals", "tickets", "engagement", "notes"],
      "model": "small",
      "extract": {
        "pipeline_momentum": {"type": "enum", "values": ["growing", "stable", "declining"]},
        "support_burden": {"type": "enum", "values": ["heavy", "moderate", "light"]},
        "engagement_trend": {"type": "enum", "values": ["increasing", "stable", "cooling"]},
        "overall_health": {"type": "enum", "values": ["healthy", "watch", "at_risk"]},
        "top_concern": {"type": "string", "max_tokens": 80},
        "recommended_action": {"type": "string", "max_tokens": 80}
      },
      "prompt": "Assess this account's health. Consider: pipeline activity (new deals, expansions, stalls), support load (ticket volume, severity, resolution), marketing engagement (event attendance, content interaction), and any signals from meeting notes. What is the single most important thing to know about this account right now?"
    },
    "reduce": {
      "sort": "overall_health == 'at_risk' DESC, -annualRevenue"
    },
    "synthesize": {
      "model": "small",
      "prompt": "Provide an executive summary of account health across the portfolio. Which accounts need immediate attention? Are there systemic patterns?"
    }
  }
}
```

**Execution trace:**

1. Five retrieval steps run in parallel:
   * 4 SQL queries (parallel, sub-second each after TMCF grounding)
   * 20 parallel search queries for meeting notes (one per account)
2. Four deterministic joins group each data source under its account.
3. Map runs 20 parallel calls. Each gets one account + its deals + tickets + engagement + meeting note snippets. Even with four data sources, the per-account context is manageable — maybe 20 deals, 30 tickets, some engagement events, and 3 document snippets. A small model handles this.
4. Reduce sorts at-risk accounts to the top.
5. Synthesize reads 20 pre-classified accounts and finds portfolio-level patterns.

Total LLM calls: 1 (template match) + 20 (map) + 1 (synthesis) = 22 calls, 20 of them parallel.

Without the map-reduce architecture, this query would require stuffing 20 accounts × 4 data sources of raw data into one LLM call. The context would be enormous. Quality would degrade. With the parallel per-entity approach, each call is small and focused.

### Example 4: Competitive Intelligence from Unstructured Data

User asks: *"Which lost deals mentioned competitors, and why did we lose?"*

This example involves entity resolution between structured records and unstructured text — matching deal records to documents that discuss them.

**Execution plan:**

```json
{
  "template": "competitive_losses",
  "steps": [
    {
      "id": "lost_deals",
      "type": "sql",
      "entity": "ent:SalesOpportunity",
      "filters": {"ent:opportunityStatus": "Lost"},
      "select": ["ent:opportunityName", "ent:estimatedValue",
                  "ent:customer", "ent:estimatedCloseDate"]
    },
    {
      "id": "deal_notes",
      "type": "search_per_entity",
      "over": "lost_deals",
      "query": "competitor loss reason {ent:customer.schema:name} {ent:opportunityName}",
      "source": "deal_notes_and_emails",
      "limit": 5
    }
  ],
  "assemble": {
    "join": {
      "left": "lost_deals", "right": "deal_notes",
      "on": "entity_id", "method": "key"
    },
    "map": {
      "over": "lost_deals",
      "with": ["deal_notes"],
      "model": "small",
      "extract": {
        "competitor_mentioned": {"type": "string"},
        "loss_reason": {"type": "string", "max_tokens": 100},
        "was_price": {"type": "boolean"},
        "was_feature_gap": {"type": "boolean"},
        "was_relationship": {"type": "boolean"},
        "win_back_potential": {"type": "enum", "values": ["high", "medium", "low"]}
      },
      "prompt": "Based on this lost deal and associated notes/emails, identify which competitor won, why we lost, and whether there's potential to win the account back. Classify the loss reason."
    },
    "reduce": {
      "filter": "competitor_mentioned != null",
      "sort": "-estimatedValue"
    },
    "synthesize": {
      "model": "small",
      "prompt": "Analyze the competitive landscape. Which competitors are we losing to most? What are the recurring reasons? Where are the win-back opportunities?"
    }
  }
}
```

Here the map step does genuine LLM work — reading unstructured documents and extracting structured competitive intelligence per deal. But because each deal is assessed independently, the calls are parallel, the context is small (one deal + 5 documents), and a small model suffices.

The reduce stage filters out deals where no competitor was identified (the notes may have been about other topics). The synthesize stage finds patterns across the competitive landscape — this is one of the few places where cross-entity reasoning genuinely adds value.

### Example 5: Contract Renewal Risk with Document Analysis

User asks: *"Which contracts are up for renewal in Q1 that have auto-renewal clauses we should review?"*

This combines structured data (contract dates) with document search (clause analysis).

**Execution plan:**

```json
{
  "template": "contract_renewal_review",
  "steps": [
    {
      "id": "renewals",
      "type": "sql",
      "entity": "ent:Contract",
      "filters": {
        "ent:renewalDate": "BETWEEN '2026-01-01' AND '2026-03-31'",
        "ent:contractStatus": "Active"
      },
      "select": ["ent:contractName", "ent:customer", "ent:contractValue",
                  "ent:renewalDate", "ent:contractDocumentRef"]
    },
    {
      "id": "contract_text",
      "type": "search_per_entity",
      "over": "renewals",
      "query": "auto-renewal termination notice period cancellation clause",
      "source": "contract_documents",
      "scope": "{ent:contractDocumentRef}",
      "limit": 5
    },
    {
      "id": "support_history",
      "type": "sql",
      "entity": "ent:SupportTicket",
      "filters": {"ent:createdDate": ">= '2025-07-01'"},
      "select": ["ent:affectedCustomer", "ent:ticketPriority", "ent:ticketStatus"]
    }
  ],
  "assemble": {
    "join": [
      {"left": "renewals", "right": "contract_text", "on": "entity_id", "method": "key"},
      {"left": "renewals", "right": "support_history", "on": "customer", "method": "ontology"}
    ],
    "map": {
      "over": "renewals",
      "with": ["contract_text", "support_history"],
      "model": "small",
      "extract": {
        "has_auto_renewal": {"type": "boolean"},
        "notice_period_days": {"type": "integer"},
        "cancellation_complexity": {"type": "enum", "values": ["simple", "moderate", "complex"]},
        "customer_satisfaction_signal": {"type": "enum", "values": ["positive", "neutral", "negative"]},
        "review_urgency": {"type": "enum", "values": ["urgent", "soon", "routine"]},
        "key_clause_summary": {"type": "string", "max_tokens": 100}
      },
      "prompt": "Review this contract's renewal clauses and the customer's recent support history. Is there an auto-renewal clause? What's the notice period? Given the customer's support experience, how urgently should we review this renewal?"
    },
    "reduce": {
      "filter": "has_auto_renewal == true",
      "sort": "review_urgency == 'urgent' DESC, notice_period_days ASC"
    }
  }
}
```

This example shows the power of combining document search with structured data and per-entity LLM reasoning. Each contract gets its own analysis of clause text + support history, in parallel.

### Example 6: Generic Single-Entity Query

User asks: *"Show me all open support tickets for Acme Corp"*

**Execution plan:**

```json
{
  "template": "entity_list",
  "steps": [
    {
      "id": "results",
      "type": "sql",
      "entity": "ent:SupportTicket",
      "filters": {
        "ent:ticketStatus": ["Open", "In Progress"],
        "ent:affectedCustomer.schema:name": "Acme Corp"
      },
      "select": ["ent:ticketSummary", "ent:ticketPriority",
                  "ent:ticketStatus", "ent:createdDate"]
    }
  ],
  "assemble": {
    "type": "direct",
    "format": "table",
    "sort": "-ent:createdDate"
  }
}
```

Single SQL step, direct passthrough. The system knows not to over-engineer simple lookups.

## 7. Model Routing

Different stages have different model requirements:

| Stage | Model Size | Reasoning |
|---|---|---|
| Template matching | Small–Medium | Pattern matching + slot filling against clear templates |
| Value mapping | Small | Lookup table with LLM fallback for fuzzy matching |
| Map (per-entity) | Small | Focused extraction from small context (one entity + its data) |
| Synthesize | Small–Medium | Pattern recognition over pre-structured data |

The only case that might require a larger model is when a single entity has genuinely complex, lengthy context — say, one account with 50 pages of contract text. Even then, you could do a map within the map — summarize each document independently, then assess the account from summaries.

This architecture means the system's capacity scales horizontally, not vertically. Adding more accounts or more data sources doesn't require bigger models or bigger context windows. It requires more parallel calls to small models. That is a fundamentally different cost and reliability profile.

## 8. Why Templates, Not a Query Planner

A natural objection: why not use an LLM as a general-purpose query planner that can handle any question? Three reasons:

**Combinatorial explosion.** A real enterprise might have 50 entity types with 500 properties across 20 data sources. The number of possible join paths is enormous. Most are meaningless. A query planner would need to evaluate or prune this space on every query. Templates pre-encode the meaningful paths.

**Reliability.** Template matching is a task LLMs are very good at — "does this question match this pattern?" Free-form query planning requires the LLM to reason about schema semantics, join validity, and data source capabilities simultaneously, which is exactly where LLMs make subtle errors.

**Domain expertise.** The templates encode institutional knowledge: "deals at risk from support issues" is a query pattern that a sales operations team has refined over years. The template captures not just what to query but how to assess the results — what constitutes "risk," what signals matter. This expertise is lost if you let an LLM plan from scratch each time.

**Coverage.** An enterprise's analytical questions follow a Zipf distribution. A library of 50–100 templates covers the vast majority of what people actually ask. For the long tail, generic templates ("show me X for Y where Z") provide basic coverage, and new specific templates can be added as patterns emerge.

## 9. Adding a New Data Source

When a new system is connected (say, a marketing automation platform), the work is:

1. **Add TMCF mappings** — map the new system's schema to existing ontology types. If `HubSpot.company_id` refers to the same entities as `D365.accountid`, record that both map to `schema:Organization`.
2. **Add enum mappings** — translate the new system's status codes, priority levels, etc. to ontology values.
3. **Add value mappings** — register natural language terms for the new system's data. "Email open rates" → `ent:MarketingEngagement WHERE ent:engagementType = 'EmailOpen'`.
4. **Optionally add templates** — if the new data source enables new query patterns (e.g., "Which accounts are going dark on marketing engagement?"), add templates. But existing templates that reference `schema:Organization` will automatically pick up the new source's data through the ontology join.

No code changes. No retraining. The ontology serves as the integration contract.

## 10. Summary of Architectural Principles

**Templates over planners.** Encode domain expertise about meaningful query patterns rather than discovering them at runtime.

**Ontology as integration layer.** A small, shared vocabulary that different source schemas map onto. The Field-Code Mapping Table (TMCF/FCT) is the grounding mechanism.

**Heterogeneous retrieval.** SQL, search, and API calls are first-class retrieval types, not everything forced through a relational model. Unstructured data (document search) and structured data (SQL) combine through the ontology.

**LLMs at specific points.** Template matching (pattern recognition), value mapping (fuzzy lookup), per-entity classification (small focused context), optional synthesis (narrative from structured data). Never as a general-purpose schema navigator.

**Parallel per-entity processing (map-reduce over LLM calls).** The map stage decomposes assessment into independent per-entity calls. Each gets small context. Small models suffice. Calls run in parallel. The system scales horizontally.

**Deterministic joins first, LLM reasoning second.** The ontology-grounded join narrows the data before any LLM sees it. Classification adds structure. Synthesis operates over the smallest possible context. Each layer does what it is best at.

**Structured intermediates enable downstream computation.** The map stage produces structured output (enums, booleans, bounded strings), which the reduce stage can filter and sort without an LLM. Narrative synthesis is optional and operates over pre-structured results.

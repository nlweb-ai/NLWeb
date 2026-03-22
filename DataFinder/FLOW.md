# DataFinder: Query Processing Flow

This document traces how DataFinder translates a natural language question into
cross-database SQL results, using the running example:

> **"Which big deals are at risk because of escalated support tickets?"**

The pipeline has four phases: **Template Matching**, **Value Mapping**,
**Semantic-to-SQL Compilation**, and **Plan Execution & Assembly**.

---

## Phase 1: Template Matching

**Code**: `translator/templates.py` &rarr; `match_template()`

The system maintains a library of hand-authored **templates** — each one
encoding a known cross-system query pattern that matters to the business.
A template is not just a string pattern; it is a complete execution plan that
includes what data to retrieve, how to join it, and how to assess the results.

### What a template contains

Taking `deals_at_risk_support` as our example:

| Field | Purpose | Example |
|---|---|---|
| `template` | NL pattern to match against | "Which deals are at risk because of support issues" |
| `extract` | Slot definitions — what to pull from the question | `deal_filter`: "any specific filter on deals", `support_signal`: "what kind of support issues" |
| `steps` | Semantic queries to execute (retrieval plan) | Step "deals": fetch SalesOpportunity; Step "tickets": fetch SupportTicket |
| `slot_to_step` | Which slot's filters apply to which step | `deal_filter` &rarr; "deals", `support_signal` &rarr; "tickets" |
| `assemble` | How to combine and assess the retrieved data | join &rarr; map &rarr; reduce &rarr; synthesize |

### How matching works

`match_template()` sends a single LLM call with:

- **System prompt**: Instructions to score the question against each template (0-100)
  and extract slot values from the best match.
- **User prompt**: The user's question plus a formatted list of all templates
  (ID, pattern, description, and slot definitions).

The LLM returns JSON:
```json
{
  "best_match": {
    "template_id": "deals_at_risk_support",
    "score": 92,
    "slots": {
      "deal_filter": "big deals",
      "support_signal": "escalated support tickets"
    }
  }
}
```

Key points:
- A score below 50 triggers the **fallback path** (direct LLM query planning
  via `nl_to_semantic.py`), bypassing the template system entirely.
- Slot extraction happens in the same LLM call as matching — no separate step.
- The template library currently has 6 templates: `deals_at_risk_support`,
  `deal_pipeline`, `customer_ticket_ranking`, `open_deals`, `support_tickets`,
  and `pipeline_by_dimension`.

### Why templates, not free-form planning?

The template approach constrains the LLM to a **classification** task (which
template?) rather than a **planning** task (what queries to run, how to join
them). This eliminates an entire class of errors around hallucinated join paths,
invented table names, or nonsensical query plans. The domain expertise about
which cross-system patterns are meaningful lives in the template definitions,
not in LLM reasoning.

---

## Phase 2: Value Mapping

**Code**: `translator/value_mapper.py` &rarr; `map_values()`

The slots extracted in Phase 1 contain natural language values like "big deals"
or "escalated support tickets". These need to be converted into concrete
ontology filter specifications that the SQL compiler can consume.

### The lookup table

A dictionary of ~40 entries maps common NL phrases to filter specs:

```
"big deals"    → [{"property": "ent:estimatedValue", "operator": "gt", "value": 100000}]
"escalations"  → [{"property": "ent:ticketStatus",    "operator": "eq", "value": "Escalated"}]
"closing soon" → [{"property": "ent:estimatedCloseDate", "operator": "lte", "value": "2026-03-31"}]
```

### Resolution strategy

For each slot value, `map_values()` tries three approaches in order:

1. **Exact lookup**: Lowercase the NL value and check the dictionary.
2. **Partial match**: Check if any dictionary key is a substring of the value
   (or vice versa). For example, "escalated support tickets" contains
   "escalated", which is not an exact key — but partial matching finds
   "escalations" won't match either. So it checks if any key appears in the
   value or the value appears in any key.
3. **LLM fallback**: For values that neither lookup hits, an LLM call translates
   them. The LLM receives a schema of available filter properties
   (with their types and valid enum values) and returns filter specs as JSON.

### Output for our example

```json
{
  "deal_filter": [
    {"property": "ent:estimatedValue", "operator": "gt", "value": 100000}
  ],
  "support_signal": [
    {"property": "ent:ticketStatus", "operator": "eq", "value": "Escalated"}
  ]
}
```

### Connecting slots to steps

The template's `slot_to_step` map tells the executor where to apply each
slot's filters:
- `deal_filter` &rarr; step "deals" (the SalesOpportunity query)
- `support_signal` &rarr; step "tickets" (the SupportTicket query)

This means the `ent:estimatedValue > 100000` filter will be appended to the
"deals" step's query, and the `ent:ticketStatus = "Escalated"` filter to the
"tickets" step's query. This injection happens in Phase 4 (`_execute_steps`).

---

## Phase 3: Semantic-to-SQL Compilation

**Code**: `translator/semantic_to_sql.py` &rarr; `SemanticToSQLCompiler.compile()`

Each step in the template contains a **semantic query** — a JSON structure
expressed entirely in ontology terms (ontology types, ontology properties,
ontology enum values). The compiler translates this to concrete SQL targeting
the actual database tables.

### The semantic query for the "deals" step

After slot filters are injected, it looks like:
```json
{
  "primary_entity": "ent:SalesOpportunity",
  "select": [
    "ent:opportunityName", "ent:estimatedValue",
    "ent:estimatedCloseDate", "ent:customer.schema:name",
    "ent:pipelineStage"
  ],
  "filters": [
    {"property": "ent:opportunityStatus", "operator": "eq", "value": "Open"},
    {"property": "ent:estimatedValue", "operator": "gt", "value": 100000}
  ],
  "order_by": [{"property": "ent:estimatedValue", "direction": "desc"}]
}
```

### How compilation works

The compiler resolves every ontology reference to a physical database artifact
through the **MappingParser**, which loads the JSON-LD mapping files at startup.

#### Step 3a: Resolve the primary entity

```
ent:SalesOpportunity
  → canonical source: dynamics365.db  (from CANONICAL_SOURCES)
  → table: d365_opportunities
  → alias: d365
```

The `CANONICAL_SOURCES` dictionary in `MappingParser` determines which database
is authoritative for each type when multiple sources exist. For example,
`schema:Organization` exists in both D365 and HubSpot, but D365 is canonical.

#### Step 3b: Resolve SELECT properties

Each selected property is resolved through `resolve_column()`:

| Ontology property | Resolution type | Physical column |
|---|---|---|
| `ent:opportunityName` | direct | `d365.d365_opportunities.name` |
| `ent:estimatedValue` | direct | `d365.d365_opportunities.estimatedvalue` |
| `ent:estimatedCloseDate` | direct | `d365.d365_opportunities.estimatedclosedate` |
| `ent:customer.schema:name` | FK reference | JOIN `d365.d365_accounts` &rarr; `d365.d365_accounts.name` |
| `ent:pipelineStage` | direct | `d365.d365_opportunities.stepname` |

The dotted property `ent:customer.schema:name` triggers a **foreign key
traversal**: the compiler sees that `ent:customer` on `ent:SalesOpportunity`
is defined in the mapping as:

```json
{
  "column": "parentaccountid",
  "references": {
    "table": "d365_accounts",
    "column": "accountid",
    "identifierColumn": "contoso_id"
  }
}
```

This produces a JOIN clause and resolves `schema:name` against the referenced
table (`d365_accounts.name`).

#### Step 3c: Resolve filters with enum translation

The filter `ent:opportunityStatus = "Open"` must be translated to the source
database's native representation. The mapping file declares:

```json
"ent:opportunityStatus": {
  "0": "Open",
  "1": "Won",
  "2": "Lost"
}
```

The compiler's `resolve_enum_value()` does a **reverse lookup**: given ontology
value "Open", it finds source value `"0"`. So the WHERE clause becomes
`statecode = '0'`.

For the "tickets" step, the Jira mapping translates:
- `ent:ticketStatus = "Escalated"` &rarr; `status = 'Escalated'`
  (direct pass-through in this case since Jira uses the same string)

#### Step 3d: Handle source-specific filters

Some ontology types are backed by rows that share a physical table.
`ent:SupportTicket` and `ent:EngineeringIssue` both map to `jira_issues`,
distinguished by a `filter` in the mapping:

```json
"filter": [{
  "column": "project_id",
  "operator": "in_subquery",
  "lookup": {
    "table": "jira_projects",
    "matchColumn": "project_id",
    "where": {"project_key": ["SUP"]}
  }
}]
```

This automatically adds a WHERE clause:
```sql
project_id IN (SELECT project_id FROM jira.jira_projects WHERE project_key IN ('SUP'))
```

This ensures that only support-project issues are returned when querying
`ent:SupportTicket`, while engineering-project issues are returned for
`ent:EngineeringIssue`.

#### Step 3e: Handle cross-database joins (affectedCustomer)

The "tickets" step selects `ent:affectedCustomer.schema:name`. In Jira, the
`affectedCustomer` relationship is not a simple foreign key — it goes through a
**link table**:

```json
"ent:affectedCustomer": {
  "join": {
    "table": "jira_issue_customer_link",
    "on": {"issue_id": "issue_id"},
    "column": "contoso_customer_id"
  }
}
```

The compiler generates:
1. JOIN `jira.jira_issue_customer_link` ON `issue_id`
2. JOIN `d365.d365_accounts` ON `contoso_customer_id = contoso_id`
3. SELECT `d365.d365_accounts.name`

This is a **cross-database join** — the query ATTACHes both `jira.db` and
`dynamics365.db` to a single SQLite connection.

#### Step 3f: Assemble the SQL

The compiler builds ATTACH DATABASE statements, then assembles SELECT / FROM /
JOIN / WHERE / ORDER BY / LIMIT clauses.

**Generated SQL for the "deals" step:**
```sql
ATTACH DATABASE 'databases/dynamics365.db' AS d365;

SELECT
    d365.d365_opportunities.name AS ent_opportunityName,
    d365.d365_opportunities.estimatedvalue AS ent_estimatedValue,
    d365.d365_opportunities.estimatedclosedate AS ent_estimatedCloseDate,
    d365.d365_accounts.name AS ent_customer_schema_name,
    d365.d365_opportunities.stepname AS ent_pipelineStage
FROM d365.d365_opportunities
JOIN d365.d365_accounts
    ON d365.d365_opportunities.parentaccountid = d365.d365_accounts.accountid
WHERE d365.d365_opportunities.statecode = '0'
    AND d365.d365_opportunities.estimatedvalue > 100000
ORDER BY d365.d365_opportunities.estimatedvalue DESC;
```

**Generated SQL for the "tickets" step:**
```sql
ATTACH DATABASE 'databases/jira.db' AS jira;
ATTACH DATABASE 'databases/dynamics365.db' AS d365;

SELECT
    jira.jira_issues.summary AS ent_ticketSummary,
    jira.jira_issues.priority AS ent_ticketPriority,
    jira.jira_issues.status AS ent_ticketStatus,
    jira.jira_issues.created AS ent_dateCreated,
    d365.d365_accounts.name AS ent_affectedCustomer_schema_name
FROM jira.jira_issues
JOIN jira.jira_issue_customer_link
    ON jira.jira_issues.issue_id = jira.jira_issue_customer_link.issue_id
JOIN d365.d365_accounts
    ON jira.jira_issue_customer_link.contoso_customer_id = d365.d365_accounts.contoso_id
WHERE project_id IN (SELECT project_id FROM jira.jira_projects WHERE project_key IN ('SUP'))
    AND jira.jira_issues.status = 'Escalated'
ORDER BY jira.jira_issues.created DESC;
```

### The role of MappingParser

`MappingParser` (in `translator/mapping_parser.py`) loads all `.jsonld` files
from the `mappings/` directory at startup and builds two registries:

- **type_registry**: `{ontology_type: [list of mapping entries]}` — one entry
  per source database that provides this type.
- **property_registry**: `{ontology_property: [(database, table, column), ...]}`
  — quick lookup for where a property lives.

Key methods:
- `get_canonical_mapping(type)` — returns the preferred source for a type
- `resolve_column(type, property, database)` — returns `{type: "direct"|"fk_ref"|"join", ...}`
- `resolve_enum_value(type, property, value, database)` — reverse-maps ontology enum to source value
- `get_filter_sql(filter_spec)` — generates WHERE clause from the mapping's filter definition

---

## Phase 4: Plan Execution & Assembly

**Code**: `translator/plan_executor.py` &rarr; `PlanExecutor.execute()`

This phase orchestrates everything: it runs the compiled SQL queries, then
applies the template's assembly stages to combine and assess the results.

### Step 4a: Execute retrieval steps

`_execute_steps()` iterates over the template's steps, and for each one:

1. Deep-copies the step's semantic query
2. Injects the mapped value filters for any slots targeting this step
   (via `slot_to_step`)
3. Calls `SemanticToSQLCompiler.compile()` to generate SQL
4. Calls `execute.run_query()` to run the SQL against SQLite

`run_query()` opens an in-memory SQLite connection, ATTACHes all needed
database files, and executes the SELECT. Results come back as lists of dicts.

After this step, we have:
- `step_results["deals"]` — list of high-value open deals with customer names
- `step_results["tickets"]` — list of escalated support tickets with customer names

### Step 4b: Assembly — the join/map/reduce/synthesize pipeline

For simple templates (like `deal_pipeline`), assembly is `"type": "direct"` —
the step results are returned as-is. For complex templates like
`deals_at_risk_support`, the assembly pipeline has four stages:

#### Join

`_join()` groups results from two steps by a shared key.

The template specifies:
```json
{
  "left": "deals",
  "right": "tickets",
  "left_key": "ent_customer_schema_name",
  "right_key": "ent_affectedCustomer_schema_name"
}
```

This is a **deterministic, ontology-grounded join** — both sides were
selected with the customer's organization name, and the join matches deals
to tickets for the same customer. No LLM involvement.

Output: a dict keyed by customer name, where each entry has:
```json
{
  "entity": { deal row },
  "associated": [ list of ticket rows for this customer ]
}
```

#### Map (per-entity LLM assessment)

`_map()` is where the LLM does focused analytical work. For each deal, it:

1. Formats the deal's data and its associated tickets into a prompt
2. Sends it to the LLM with a structured output spec:
   ```json
   {
     "risk_level": {"type": "enum", "values": ["high", "medium", "low"]},
     "reason": {"type": "string"},
     "ticket_count": {"type": "integer"}
   }
   ```
3. Parses the LLM's JSON response and merges it into the deal record

These calls run **in parallel** (ThreadPoolExecutor, up to 10 workers). Each
call has a small context (~100-500 tokens of deal + ticket data), making them
fast and focused. The LLM is not planning or deciding what to query — it is
assessing pre-retrieved, pre-joined data against a specific rubric.

Example prompt for one deal:
```
Assess the risk level for this deal based on its associated support tickets.
Consider: number of tickets, their priority/severity, status, and recency.

Deal: ent_opportunityName: Acme Cloud Migration, ent_estimatedValue: 450000, ...

Support Tickets:
  - ent_ticketSummary: Platform outage affecting services, ent_ticketPriority: Highest, ...
  - ent_ticketSummary: Data sync failures, ent_ticketPriority: High, ...

Respond with JSON only: {"risk_level": "high|medium|low", "reason": "brief explanation", "ticket_count": N}
```

Example LLM response:
```json
{"risk_level": "high", "reason": "2 escalated tickets including a platform outage on a $450K deal", "ticket_count": 2}
```

#### Reduce

`_reduce()` is purely deterministic — no LLM. It applies:

1. **Filter** (optional): e.g., only keep `risk_level in ["high", "medium"]`
2. **Sort**: by `risk_level` rank (high=0, medium=1, low=2) descending, then by
   `estimatedValue` descending
3. **Limit**: cap at 15 results

For the `deals_at_risk_support` template, the reduce spec is:
```json
{"sort": "-risk_level_rank,-ent_estimatedValue", "limit": 15}
```

This surfaces the highest-risk, highest-value deals first.

#### Synthesize

`_synthesize()` makes one final LLM call to produce a narrative summary.
It receives the top 15 assessed deals formatted as a markdown table, plus
the prompt:

> "Summarize the risk landscape across these deals. Which are most at risk
> and why? Are there patterns?"

The output is a 2-4 paragraph business analyst narrative with specific deal
names, dollar amounts, and ticket details.

---

## Summary: Where LLMs are used vs. not

| Step | LLM? | Purpose |
|---|---|---|
| Template matching | Yes (1 call) | Classification: which template fits this question |
| Slot extraction | Yes (same call) | Extract NL values from the question |
| Value mapping (lookup) | No | Dictionary lookup of NL &rarr; ontology filters |
| Value mapping (fallback) | Yes (0-1 calls) | Only for NL values not in the dictionary |
| Semantic &rarr; SQL compilation | No | Deterministic traversal of mapping files |
| SQL execution | No | SQLite query |
| Join | No | Deterministic grouping by shared key |
| Map (per-entity assessment) | Yes (N parallel calls) | Focused assessment of pre-retrieved data |
| Reduce (filter/sort/limit) | No | Deterministic post-processing |
| Synthesize | Yes (1 call) | Narrative summary of final results |

The design principle: LLMs handle **classification** (template matching),
**extraction** (slot values), and **assessment** (per-entity risk evaluation).
Everything structural — query compilation, joins, filtering, sorting — is
deterministic code grounded in the ontology and mapping files.

# Enterprise Semantic Layer: Proof of Concept Design Document

## Purpose

This document provides implementation instructions for building a proof-of-concept that demonstrates the core value proposition of an enterprise semantic layer. The POC consists of four parts:

1. **Source databases**: Realistic tables for three enterprise applications (HubSpot CRM, Jira, Dynamics 365 Sales) populated with synthetic data for one fictional company
2. **Ontology**: A Schema.org-based enterprise vocabulary extending Schema.org where needed
3. **TMCF mappings**: Declarative mappings from each application's native schema to the shared ontology
4. **NL-to-semantic translator**: A system that takes English questions and translates them into queries expressed against the common ontology, which then get compiled to SQL against the source tables using the TMCF mappings

The result should be a working demo where a user asks "which deals are at risk based on open support tickets?" and the system joins across HubSpot, Jira, and Dynamics 365 data using the semantic layer — without any hand-coded cross-system glue.

---

## Part 1: Source Application Databases

Use SQLite for all three databases. Each gets its own .db file, simulating three separate applications with no shared schema.

### 1.1 Fictional Company: Contoso Ltd

Use Microsoft's standard fictional company "Contoso" as the demo organization. Contoso Ltd is a mid-size B2B technology company that sells software products and professional services. They have:

- ~50 customer accounts (companies they sell to)
- ~200 contacts (people at those companies)
- ~80 deals/opportunities in various stages
- ~120 products/line items
- ~300 Jira issues across 4 projects
- ~150 support tickets tracked in Jira Service Management

All three systems share the same universe of customers, contacts, and employees — but use different IDs, different column names, and different schema conventions. This is the core challenge the semantic layer solves.

**Shared identity bridge**: To keep the base case simple (per the assumption of common IDs), generate a master entity list first, then distribute entities across the three systems with a shared `contoso_id` that appears in each system (as different column names). In a real deployment, this would be the entity resolution problem; here we assume it's been solved.

### 1.2 HubSpot CRM Database

**File**: `hubspot.db`

HubSpot is the marketing and early-pipeline CRM. It tracks contacts, companies, deals (in early stages), and marketing engagement.

#### Table: hs_companies

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| company_id | INTEGER PRIMARY KEY | HubSpot internal ID | 1001 |
| contoso_id | TEXT | Cross-system identifier | "CUST-0042" |
| name | TEXT | Company name | "Northwind Traders" |
| domain | TEXT | Website domain | "northwindtraders.com" |
| industry | TEXT | Industry classification | "Technology" |
| city | TEXT | City | "Seattle" |
| state | TEXT | State/province | "WA" |
| country | TEXT | Country | "US" |
| num_employees | INTEGER | Employee count | 500 |
| annual_revenue | REAL | Annual revenue (USD) | 5000000.00 |
| lifecycle_stage | TEXT | HubSpot lifecycle stage | "customer" |
| hs_lead_status | TEXT | Lead status | "OPEN" |
| createdate | TEXT | ISO 8601 creation date | "2024-03-15T10:30:00Z" |
| lastmodifieddate | TEXT | Last modified | "2025-11-02T14:20:00Z" |
| hubspot_owner_id | INTEGER | Assigned HubSpot owner | 201 |

Lifecycle stages: "subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity", "customer", "evangelist", "other"

#### Table: hs_contacts

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| contact_id | INTEGER PRIMARY KEY | HubSpot contact ID | 5001 |
| contoso_id | TEXT | Cross-system person ID | "PER-0117" |
| email | TEXT UNIQUE | Email address | "j.smith@northwind.com" |
| firstname | TEXT | First name | "Jordan" |
| lastname | TEXT | Last name | "Smith" |
| phone | TEXT | Phone | "+1-206-555-0142" |
| jobtitle | TEXT | Job title | "VP of Engineering" |
| company_id | INTEGER | FK to hs_companies | 1001 |
| lifecyclestage | TEXT | Lifecycle stage | "customer" |
| hs_lead_status | TEXT | Lead status | "CONNECTED" |
| lastmodifieddate | TEXT | Last modified | "2025-10-15T09:00:00Z" |
| createdate | TEXT | Created | "2024-01-20T08:00:00Z" |

#### Table: hs_deals

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| deal_id | INTEGER PRIMARY KEY | HubSpot deal ID | 8001 |
| contoso_id | TEXT | Cross-system deal ID | "DEAL-0033" |
| dealname | TEXT | Deal name | "Northwind Enterprise License" |
| amount | REAL | Deal value (USD) | 150000.00 |
| dealstage | TEXT | Pipeline stage | "contractsent" |
| pipeline | TEXT | Pipeline name | "default" |
| closedate | TEXT | Expected close date | "2026-03-30" |
| createdate | TEXT | Created | "2025-08-01T10:00:00Z" |
| company_id | INTEGER | FK to hs_companies | 1001 |
| hubspot_owner_id | INTEGER | Deal owner | 201 |
| deal_type | TEXT | New or existing business | "existingbusiness" |
| hs_priority | TEXT | Priority | "high" |

Deal stages: "appointmentscheduled", "qualifiedtobuy", "presentationscheduled", "decisionmakerboughtin", "contractsent", "closedwon", "closedlost"

#### Table: hs_deal_contacts (association table)

| Column | Type |
|--------|------|
| deal_id | INTEGER |
| contact_id | INTEGER |
| role | TEXT |

Roles: "DECISION_MAKER", "CHAMPION", "INFLUENCER", "BLOCKER", "END_USER"

#### Table: hs_owners

| Column | Type | Description |
|--------|------|-------------|
| owner_id | INTEGER PRIMARY KEY | Owner ID |
| email | TEXT | Owner email |
| firstname | TEXT | First name |
| lastname | TEXT | Last name |

Generate 8-12 HubSpot owners (these are Contoso sales/marketing employees).

#### Table: hs_marketing_emails

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| event_id | INTEGER PRIMARY KEY | Event ID | 30001 |
| contact_id | INTEGER | FK to hs_contacts | 5001 |
| email_campaign_id | INTEGER | Campaign ID | 601 |
| event_type | TEXT | Event type | "OPEN" |
| event_timestamp | TEXT | When it happened | "2025-09-15T14:22:00Z" |

Event types: "SENT", "DELIVERED", "OPEN", "CLICK", "BOUNCE", "UNSUBSCRIBE"

#### Table: hs_campaigns

| Column | Type | Description |
|--------|------|-------------|
| campaign_id | INTEGER PRIMARY KEY | Campaign ID |
| name | TEXT | Campaign name |
| type | TEXT | "EMAIL", "SOCIAL", "CONTENT" |
| start_date | TEXT | Start date |
| end_date | TEXT | End date |

Generate 8-10 marketing campaigns.

### 1.3 Jira Database

**File**: `jira.db`

Jira tracks engineering work (bugs, features, tasks) and support tickets (via Jira Service Management). This is where product development and customer support issues live.

#### Table: jira_projects

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| project_id | INTEGER PRIMARY KEY | Project ID | 10001 |
| project_key | TEXT UNIQUE | Short key | "ENG" |
| name | TEXT | Project name | "Engineering" |
| project_type | TEXT | Type | "software" |
| lead_account_id | TEXT | Project lead | "contoso-emp-005" |

Generate 4 projects:
- **ENG** (Engineering): software development issues
- **PLATFORM** (Platform): infrastructure/DevOps
- **SUP** (Support): customer support tickets (Jira Service Management style)
- **DOCS** (Documentation): documentation tasks

#### Table: jira_issues

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| issue_id | INTEGER PRIMARY KEY | Issue ID | 20001 |
| issue_key | TEXT UNIQUE | Display key | "SUP-142" |
| project_id | INTEGER | FK to jira_projects | 10001 |
| summary | TEXT | Issue title | "Login fails for SSO users" |
| description | TEXT | Full description | "When users attempt..." |
| issue_type | TEXT | Type of issue | "Bug" |
| status | TEXT | Current status | "In Progress" |
| priority | TEXT | Priority | "High" |
| assignee_account_id | TEXT | Assigned employee | "contoso-emp-012" |
| reporter_account_id | TEXT | Reporter | "contoso-emp-005" |
| created | TEXT | Created date | "2025-09-20T11:00:00Z" |
| updated | TEXT | Last updated | "2025-11-01T16:30:00Z" |
| resolved | TEXT | Resolution date (nullable) | "2025-10-15T09:00:00Z" |
| resolution | TEXT | Resolution type (nullable) | "Fixed" |
| story_points | INTEGER | Story points (nullable) | 5 |
| sprint_id | INTEGER | FK to jira_sprints (nullable) | 401 |
| labels | TEXT | Comma-separated labels | "customer-reported,regression" |
| components | TEXT | Comma-separated components | "auth,sso" |

Issue types: "Bug", "Story", "Task", "Epic", "Sub-task", "Service Request", "Incident"

Statuses: "To Do", "In Progress", "In Review", "Done", "Closed", "Waiting for Customer", "Escalated"

Priorities: "Highest", "High", "Medium", "Low", "Lowest"

Resolutions: "Fixed", "Won't Fix", "Duplicate", "Cannot Reproduce", "Done", NULL (unresolved)

#### Table: jira_issue_customer_link

This is how Jira connects issues to customers. In Jira Service Management, support tickets are linked to requesting organizations.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| issue_id | INTEGER | FK to jira_issues | 20001 |
| contoso_customer_id | TEXT | Cross-system customer ID | "CUST-0042" |
| customer_name | TEXT | Denormalized name | "Northwind Traders" |
| link_type | TEXT | Relationship type | "REPORTED_BY" |

Link types: "REPORTED_BY", "AFFECTS", "REQUESTED_BY"

This table is critical — it connects Jira support tickets to the same customers tracked in HubSpot and Dynamics 365.

#### Table: jira_users

| Column | Type | Description |
|--------|------|-------------|
| account_id | TEXT PRIMARY KEY | Jira account ID (e.g. "contoso-emp-005") |
| display_name | TEXT | Full name |
| email | TEXT | Email |
| active | INTEGER | 1=active, 0=inactive |

Generate 15-20 Jira users (Contoso employees — engineers, support staff, PMs).

#### Table: jira_sprints

| Column | Type | Description |
|--------|------|-------------|
| sprint_id | INTEGER PRIMARY KEY | Sprint ID |
| name | TEXT | Sprint name |
| state | TEXT | "active", "closed", "future" |
| start_date | TEXT | Start date |
| end_date | TEXT | End date |
| project_id | INTEGER | FK to jira_projects |

Generate 6-8 sprints for ENG and PLATFORM projects.

#### Table: jira_comments

| Column | Type | Description |
|--------|------|-------------|
| comment_id | INTEGER PRIMARY KEY | Comment ID |
| issue_id | INTEGER | FK to jira_issues |
| author_account_id | TEXT | Who wrote it |
| body | TEXT | Comment text |
| created | TEXT | Created timestamp |

Generate 2-4 comments per issue on average.

### 1.4 Dynamics 365 Sales Database

**File**: `dynamics365.db`

Dynamics 365 is the formal sales and order management system. It has the "system of record" for accounts, opportunities, quotes, and orders. It represents the later-stage pipeline and post-sale relationship.

#### Table: d365_accounts

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| accountid | TEXT PRIMARY KEY | D365 GUID | "a1b2c3d4-..." |
| contoso_id | TEXT | Cross-system ID | "CUST-0042" |
| name | TEXT | Account name | "Northwind Traders" |
| accountnumber | TEXT | Account number | "ACC-NWT-001" |
| revenue | REAL | Annual revenue | 5000000.00 |
| numberofemployees | INTEGER | Headcount | 500 |
| industrycode | INTEGER | Industry code | 12 |
| address1_city | TEXT | City | "Seattle" |
| address1_stateorprovince | TEXT | State | "WA" |
| address1_country | TEXT | Country | "US" |
| telephone1 | TEXT | Main phone | "+1-206-555-0100" |
| websiteurl | TEXT | Website | "https://northwindtraders.com" |
| ownerid | TEXT | Account owner GUID | "emp-guid-005" |
| statecode | INTEGER | 0=Active, 1=Inactive | 0 |
| createdon | TEXT | Created | "2023-06-15T10:00:00Z" |
| modifiedon | TEXT | Modified | "2025-10-28T11:30:00Z" |
| customertypecode | INTEGER | 1=Competitor,3=Customer,11=Prospect | 3 |
| accountratingcode | INTEGER | 1=Default,2=High,3=Low | 2 |

Industry codes (subset): 1=Accounting, 4=Agriculture, 7=Consulting, 12=Technology, 15=Financial Services, 18=Healthcare, 21=Manufacturing, 24=Retail, 27=Education

#### Table: d365_contacts

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| contactid | TEXT PRIMARY KEY | D365 GUID | "c5d6e7f8-..." |
| contoso_id | TEXT | Cross-system person ID | "PER-0117" |
| firstname | TEXT | First name | "Jordan" |
| lastname | TEXT | Last name | "Smith" |
| emailaddress1 | TEXT | Primary email | "j.smith@northwind.com" |
| telephone1 | TEXT | Phone | "+1-206-555-0142" |
| jobtitle | TEXT | Job title | "VP of Engineering" |
| parentcustomerid | TEXT | FK to d365_accounts.accountid | "a1b2c3d4-..." |
| ownerid | TEXT | Contact owner | "emp-guid-005" |
| statecode | INTEGER | 0=Active, 1=Inactive | 0 |
| createdon | TEXT | Created | "2024-01-20T08:00:00Z" |

#### Table: d365_opportunities

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| opportunityid | TEXT PRIMARY KEY | D365 GUID | "op-guid-033" |
| contoso_id | TEXT | Cross-system deal ID | "DEAL-0033" |
| name | TEXT | Opportunity name | "Northwind Enterprise License" |
| estimatedvalue | REAL | Estimated revenue | 150000.00 |
| actualvalue | REAL | Actual value (if won) | NULL |
| estimatedclosedate | TEXT | Expected close | "2026-03-30" |
| actualclosedate | TEXT | Actual close (if closed) | NULL |
| stepname | TEXT | Sales stage | "Propose" |
| statecode | INTEGER | 0=Open, 1=Won, 2=Lost | 0 |
| statuscode | INTEGER | Sub-status | 1 |
| parentaccountid | TEXT | FK to d365_accounts | "a1b2c3d4-..." |
| parentcontactid | TEXT | FK to d365_contacts | "c5d6e7f8-..." |
| ownerid | TEXT | Opportunity owner | "emp-guid-005" |
| createdon | TEXT | Created | "2025-08-01T10:00:00Z" |
| modifiedon | TEXT | Modified | "2025-11-01T09:00:00Z" |
| closeprobability | INTEGER | Win probability % | 70 |
| budgetamount | REAL | Customer budget | 200000.00 |
| purchaseprocess | TEXT | "Individual","Committee","Unknown" | "Committee" |
| purchasetimeframe | TEXT | "Immediate","ThisQuarter","ThisYear","Unknown" | "ThisQuarter" |

Step names: "Qualify", "Develop", "Propose", "Close"

#### Table: d365_products

| Column | Type | Description |
|--------|------|-------------|
| productid | TEXT PRIMARY KEY | Product GUID |
| name | TEXT | Product name |
| productnumber | TEXT | SKU |
| description | TEXT | Description |
| price | REAL | List price |
| productstructure | TEXT | "Product" or "ProductFamily" |
| statecode | INTEGER | 0=Active, 1=Retired, 2=Draft |

Generate 10-15 products: software licenses (per-seat, enterprise), professional services (implementation, training, support tiers), add-on modules.

#### Table: d365_opportunityproducts

| Column | Type | Description |
|--------|------|-------------|
| opportunityproductid | TEXT PRIMARY KEY | Line item GUID |
| opportunityid | TEXT | FK to d365_opportunities |
| productid | TEXT | FK to d365_products |
| quantity | REAL | Quantity |
| priceperunit | REAL | Price per unit |
| extendedamount | REAL | quantity * priceperunit |
| description | TEXT | Line item description |

#### Table: d365_orders

| Column | Type | Description |
|--------|------|-------------|
| salesorderid | TEXT PRIMARY KEY | Order GUID |
| name | TEXT | Order name |
| ordernumber | TEXT | Order number |
| totalamount | REAL | Total value |
| customerid | TEXT | FK to d365_accounts |
| opportunityid | TEXT | FK to d365_opportunities (nullable) |
| statecode | INTEGER | 0=Active, 1=Submitted, 2=Canceled, 3=Fulfilled |
| createdon | TEXT | Created |
| submitdate | TEXT | Submitted date |

#### Table: d365_systemusers

| Column | Type | Description |
|--------|------|-------------|
| systemuserid | TEXT PRIMARY KEY | User GUID (e.g. "emp-guid-005") |
| fullname | TEXT | Full name |
| internalemailaddress | TEXT | Email |
| title | TEXT | Job title |
| businessunitid | TEXT | Business unit |
| isdisabled | INTEGER | 0=active, 1=disabled |

Generate 15-20 D365 users (overlapping with Jira users where appropriate — same Contoso employees appear in both systems).

### 1.5 Synthetic Data Generation

Implement as a Python script: `generate_data.py`

#### Entity Master Lists

Generate these first, then distribute across all three systems:

```python
# Master lists — generate once, reference everywhere
CUSTOMERS = [
    {"contoso_id": "CUST-0001", "name": "Northwind Traders", "domain": "northwindtraders.com",
     "industry": "Technology", "city": "Seattle", "state": "WA", "employees": 500, "revenue": 5000000},
    {"contoso_id": "CUST-0002", "name": "Adventure Works", "domain": "adventureworks.com",
     "industry": "Manufacturing", "city": "Portland", "state": "OR", "employees": 1200, "revenue": 15000000},
    # ... ~50 total
]

CONTACTS = [
    {"contoso_id": "PER-0001", "first": "Jordan", "last": "Smith",
     "email": "j.smith@northwindtraders.com", "title": "VP of Engineering", "customer_id": "CUST-0001"},
    # ... ~200 total, 3-6 per customer
]

EMPLOYEES = [
    {"contoso_id": "EMP-0001", "first": "Alex", "last": "Johnson",
     "email": "alex.johnson@contoso.com", "title": "Account Executive", "dept": "Sales"},
    # ... ~20 total, appearing across all three systems
]

DEALS = [
    {"contoso_id": "DEAL-0001", "name": "Northwind Enterprise License",
     "customer_id": "CUST-0001", "amount": 150000, "stage": "Propose", "close_date": "2026-03-30"},
    # ... ~80 total
]
```

#### Cross-System Data Consistency Requirements

These rules ensure the demo tells a coherent story:

1. Every customer in HubSpot also appears in D365 (same contoso_id). Some customers in D365 may NOT be in HubSpot (legacy accounts).
2. Every deal in HubSpot has a corresponding opportunity in D365 (same contoso_id). HubSpot has the marketing-side view; D365 has the formal opportunity record.
3. ~30% of customers should have open support tickets in Jira linked via `jira_issue_customer_link`. This enables the cross-system "deals at risk" query.
4. Some Contoso employees appear in all three systems under different ID schemes:
   - HubSpot: `hubspot_owner_id` (integer)
   - Jira: `account_id` (string like "contoso-emp-005")
   - D365: `systemuserid` (GUID-like string like "emp-guid-005")
   - Create a mapping: EMP-0005 -> hubspot owner 205, jira "contoso-emp-005", d365 "emp-guid-005"
5. Temporal coherence:
   - Deals created 3-12 months ago
   - Support tickets created 1-6 months ago
   - Some support tickets reference deals or products by name in their description
   - Recent activity (comments, status changes) within last 2 months
6. Interesting patterns to embed (these make the demo queries compelling):
   - 3-5 customers with high-value open deals AND multiple escalated support tickets -> "deals at risk"
   - 2-3 customers with recent deal closure AND surge in support tickets -> "onboarding problems"
   - A few customers with declining marketing engagement (no email opens in 3+ months) AND upcoming renewals -> "churn risk"
   - One customer with a closed-lost deal who then filed several support tickets referencing competitor features -> "competitive intelligence"

#### Data Volume Targets

| Entity | Count | Notes |
|--------|-------|-------|
| Customers/Accounts | ~50 | Same entities across all 3 systems |
| Contacts | ~200 | 3-6 per customer |
| Employees | ~20 | Appear across systems with different IDs |
| Deals/Opportunities | ~80 | 60% open, 25% won, 15% lost |
| Products | 10-15 | Software + services |
| Jira issues (engineering) | ~200 | Bugs, stories, tasks |
| Jira issues (support) | ~150 | Service requests, incidents |
| Jira comments | ~800 | 2-4 per issue average |
| Marketing email events | ~2000 | Across 8-10 campaigns |
| D365 orders | ~30 | For won deals |
| D365 opportunity line items | ~150 | 1-3 per opportunity |

Use the `faker` library for realistic names, addresses, phone numbers, and email addresses. Use deterministic seeding (`random.seed(42)`, `Faker.seed_instance(42)`) so the data is reproducible.

---

## Part 2: Enterprise Ontology (Schema.org Extension)

Define the ontology as a set of MCF (Meta Content Framework) files, following Data Commons conventions. The ontology extends Schema.org into enterprise territory.

**File**: `ontology/enterprise_schema.mcf`

### 2.1 Design Principles

1. **Reuse Schema.org types and properties** wherever they exist. `schema:Organization`, `schema:Person`, `schema:Product`, `schema:Order`, `schema:OrderItem` already cover a lot of ground.
2. **Extend with `ent:` namespace** for enterprise-specific types and properties that Schema.org doesn't cover (pipeline stages, support tickets, sprints, etc.).
3. **Keep the core tight.** Define only what's needed to map the three source systems. Don't speculate about types we won't use.
4. **Properties should be precise.** "revenue" must distinguish `annual_revenue` from `deal_value` from `order_total`. Each is a different property.

### 2.2 Schema.org Types We Use Directly

These exist in Schema.org and need no extension:

- **schema:Organization** — customer accounts/companies. Properties: name, url, telephone, address, numberOfEmployees, industry (Note: Schema.org doesn't have industry directly — it has naics code. We'll add `ent:industry` as a Text property.)
- **schema:Person** — contacts at customer organizations AND internal employees. Properties: givenName, familyName, email, telephone, jobTitle, worksFor (-> Organization)
- **schema:Product** — products being sold. Properties: name, productID, description, offers -> schema:Offer with price, priceCurrency
- **schema:Order** — fulfilled sales orders. Properties: orderNumber, orderDate, customer (-> Organization), orderedItem (-> OrderItem), orderStatus
- **schema:OrderItem** — line items on orders. Properties: orderedItem (-> Product), orderQuantity, price

### 2.3 Enterprise Extensions (ent: namespace)

These types don't exist in Schema.org and must be defined:

```mcf
# === Enterprise Extension Schema ===

# --- SalesOpportunity ---
# A potential sale being tracked through a pipeline.
# Schema.org has nothing for sales pipeline management.

Node: ent:SalesOpportunity
typeOf: schema:Class
subClassOf: schema:Intangible
name: "SalesOpportunity"
description: "A potential sale to a customer being tracked through a sales pipeline."

Node: ent:opportunityName
typeOf: schema:Property
name: "opportunityName"
domainIncludes: ent:SalesOpportunity
rangeIncludes: schema:Text

Node: ent:estimatedValue
typeOf: schema:Property
name: "estimatedValue"
description: "The estimated monetary value of this opportunity."
domainIncludes: ent:SalesOpportunity
rangeIncludes: schema:MonetaryAmount

Node: ent:actualValue
typeOf: schema:Property
name: "actualValue"
description: "The actual monetary value when the opportunity closes."
domainIncludes: ent:SalesOpportunity
rangeIncludes: schema:MonetaryAmount

Node: ent:estimatedCloseDate
typeOf: schema:Property
name: "estimatedCloseDate"
domainIncludes: ent:SalesOpportunity
rangeIncludes: schema:Date

Node: ent:actualCloseDate
typeOf: schema:Property
name: "actualCloseDate"
domainIncludes: ent:SalesOpportunity
rangeIncludes: schema:Date

Node: ent:pipelineStage
typeOf: schema:Property
name: "pipelineStage"
description: "Current stage in the sales pipeline."
domainIncludes: ent:SalesOpportunity
rangeIncludes: ent:PipelineStageEnum

Node: ent:opportunityStatus
typeOf: schema:Property
name: "opportunityStatus"
description: "Whether the opportunity is open, won, or lost."
domainIncludes: ent:SalesOpportunity
rangeIncludes: ent:OpportunityStatusEnum

Node: ent:closeProbability
typeOf: schema:Property
name: "closeProbability"
description: "Estimated probability of winning, as a percentage 0-100."
domainIncludes: ent:SalesOpportunity
rangeIncludes: schema:Number

Node: ent:customer
typeOf: schema:Property
name: "customer"
description: "The customer organization for this opportunity."
domainIncludes: ent:SalesOpportunity
rangeIncludes: schema:Organization

Node: ent:primaryContact
typeOf: schema:Property
name: "primaryContact"
domainIncludes: ent:SalesOpportunity
rangeIncludes: schema:Person

Node: ent:owner
typeOf: schema:Property
name: "owner"
description: "The employee who owns/is responsible for this entity."
domainIncludes: ent:SalesOpportunity, ent:SupportTicket
rangeIncludes: schema:Person

# Pipeline Stage Enumeration
Node: ent:PipelineStageEnum
typeOf: schema:Class
subClassOf: schema:Enumeration

Node: ent:PipelineStage_Qualify
typeOf: ent:PipelineStageEnum
name: "Qualify"

Node: ent:PipelineStage_Develop
typeOf: ent:PipelineStageEnum
name: "Develop"

Node: ent:PipelineStage_Propose
typeOf: ent:PipelineStageEnum
name: "Propose"

Node: ent:PipelineStage_Close
typeOf: ent:PipelineStageEnum
name: "Close"

# Opportunity Status Enumeration
Node: ent:OpportunityStatusEnum
typeOf: schema:Class
subClassOf: schema:Enumeration

Node: ent:OpportunityStatus_Open
typeOf: ent:OpportunityStatusEnum
name: "Open"

Node: ent:OpportunityStatus_Won
typeOf: ent:OpportunityStatusEnum
name: "Won"

Node: ent:OpportunityStatus_Lost
typeOf: ent:OpportunityStatusEnum
name: "Lost"


# --- SupportTicket ---
# A customer support issue or service request.
# Schema.org has no support/ticketing concept.

Node: ent:SupportTicket
typeOf: schema:Class
subClassOf: schema:Intangible
name: "SupportTicket"
description: "A customer support issue, incident, or service request."

Node: ent:ticketId
typeOf: schema:Property
name: "ticketId"
domainIncludes: ent:SupportTicket
rangeIncludes: schema:Text

Node: ent:ticketSummary
typeOf: schema:Property
name: "ticketSummary"
domainIncludes: ent:SupportTicket
rangeIncludes: schema:Text

Node: ent:ticketDescription
typeOf: schema:Property
name: "ticketDescription"
domainIncludes: ent:SupportTicket
rangeIncludes: schema:Text

Node: ent:ticketStatus
typeOf: schema:Property
name: "ticketStatus"
domainIncludes: ent:SupportTicket
rangeIncludes: ent:TicketStatusEnum

Node: ent:ticketPriority
typeOf: schema:Property
name: "ticketPriority"
domainIncludes: ent:SupportTicket
rangeIncludes: ent:PriorityEnum

Node: ent:ticketType
typeOf: schema:Property
name: "ticketType"
description: "Whether this is a service request, incident, bug report, etc."
domainIncludes: ent:SupportTicket
rangeIncludes: schema:Text

Node: ent:affectedCustomer
typeOf: schema:Property
name: "affectedCustomer"
description: "The customer organization affected by this ticket."
domainIncludes: ent:SupportTicket
rangeIncludes: schema:Organization

Node: ent:reportedBy
typeOf: schema:Property
name: "reportedBy"
domainIncludes: ent:SupportTicket
rangeIncludes: schema:Person

Node: ent:assignee
typeOf: schema:Property
name: "assignee"
domainIncludes: ent:SupportTicket, ent:EngineeringIssue
rangeIncludes: schema:Person

Node: ent:dateCreated
typeOf: schema:Property
name: "dateCreated"
domainIncludes: ent:SupportTicket, ent:EngineeringIssue, ent:SalesOpportunity
rangeIncludes: schema:DateTime

Node: ent:dateResolved
typeOf: schema:Property
name: "dateResolved"
domainIncludes: ent:SupportTicket, ent:EngineeringIssue
rangeIncludes: schema:DateTime

Node: ent:resolution
typeOf: schema:Property
name: "resolution"
domainIncludes: ent:SupportTicket, ent:EngineeringIssue
rangeIncludes: schema:Text

# Ticket Status Enumeration
Node: ent:TicketStatusEnum
typeOf: schema:Class
subClassOf: schema:Enumeration

Node: ent:TicketStatus_Open
typeOf: ent:TicketStatusEnum
name: "Open"

Node: ent:TicketStatus_InProgress
typeOf: ent:TicketStatusEnum
name: "InProgress"

Node: ent:TicketStatus_WaitingOnCustomer
typeOf: ent:TicketStatusEnum
name: "WaitingOnCustomer"

Node: ent:TicketStatus_Escalated
typeOf: ent:TicketStatusEnum
name: "Escalated"

Node: ent:TicketStatus_Resolved
typeOf: ent:TicketStatusEnum
name: "Resolved"

Node: ent:TicketStatus_Closed
typeOf: ent:TicketStatusEnum
name: "Closed"

# Priority Enumeration (shared across types)
Node: ent:PriorityEnum
typeOf: schema:Class
subClassOf: schema:Enumeration

Node: ent:Priority_Highest
typeOf: ent:PriorityEnum
name: "Highest"

Node: ent:Priority_High
typeOf: ent:PriorityEnum
name: "High"

Node: ent:Priority_Medium
typeOf: ent:PriorityEnum
name: "Medium"

Node: ent:Priority_Low
typeOf: ent:PriorityEnum
name: "Low"


# --- EngineeringIssue ---
# A software development work item (bug, feature, task).

Node: ent:EngineeringIssue
typeOf: schema:Class
subClassOf: schema:Intangible
name: "EngineeringIssue"
description: "A software development work item such as a bug, feature request, or task."

Node: ent:issueKey
typeOf: schema:Property
name: "issueKey"
domainIncludes: ent:EngineeringIssue
rangeIncludes: schema:Text

Node: ent:issueSummary
typeOf: schema:Property
name: "issueSummary"
domainIncludes: ent:EngineeringIssue
rangeIncludes: schema:Text

Node: ent:issueType
typeOf: schema:Property
name: "issueType"
description: "Bug, Story, Task, Epic, etc."
domainIncludes: ent:EngineeringIssue
rangeIncludes: schema:Text

Node: ent:issueStatus
typeOf: schema:Property
name: "issueStatus"
domainIncludes: ent:EngineeringIssue
rangeIncludes: schema:Text

Node: ent:issuePriority
typeOf: schema:Property
name: "issuePriority"
domainIncludes: ent:EngineeringIssue
rangeIncludes: ent:PriorityEnum

Node: ent:storyPoints
typeOf: schema:Property
name: "storyPoints"
domainIncludes: ent:EngineeringIssue
rangeIncludes: schema:Number

Node: ent:project
typeOf: schema:Property
name: "project"
domainIncludes: ent:EngineeringIssue, ent:SupportTicket
rangeIncludes: ent:Project


# --- Project ---

Node: ent:Project
typeOf: schema:Class
subClassOf: schema:Intangible
name: "Project"
description: "A project grouping related work items."

Node: ent:projectKey
typeOf: schema:Property
name: "projectKey"
domainIncludes: ent:Project
rangeIncludes: schema:Text

Node: ent:projectName
typeOf: schema:Property
name: "projectName"
domainIncludes: ent:Project
rangeIncludes: schema:Text


# --- Additional Organization properties ---

Node: ent:annualRevenue
typeOf: schema:Property
name: "annualRevenue"
description: "Annual revenue of the organization."
domainIncludes: schema:Organization
rangeIncludes: schema:MonetaryAmount

Node: ent:industry
typeOf: schema:Property
name: "industry"
description: "Industry classification."
domainIncludes: schema:Organization
rangeIncludes: schema:Text

Node: ent:lifecycleStage
typeOf: schema:Property
name: "lifecycleStage"
description: "CRM lifecycle stage (lead, customer, etc.)."
domainIncludes: schema:Organization, schema:Person
rangeIncludes: schema:Text

Node: ent:customerType
typeOf: schema:Property
name: "customerType"
description: "Classification as prospect, customer, competitor, etc."
domainIncludes: schema:Organization
rangeIncludes: schema:Text


# --- MarketingCampaign ---

Node: ent:MarketingCampaign
typeOf: schema:Class
subClassOf: schema:Intangible
name: "MarketingCampaign"
description: "A marketing campaign targeting contacts."

Node: ent:campaignName
typeOf: schema:Property
name: "campaignName"
domainIncludes: ent:MarketingCampaign
rangeIncludes: schema:Text

Node: ent:campaignType
typeOf: schema:Property
name: "campaignType"
domainIncludes: ent:MarketingCampaign
rangeIncludes: schema:Text

Node: ent:startDate
typeOf: schema:Property
name: "startDate"
domainIncludes: ent:MarketingCampaign
rangeIncludes: schema:Date

Node: ent:endDate
typeOf: schema:Property
name: "endDate"
domainIncludes: ent:MarketingCampaign
rangeIncludes: schema:Date


# --- MarketingEngagement ---

Node: ent:MarketingEngagement
typeOf: schema:Class
subClassOf: schema:Intangible
name: "MarketingEngagement"
description: "A marketing interaction event (email open, click, etc.)."

Node: ent:engagementType
typeOf: schema:Property
name: "engagementType"
description: "Type of engagement: SENT, DELIVERED, OPEN, CLICK, BOUNCE, UNSUBSCRIBE"
domainIncludes: ent:MarketingEngagement
rangeIncludes: schema:Text

Node: ent:engagementDate
typeOf: schema:Property
name: "engagementDate"
domainIncludes: ent:MarketingEngagement
rangeIncludes: schema:DateTime

Node: ent:engagementContact
typeOf: schema:Property
name: "engagementContact"
domainIncludes: ent:MarketingEngagement
rangeIncludes: schema:Person

Node: ent:engagementCampaign
typeOf: schema:Property
name: "engagementCampaign"
domainIncludes: ent:MarketingEngagement
rangeIncludes: ent:MarketingCampaign
```

### 2.4 Enumeration Value Mapping Tables

The ontology must also include mapping rules for enumerated values that differ across systems. Implement these as JSON lookup files:

**File**: `ontology/enum_mappings.json`

```json
{
  "pipeline_stage": {
    "ontology_type": "ent:PipelineStageEnum",
    "mappings": {
      "hubspot": {
        "appointmentscheduled": "Qualify",
        "qualifiedtobuy": "Qualify",
        "presentationscheduled": "Develop",
        "decisionmakerboughtin": "Develop",
        "contractsent": "Propose",
        "closedwon": "Close",
        "closedlost": "Close"
      },
      "dynamics365": {
        "Qualify": "Qualify",
        "Develop": "Develop",
        "Propose": "Propose",
        "Close": "Close"
      }
    }
  },
  "opportunity_status": {
    "ontology_type": "ent:OpportunityStatusEnum",
    "mappings": {
      "hubspot": {
        "closedwon": "Won",
        "closedlost": "Lost",
        "_default": "Open"
      },
      "dynamics365_statecode": {
        "0": "Open",
        "1": "Won",
        "2": "Lost"
      }
    }
  },
  "ticket_status": {
    "ontology_type": "ent:TicketStatusEnum",
    "mappings": {
      "jira": {
        "To Do": "Open",
        "In Progress": "InProgress",
        "In Review": "InProgress",
        "Waiting for Customer": "WaitingOnCustomer",
        "Escalated": "Escalated",
        "Done": "Resolved",
        "Closed": "Closed"
      }
    }
  },
  "priority": {
    "ontology_type": "ent:PriorityEnum",
    "mappings": {
      "jira": {
        "Highest": "Highest",
        "High": "High",
        "Medium": "Medium",
        "Low": "Low",
        "Lowest": "Low"
      },
      "hubspot": {
        "high": "High",
        "medium": "Medium",
        "low": "Low"
      }
    }
  }
}
```

---

## Part 3: TMCF Mappings

Template MCF files declare how each source table maps to the ontology. These follow the Data Commons TMCF format adapted for the enterprise context.

The key syntax:
- `Node: E:<DatasetName>->E<N>` declares an entity
- `typeOf:` declares its ontology type
- `C:<DatasetName>-><ColumnName>` references a column value
- Properties on the left are ontology properties; column references on the right are source columns

### 3.1 HubSpot Mappings

**File**: `mappings/hubspot.tmcf`

```tmcf
# === HubSpot Companies -> schema:Organization ===

Node: E:hs_companies->E1
typeOf: schema:Organization
identifier: C:hs_companies->contoso_id
name: C:hs_companies->name
url: C:hs_companies->domain
ent:industry: C:hs_companies->industry
ent:annualRevenue: C:hs_companies->annual_revenue
schema:numberOfEmployees: C:hs_companies->num_employees
schema:address: C:hs_companies->city
ent:lifecycleStage: C:hs_companies->lifecycle_stage
ent:customerType: C:hs_companies->lifecycle_stage


# === HubSpot Contacts -> schema:Person ===

Node: E:hs_contacts->E1
typeOf: schema:Person
identifier: C:hs_contacts->contoso_id
schema:givenName: C:hs_contacts->firstname
schema:familyName: C:hs_contacts->lastname
schema:email: C:hs_contacts->email
schema:telephone: C:hs_contacts->phone
schema:jobTitle: C:hs_contacts->jobtitle
schema:worksFor: C:hs_contacts->company_id
ent:lifecycleStage: C:hs_contacts->lifecyclestage


# === HubSpot Deals -> ent:SalesOpportunity ===

Node: E:hs_deals->E1
typeOf: ent:SalesOpportunity
identifier: C:hs_deals->contoso_id
ent:opportunityName: C:hs_deals->dealname
ent:estimatedValue: C:hs_deals->amount
ent:pipelineStage: C:hs_deals->dealstage
ent:estimatedCloseDate: C:hs_deals->closedate
ent:customer: C:hs_deals->company_id
ent:dateCreated: C:hs_deals->createdate
ent:owner: C:hs_deals->hubspot_owner_id


# === HubSpot Campaigns -> ent:MarketingCampaign ===

Node: E:hs_campaigns->E1
typeOf: ent:MarketingCampaign
ent:campaignName: C:hs_campaigns->name
ent:campaignType: C:hs_campaigns->type
ent:startDate: C:hs_campaigns->start_date
ent:endDate: C:hs_campaigns->end_date


# === HubSpot Email Events -> ent:MarketingEngagement ===

Node: E:hs_marketing_emails->E1
typeOf: ent:MarketingEngagement
ent:engagementType: C:hs_marketing_emails->event_type
ent:engagementDate: C:hs_marketing_emails->event_timestamp
ent:engagementContact: C:hs_marketing_emails->contact_id
ent:engagementCampaign: C:hs_marketing_emails->email_campaign_id
```

### 3.2 Jira Mappings

**File**: `mappings/jira.tmcf`

```tmcf
# === Jira Projects -> ent:Project ===

Node: E:jira_projects->E1
typeOf: ent:Project
ent:projectKey: C:jira_projects->project_key
ent:projectName: C:jira_projects->name


# === Jira Support Issues -> ent:SupportTicket ===
# Only issues from the SUP project are SupportTickets.
# Filter: project_key = "SUP"

Node: E:jira_issues_support->E1
typeOf: ent:SupportTicket
ent:ticketId: C:jira_issues->issue_key
ent:ticketSummary: C:jira_issues->summary
ent:ticketDescription: C:jira_issues->description
ent:ticketStatus: C:jira_issues->status
ent:ticketPriority: C:jira_issues->priority
ent:ticketType: C:jira_issues->issue_type
ent:assignee: C:jira_issues->assignee_account_id
ent:reportedBy: C:jira_issues->reporter_account_id
ent:dateCreated: C:jira_issues->created
ent:dateResolved: C:jira_issues->resolved
ent:resolution: C:jira_issues->resolution

# Customer linkage comes from join with jira_issue_customer_link
ent:affectedCustomer: C:jira_issue_customer_link->contoso_customer_id


# === Jira Engineering Issues -> ent:EngineeringIssue ===
# Issues from ENG, PLATFORM, DOCS projects.

Node: E:jira_issues_eng->E1
typeOf: ent:EngineeringIssue
ent:issueKey: C:jira_issues->issue_key
ent:issueSummary: C:jira_issues->summary
ent:issueType: C:jira_issues->issue_type
ent:issueStatus: C:jira_issues->status
ent:issuePriority: C:jira_issues->priority
ent:assignee: C:jira_issues->assignee_account_id
ent:dateCreated: C:jira_issues->created
ent:dateResolved: C:jira_issues->resolved
ent:resolution: C:jira_issues->resolution
ent:storyPoints: C:jira_issues->story_points
ent:project: C:jira_issues->project_id
```

### 3.3 Dynamics 365 Mappings

**File**: `mappings/dynamics365.tmcf`

```tmcf
# === D365 Accounts -> schema:Organization ===

Node: E:d365_accounts->E1
typeOf: schema:Organization
identifier: C:d365_accounts->contoso_id
name: C:d365_accounts->name
schema:telephone: C:d365_accounts->telephone1
url: C:d365_accounts->websiteurl
schema:numberOfEmployees: C:d365_accounts->numberofemployees
ent:annualRevenue: C:d365_accounts->revenue
schema:address: C:d365_accounts->address1_city
ent:customerType: C:d365_accounts->customertypecode


# === D365 Contacts -> schema:Person ===

Node: E:d365_contacts->E1
typeOf: schema:Person
identifier: C:d365_contacts->contoso_id
schema:givenName: C:d365_contacts->firstname
schema:familyName: C:d365_contacts->lastname
schema:email: C:d365_contacts->emailaddress1
schema:telephone: C:d365_contacts->telephone1
schema:jobTitle: C:d365_contacts->jobtitle
schema:worksFor: C:d365_contacts->parentcustomerid


# === D365 Opportunities -> ent:SalesOpportunity ===

Node: E:d365_opportunities->E1
typeOf: ent:SalesOpportunity
identifier: C:d365_opportunities->contoso_id
ent:opportunityName: C:d365_opportunities->name
ent:estimatedValue: C:d365_opportunities->estimatedvalue
ent:actualValue: C:d365_opportunities->actualvalue
ent:estimatedCloseDate: C:d365_opportunities->estimatedclosedate
ent:actualCloseDate: C:d365_opportunities->actualclosedate
ent:pipelineStage: C:d365_opportunities->stepname
ent:opportunityStatus: C:d365_opportunities->statecode
ent:closeProbability: C:d365_opportunities->closeprobability
ent:customer: C:d365_opportunities->parentaccountid
ent:primaryContact: C:d365_opportunities->parentcontactid
ent:owner: C:d365_opportunities->ownerid
ent:dateCreated: C:d365_opportunities->createdon


# === D365 Products -> schema:Product ===

Node: E:d365_products->E1
typeOf: schema:Product
schema:productID: C:d365_products->productnumber
schema:name: C:d365_products->name
schema:description: C:d365_products->description


# === D365 Orders -> schema:Order ===

Node: E:d365_orders->E1
typeOf: schema:Order
schema:orderNumber: C:d365_orders->ordernumber
schema:orderDate: C:d365_orders->createdon
schema:customer: C:d365_orders->customerid
schema:orderStatus: C:d365_orders->statecode


# === D365 Opportunity Line Items -> schema:OrderItem ===
# (Used as proposed line items on opportunities, before they become actual order items)

Node: E:d365_opportunityproducts->E1
typeOf: schema:OrderItem
schema:orderedItem: C:d365_opportunityproducts->productid
schema:orderQuantity: C:d365_opportunityproducts->quantity
schema:price: C:d365_opportunityproducts->priceperunit
```

---

## Part 4: NL-to-Semantic Query Translator

This is the component that takes a natural language question and translates it into a structured query against the shared ontology, which then gets compiled to SQL against the source databases using the TMCF mappings.

### 4.1 Architecture

```
User Question (English)
        |
        v
+----------------------+
|  NL -> Semantic Query |  (LLM call)
|  "which deals are    |
|   at risk..."        |
|        |             |
|  SemanticQuery{      |
|    find: SalesOpp    |
|    where: status=Open|
|    join: SupportTkt  |
|    on: customer      |
|    having: count>2   |
|  }                   |
+----------------------+
        |
        v
+----------------------+
|  Semantic -> SQL      |  (deterministic compiler)
|  Uses TMCF mappings  |
|  + enum mappings     |
|        |             |
|  SELECT ... FROM     |
|  d365_opportunities  |
|  JOIN jira_issues... |
+----------------------+
        |
        v
+----------------------+
|  SQL Execution       |
|  Against source DBs  |
|        |             |
|  Results             |
+----------------------+
        |
        v
+----------------------+
|  Result -> English    |  (LLM call)
|  Natural language    |
|  summary of findings |
+----------------------+
```

### 4.2 Semantic Query Language

Define a JSON-based intermediate representation that the LLM outputs. This is the "common language" between natural language and SQL.

```json
{
  "description": "Find open deals where the customer has more than 2 escalated support tickets",
  "primary_entity": "ent:SalesOpportunity",
  "select": [
    "ent:opportunityName",
    "ent:estimatedValue",
    "ent:estimatedCloseDate",
    "ent:customer.schema:name",
    "ent:pipelineStage"
  ],
  "filters": [
    {
      "property": "ent:opportunityStatus",
      "operator": "eq",
      "value": "Open"
    }
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
      "alias": "open_ticket_count",
      "filters": [
        {
          "property": "ent:ticketStatus",
          "operator": "in",
          "value": ["Escalated", "Open", "InProgress"]
        }
      ]
    }
  ],
  "having": [
    {
      "alias": "open_ticket_count",
      "operator": "gt",
      "value": 2
    }
  ],
  "order_by": [
    {"property": "ent:estimatedValue", "direction": "desc"}
  ]
}
```

### 4.3 LLM Prompt for NL -> Semantic Query

Implement as a Python module: `translator/nl_to_semantic.py`

The LLM prompt must include:
1. The complete ontology (all types, properties, and enumerations)
2. The semantic query language spec with examples
3. The user's question

```python
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
  "aggregations": [{"function": "count|sum|avg|min|max", "entity": "type", "alias": "name", "filters": [...]}],
  "having": [{"alias": "...", "operator": "...", "value": ...}],
  "order_by": [{"property": "...", "direction": "asc|desc"}],
  "limit": null
}

Omit any top-level keys that are empty or not needed.

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
"""
```

### 4.4 Semantic Query -> SQL Compiler

Implement as: `translator/semantic_to_sql.py`

This is the deterministic (non-LLM) component that reads the TMCF mappings and enum mappings, and compiles a semantic query into SQL.

#### Algorithm

```
Input: SemanticQuery (JSON), TMCF mappings, enum_mappings
Output: SQL query string, list of (database_file, table_name) to execute against

1. RESOLVE PRIMARY TABLE
   - Look up primary_entity in TMCF mappings
   - Find which source database + table maps to this type
   - If multiple sources map to the same type (e.g., Organization appears in
     both HubSpot and D365), pick the "richest" source or the one that has
     the most requested select properties. For the POC, use a priority order:
     SalesOpportunity -> dynamics365.d365_opportunities (canonical)
     SupportTicket -> jira.jira_issues (canonical)
     Organization -> dynamics365.d365_accounts (canonical)
     Person -> dynamics365.d365_contacts (canonical)
     MarketingCampaign -> hubspot.hs_campaigns (canonical)
     MarketingEngagement -> hubspot.hs_marketing_emails (canonical)

2. RESOLVE SELECT COLUMNS
   - For each property in select[], look up the TMCF mapping to find the
     source column name
   - For dotted paths like "ent:customer.schema:name", resolve the FK chain:
     ent:customer maps to parentaccountid in d365_opportunities
     schema:name maps to name in d365_accounts
     -> generates a JOIN and selects d365_accounts.name

3. RESOLVE JOINS
   - For each join in joins[], find the target table from TMCF
   - Resolve the "on" properties to actual columns using TMCF
   - The join key is the shared entity identifier (contoso_id)
   - Cross-database joins: since we use SQLite, ATTACH the other database
     files and reference tables as db_alias.table_name

4. RESOLVE FILTERS
   - Map ontology property to source column via TMCF
   - Map enum values through enum_mappings.json
     e.g., ent:opportunityStatus "Open" -> statecode 0 (for D365)
   - Generate WHERE clauses

5. RESOLVE AGGREGATIONS
   - Map to SQL aggregate functions
   - Apply sub-filters within the aggregation
   - Generate GROUP BY as needed

6. GENERATE SQL
   - Combine all parts into a valid SQL statement
   - Use ATTACH DATABASE for cross-database queries
   - Return the SQL plus execution instructions
```

#### Cross-Database Query Pattern

Since the three systems are separate SQLite databases, use ATTACH:

```sql
-- Attach all databases
ATTACH DATABASE 'hubspot.db' AS hubspot;
ATTACH DATABASE 'jira.db' AS jira;
ATTACH DATABASE 'dynamics365.db' AS d365;

-- Example: deals at risk (opportunities with escalated tickets)
SELECT
    d365.d365_opportunities.name AS opportunity_name,
    d365.d365_opportunities.estimatedvalue AS estimated_value,
    d365.d365_opportunities.estimatedclosedate AS close_date,
    d365.d365_accounts.name AS customer_name,
    COUNT(jira.jira_issues.issue_id) AS escalated_ticket_count
FROM d365.d365_opportunities
JOIN d365.d365_accounts
    ON d365.d365_opportunities.parentaccountid = d365.d365_accounts.accountid
JOIN jira.jira_issue_customer_link
    ON d365.d365_accounts.contoso_id = jira.jira_issue_customer_link.contoso_customer_id
JOIN jira.jira_issues
    ON jira.jira_issue_customer_link.issue_id = jira.jira_issues.issue_id
WHERE d365.d365_opportunities.statecode = 0  -- Open
    AND jira.jira_issues.status IN ('Escalated', 'In Progress', 'To Do')
    AND jira.jira_issues.project_id IN (
        SELECT project_id FROM jira.jira_projects WHERE project_key = 'SUP'
    )
GROUP BY d365.d365_opportunities.opportunityid
HAVING COUNT(jira.jira_issues.issue_id) > 2
ORDER BY d365.d365_opportunities.estimatedvalue DESC;
```

### 4.5 Result Summarizer

Implement as: `translator/summarize_results.py`

After SQL execution, pass the results back through an LLM to generate a natural language summary.

```python
SUMMARIZE_PROMPT = """You are summarizing query results for a business user.

The user asked: "{original_question}"

The query found the following results:
{results_as_table}

Provide a concise, actionable summary. Highlight the most important findings.
If there are concerning patterns (e.g., high-value deals with many support issues),
call them out explicitly. Use specific numbers and names from the data.
Keep it to 2-4 paragraphs."""
```

### 4.6 Demo Script

Implement as: `demo.py`

A simple CLI that ties everything together:

```python
"""
Usage: python demo.py "which deals are at risk based on support tickets?"
"""

import sys
from translator.nl_to_semantic import translate_to_semantic
from translator.semantic_to_sql import compile_to_sql
from translator.execute import run_query
from translator.summarize_results import summarize

def main():
    question = sys.argv[1] if len(sys.argv) > 1 else input("Ask a question: ")

    # Step 1: NL -> Semantic Query (LLM)
    print("\n  Translating to semantic query...")
    semantic_query = translate_to_semantic(question)
    print(f"Semantic query:\n{json.dumps(semantic_query, indent=2)}")

    # Step 2: Semantic Query -> SQL (deterministic)
    print("\n  Compiling to SQL...")
    sql, db_config = compile_to_sql(semantic_query)
    print(f"Generated SQL:\n{sql}")

    # Step 3: Execute
    print("\n  Executing query...")
    results = run_query(sql, db_config)
    print(f"Found {len(results)} results")

    # Step 4: Summarize (LLM)
    print("\n  Summarizing results...")
    summary = summarize(question, results)
    print(f"\n{summary}")

if __name__ == "__main__":
    main()
```

### 4.7 Example Queries to Support

The system should handle at least these queries:

1. **"Which deals are at risk based on open support tickets?"**
   - Joins: SalesOpportunity -> Organization <- SupportTicket
   - Cross-system: D365 opportunities + Jira support tickets

2. **"Show me customers with declining marketing engagement who have upcoming renewals"**
   - Joins: Organization <- MarketingEngagement, Organization <- SalesOpportunity
   - Cross-system: HubSpot engagement + D365 opportunities

3. **"What's the average time to resolve support tickets for our top 10 customers by deal value?"**
   - Joins: Organization <- SalesOpportunity, Organization <- SupportTicket
   - Aggregations: avg resolution time, sum deal value
   - Cross-system: all three databases

4. **"Which sales reps have the most deals with customers who have escalated tickets?"**
   - Joins: Person (as owner) -> SalesOpportunity -> Organization <- SupportTicket
   - Cross-system: D365 + Jira

5. **"List all products sold to customers with more than 5 open support tickets"**
   - Joins: Product -> OrderItem -> Order -> Organization <- SupportTicket
   - Cross-system: D365 + Jira

6. **"How many engineering issues are customer-reported versus internally found?"**
   - Filter on labels containing "customer-reported" in Jira
   - Single system but uses ontology vocabulary

7. **"What's our total pipeline value by industry?"**
   - Joins: SalesOpportunity -> Organization
   - Aggregation: sum estimatedValue, group by industry
   - Single system (D365) but expressed in ontology terms

8. **"Show me contacts at customers with both open deals and escalated tickets who haven't opened a marketing email in 3 months"**
   - Joins across all three systems
   - The "holy grail" cross-system query

---

## Part 5: Project Structure

```
enterprise-semantic-layer/
├── README.md
├── requirements.txt              # faker, anthropic (or openai), sqlite3 (stdlib)
├── generate_data.py              # Synthetic data generator
├── databases/
│   ├── hubspot.db               # Generated
│   ├── jira.db                  # Generated
│   └── dynamics365.db           # Generated
├── ontology/
│   ├── enterprise_schema.mcf    # The ontology
│   └── enum_mappings.json       # Enumeration value mappings
├── mappings/
│   ├── hubspot.tmcf             # HubSpot -> ontology mappings
│   ├── jira.tmcf                # Jira -> ontology mappings
│   └── dynamics365.tmcf         # D365 -> ontology mappings
├── translator/
│   ├── __init__.py
│   ├── nl_to_semantic.py        # LLM: English -> SemanticQuery JSON
│   ├── semantic_to_sql.py       # Deterministic: SemanticQuery -> SQL
│   ├── tmcf_parser.py           # Reads TMCF files into lookup structures
│   ├── execute.py               # Runs SQL against SQLite databases
│   └── summarize_results.py     # LLM: Results -> English summary
├── demo.py                      # CLI entry point
└── tests/
    ├── test_data_generation.py  # Verify data consistency
    ├── test_tmcf_parser.py      # Verify TMCF parsing
    ├── test_semantic_to_sql.py  # Verify SQL compilation
    └── test_example_queries.py  # End-to-end tests for the 8 example queries
```

---

## Part 6: Implementation Order

Build in this sequence, testing at each step:

### Step 1: Generate synthetic data
- Implement `generate_data.py`
- Create master entity lists with cross-system IDs
- Populate all three SQLite databases
- Test: Verify row counts match targets, verify cross-system IDs are consistent, run basic SELECT queries

### Step 2: Define ontology and mappings
- Write `enterprise_schema.mcf`
- Write `enum_mappings.json`
- Write the three TMCF files
- Test: Parse all MCF/TMCF files, verify all referenced properties exist in ontology

### Step 3: Build TMCF parser
- Implement `tmcf_parser.py` that reads TMCF files and produces lookup dictionaries:
  - `ontology_type -> [(database, table, column_mappings)]`
  - `ontology_property -> [(database, table, column)]`
- Test: Parser correctly resolves SalesOpportunity to d365_opportunities, SupportTicket to jira_issues, etc.

### Step 4: Build SQL compiler
- Implement `semantic_to_sql.py`
- Handle: single-table queries, cross-database joins via ATTACH, enum value translation, aggregations, HAVING clauses
- Test: Hand-write semantic query JSON for each of the 8 example queries, verify generated SQL is valid and returns expected results

### Step 5: Build NL translator
- Implement `nl_to_semantic.py` using Anthropic API (Claude)
- The prompt includes the full ontology and examples
- Test: Feed each of the 8 example questions, verify the semantic query JSON is correct

### Step 6: Build result summarizer and demo CLI
- Implement `summarize_results.py`
- Implement `demo.py`
- Test: End-to-end with all 8 example queries

### Step 7: Write tests
- Unit tests for TMCF parser
- Unit tests for SQL compiler (given known semantic query -> expected SQL)
- Integration tests that run each example query end-to-end
- Data consistency tests (every contoso_id in Jira customer links exists in D365 accounts, etc.)

---

## Part 7: Key Design Decisions and Constraints

### Use Anthropic API for LLM calls
- Model: claude-sonnet-4-20250514
- Two LLM calls per query: NL->semantic and results->summary
- The SQL compilation step is purely deterministic (no LLM) — this is important because it demonstrates that the semantic layer does the heavy lifting, not prompt engineering

### The SQL compiler must be deterministic
- Given the same semantic query JSON, it must always produce the same SQL
- No LLM in the loop for SQL generation
- This is a key part of the argument: the semantic layer makes the data legible enough that a deterministic compiler can do cross-system joins. You don't need an LLM to figure out that Salesforce Account = SAP Customer.

### TMCF format simplifications for POC
- Data Commons TMCF supports complex features (quantities, nested entities, provenance). For this POC, we use a simplified subset:
  - One entity per Node block
  - Column references (C:) to simple column values
  - No nested entities (handle FK references at query compilation time)
  - Filter expressions as comments (e.g., "# Filter: project_key = 'SUP'") that the parser reads

### Cross-database joins use shared contoso_id
- This is the "assume common IDs" simplification
- In the real system, entity resolution (Part 3 of the proposal) would establish these common IDs
- For the POC, we pre-generate them and plant them in all three databases

### Enum mapping is separate from TMCF
- TMCF maps columns to ontology properties
- enum_mappings.json maps source values to ontology enumeration values
- The SQL compiler uses both: TMCF for column names, enum_mappings for WHERE clause values

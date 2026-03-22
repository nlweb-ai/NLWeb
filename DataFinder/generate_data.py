#!/usr/bin/env python3
"""
Synthetic data generator for the Enterprise Semantic Layer POC.
Generates three SQLite databases (hubspot.db, jira.db, dynamics365.db)
populated with coherent data for the fictional company Contoso Ltd.

Usage: python generate_data.py
"""

import sqlite3
import random
import uuid
import os
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "databases")
os.makedirs(DB_DIR, exist_ok=True)

# ============================================================
# Master Entity Lists
# ============================================================

INDUSTRIES = [
    "Technology", "Manufacturing", "Financial Services", "Healthcare",
    "Retail", "Consulting", "Education", "Agriculture", "Accounting",
]

INDUSTRY_TO_D365_CODE = {
    "Accounting": 1, "Agriculture": 4, "Consulting": 7, "Technology": 12,
    "Financial Services": 15, "Healthcare": 18, "Manufacturing": 21,
    "Retail": 24, "Education": 27,
}

COMPANY_NAMES = [
    "Northwind Traders", "Adventure Works", "Fabrikam Inc", "Tailspin Toys",
    "Woodgrove Bank", "Litware Inc", "Proseware Inc", "Lucerne Publishing",
    "Fourth Coffee", "Consolidated Messenger", "Graphic Design Institute",
    "Humongous Insurance", "Margie's Travel", "Trey Research", "The Phone Company",
    "Wide World Importers", "Datum Corporation", "Coho Vineyard", "Alpine Ski House",
    "A Datum Corporation", "Blue Yonder Airlines", "City Power & Light",
    "Coho Winery", "Nod Publishers", "Southridge Video", "Wingtip Toys",
    "Liberty's Delightful Sinful Bakery", "Relecloud", "VanArsdel Ltd",
    "Bellows College", "Best For You Organics", "Lamna Healthcare",
    "Munson's Pickles", "Adatum Corporation", "Contoso Pharmaceuticals",
    "Fabrikam Residences", "First Up Consultants", "Trey Research Labs",
    "Parnell Aerospace", "Oceana Systems", "Keystone Financial",
    "Summit Technologies", "Pinnacle Solutions", "Redstone Analytics",
    "Cascade Networks", "Verdant Agriculture", "Nova Dynamics",
    "Ironclad Security", "Sapphire Health", "Meridian Software",
]

JOB_TITLES = [
    "VP of Engineering", "CTO", "Director of IT", "Head of Procurement",
    "VP of Sales", "CFO", "Director of Operations", "Head of Product",
    "VP of Marketing", "CEO", "Director of Engineering", "IT Manager",
    "Procurement Manager", "Sales Director", "Operations Manager",
    "Product Manager", "Marketing Director", "Technical Lead",
    "Senior Developer", "Project Manager",
]

EMPLOYEE_ROLES = [
    ("Alex", "Johnson", "Account Executive", "Sales"),
    ("Sarah", "Chen", "Senior Account Executive", "Sales"),
    ("Michael", "Williams", "Sales Manager", "Sales"),
    ("Emily", "Davis", "Marketing Manager", "Marketing"),
    ("James", "Rodriguez", "SDR", "Sales"),
    ("Lisa", "Anderson", "VP of Sales", "Sales"),
    ("David", "Kim", "Solutions Engineer", "Pre-Sales"),
    ("Rachel", "Thompson", "Customer Success Manager", "Customer Success"),
    ("Kevin", "Martinez", "Support Engineer", "Support"),
    ("Amy", "Wilson", "Senior Support Engineer", "Support"),
    ("Brian", "Taylor", "Engineering Manager", "Engineering"),
    ("Jessica", "Brown", "Senior Developer", "Engineering"),
    ("Daniel", "Lee", "DevOps Engineer", "Engineering"),
    ("Nicole", "Garcia", "Product Manager", "Product"),
    ("Ryan", "Thomas", "Technical Writer", "Documentation"),
    ("Michelle", "Jackson", "QA Lead", "Engineering"),
    ("Chris", "White", "Platform Engineer", "Engineering"),
    ("Stephanie", "Harris", "Support Team Lead", "Support"),
    ("Andrew", "Clark", "Data Analyst", "Analytics"),
    ("Laura", "Lewis", "Marketing Coordinator", "Marketing"),
]

PRODUCTS = [
    ("Contoso Platform - Enterprise License", "CONT-ENT-001", "Full enterprise platform license with unlimited users", 50000.00),
    ("Contoso Platform - Professional License", "CONT-PRO-001", "Professional tier license, up to 100 users", 15000.00),
    ("Contoso Platform - Team License", "CONT-TEAM-001", "Team tier license, up to 25 users", 5000.00),
    ("Contoso Analytics Module", "CONT-ANA-001", "Advanced analytics and reporting add-on", 12000.00),
    ("Contoso API Gateway", "CONT-API-001", "API management and gateway module", 8000.00),
    ("Contoso Security Suite", "CONT-SEC-001", "Enhanced security and compliance package", 10000.00),
    ("Implementation Services - Standard", "SVC-IMP-STD", "Standard implementation package (4 weeks)", 25000.00),
    ("Implementation Services - Premium", "SVC-IMP-PRM", "Premium implementation with custom integration (8 weeks)", 50000.00),
    ("Annual Support - Gold", "SVC-SUP-GLD", "Gold support tier with 4-hour SLA", 15000.00),
    ("Annual Support - Platinum", "SVC-SUP-PLT", "Platinum support with dedicated TAM", 30000.00),
    ("Training - Admin Certification", "SVC-TRN-ADM", "Administrator certification training (3 days)", 3000.00),
    ("Training - Developer Bootcamp", "SVC-TRN-DEV", "Developer bootcamp training (5 days)", 5000.00),
    ("Contoso Mobile Module", "CONT-MOB-001", "Mobile application add-on", 6000.00),
    ("Contoso Integration Hub", "CONT-INT-001", "Pre-built integrations for popular enterprise apps", 9000.00),
]

CAMPAIGN_NAMES = [
    ("Q4 2025 Product Launch", "EMAIL", "2025-10-01", "2025-12-31"),
    ("Winter Webinar Series", "CONTENT", "2025-11-15", "2026-02-28"),
    ("Customer Success Stories", "EMAIL", "2025-09-01", "2025-11-30"),
    ("Annual Conference Promotion", "EMAIL", "2025-08-01", "2025-10-15"),
    ("Platform 3.0 Announcement", "EMAIL", "2025-12-01", "2026-01-31"),
    ("New Year Special Offer", "EMAIL", "2026-01-01", "2026-01-31"),
    ("Developer Community Newsletter", "CONTENT", "2025-07-01", "2026-03-31"),
    ("Security Compliance Guide", "CONTENT", "2025-10-15", "2026-03-15"),
    ("Partner Channel Update", "EMAIL", "2025-11-01", "2026-02-28"),
    ("ROI Calculator Campaign", "SOCIAL", "2025-09-15", "2025-12-15"),
]

SUPPORT_SUMMARIES = [
    "Login fails for SSO users", "API rate limiting errors during peak hours",
    "Dashboard not loading after upgrade", "Data export timing out for large datasets",
    "Permission denied error on admin panel", "Integration sync failing with Salesforce",
    "Mobile app crashing on iOS 18", "Report generation produces incorrect totals",
    "User provisioning via SCIM not working", "Webhook delivery failing intermittently",
    "Custom field validation not enforced", "Audit log missing entries for bulk operations",
    "Search indexing delayed by several hours", "File upload size limit too restrictive",
    "Two-factor authentication reset process broken", "Email notifications not being delivered",
    "Calendar sync missing recurring events", "Bulk import fails silently on invalid rows",
    "Role-based access not applying to new module", "PDF export truncating long tables",
    "SSO redirect loop after password change", "API pagination returning duplicate records",
    "Workflow automation triggers firing twice", "Data retention policy not applying correctly",
    "Custom report filters not saving", "Real-time notifications delayed by 30+ minutes",
    "Backup restore fails for databases over 50GB", "Multi-language support missing translations",
    "OAuth token refresh not working", "Performance degradation during business hours",
]

ENG_SUMMARIES = [
    "Implement GraphQL API layer", "Refactor authentication middleware",
    "Add Redis caching for hot queries", "Migrate to PostgreSQL 16",
    "Implement rate limiting service", "Add OpenTelemetry instrumentation",
    "Upgrade React to v19", "Implement server-side rendering",
    "Add E2E test coverage for checkout flow", "Refactor payment processing module",
    "Implement feature flag system", "Add support for custom webhooks",
    "Migrate to Kubernetes", "Implement RBAC v2",
    "Add real-time collaboration features", "Optimize database query performance",
    "Implement audit logging service", "Add multi-tenancy support",
    "Refactor notification system", "Implement data pipeline for analytics",
    "Add support for custom integrations", "Migrate frontend to TypeScript",
    "Implement CI/CD pipeline improvements", "Add automated security scanning",
    "Refactor API versioning strategy", "Implement search improvements",
    "Add bulk operation support", "Optimize file storage service",
    "Implement retry logic for external services", "Add comprehensive API documentation",
]

# ============================================================
# Generate Master Lists
# ============================================================

def generate_customers():
    customers = []
    states = ["WA", "OR", "CA", "NY", "TX", "IL", "MA", "CO", "GA", "FL", "VA", "PA", "NC", "AZ", "OH"]
    cities = {
        "WA": ["Seattle", "Bellevue", "Redmond"], "OR": ["Portland", "Eugene"],
        "CA": ["San Francisco", "Los Angeles", "San Jose", "San Diego"],
        "NY": ["New York", "Albany", "Buffalo"], "TX": ["Austin", "Dallas", "Houston"],
        "IL": ["Chicago", "Naperville"], "MA": ["Boston", "Cambridge"],
        "CO": ["Denver", "Boulder"], "GA": ["Atlanta", "Savannah"],
        "FL": ["Miami", "Orlando", "Tampa"], "VA": ["Arlington", "Richmond"],
        "PA": ["Philadelphia", "Pittsburgh"], "NC": ["Charlotte", "Raleigh"],
        "AZ": ["Phoenix", "Scottsdale"], "OH": ["Columbus", "Cleveland"],
    }
    for i, name in enumerate(COMPANY_NAMES):
        state = states[i % len(states)]
        city = random.choice(cities[state])
        industry = INDUSTRIES[i % len(INDUSTRIES)]
        domain = name.lower().replace(" ", "").replace("'", "").replace(".", "") + ".com"
        customers.append({
            "contoso_id": f"CUST-{i+1:04d}",
            "name": name,
            "domain": domain,
            "industry": industry,
            "city": city,
            "state": state,
            "country": "US",
            "employees": random.randint(50, 5000),
            "revenue": random.randint(1, 50) * 1000000.0,
        })
    return customers

def generate_contacts(customers):
    contacts = []
    idx = 0
    for cust in customers:
        n_contacts = random.randint(3, 6)
        domain = cust["domain"]
        for j in range(n_contacts):
            first = fake.first_name()
            last = fake.last_name()
            title = random.choice(JOB_TITLES)
            email = f"{first[0].lower()}.{last.lower()}@{domain}"
            contacts.append({
                "contoso_id": f"PER-{idx+1:04d}",
                "first": first,
                "last": last,
                "email": email,
                "phone": fake.phone_number(),
                "title": title,
                "customer_id": cust["contoso_id"],
            })
            idx += 1
    return contacts

def generate_employees():
    employees = []
    for i, (first, last, title, dept) in enumerate(EMPLOYEE_ROLES):
        employees.append({
            "contoso_id": f"EMP-{i+1:04d}",
            "first": first,
            "last": last,
            "email": f"{first.lower()}.{last.lower()}@contoso.com",
            "title": title,
            "dept": dept,
            "hs_owner_id": 201 + i,
            "jira_account_id": f"contoso-emp-{i+1:03d}",
            "d365_user_id": f"emp-guid-{i+1:03d}",
        })
    return employees

def generate_deals(customers):
    """Generate ~80 deals. 60% open, 25% won, 15% lost."""
    deals = []
    stages_open = ["Qualify", "Develop", "Propose", "Close"]
    deal_idx = 0
    base_date = datetime(2025, 6, 1)

    for cust in customers:
        n_deals = random.choices([0, 1, 2, 3], weights=[15, 45, 30, 10])[0]
        for _ in range(n_deals):
            roll = random.random()
            if roll < 0.60:
                status = "Open"
                stage = random.choice(stages_open)
                actual_value = None
                actual_close = None
                close_date = (datetime.now() + timedelta(days=random.randint(10, 180))).strftime("%Y-%m-%d")
            elif roll < 0.85:
                status = "Won"
                stage = "Close"
                amount = random.randint(20, 500) * 1000.0
                actual_value = amount
                actual_close = (base_date + timedelta(days=random.randint(0, 200))).strftime("%Y-%m-%d")
                close_date = actual_close
            else:
                status = "Lost"
                stage = "Close"
                actual_value = None
                actual_close = (base_date + timedelta(days=random.randint(0, 200))).strftime("%Y-%m-%d")
                close_date = actual_close

            amount = random.randint(10, 500) * 1000.0
            create_date = base_date + timedelta(days=random.randint(-90, 180))
            product_ref = random.choice(PRODUCTS)

            deals.append({
                "contoso_id": f"DEAL-{deal_idx+1:04d}",
                "name": f"{cust['name']} - {product_ref[0].split(' - ')[0]}",
                "customer_id": cust["contoso_id"],
                "amount": amount if status != "Won" else actual_value,
                "stage": stage,
                "status": status,
                "close_date": close_date,
                "create_date": create_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "actual_value": actual_value,
                "actual_close": actual_close,
                "probability": {"Qualify": 20, "Develop": 40, "Propose": 60, "Close": 80}.get(stage, 50),
            })
            deal_idx += 1
    return deals

# ============================================================
# Pattern embedding: mark specific customers for demo scenarios
# ============================================================

def select_pattern_customers(customers, deals):
    """Select customers for the demo patterns."""
    # Customers with open high-value deals
    cust_with_open_deals = set()
    for d in deals:
        if d["status"] == "Open" and d["amount"] >= 100000:
            cust_with_open_deals.add(d["customer_id"])

    cust_list = [c for c in customers if c["contoso_id"] in cust_with_open_deals]
    if len(cust_list) < 5:
        # Add more customers
        extras = [c for c in customers if c["contoso_id"] not in cust_with_open_deals]
        cust_list.extend(extras[:5 - len(cust_list)])

    patterns = {
        "deals_at_risk": [c["contoso_id"] for c in cust_list[:5]],  # 5 customers
        "onboarding_problems": [],
        "churn_risk": [],
        "competitive_intel": None,
    }

    # Onboarding problems: customers with recently won deals
    won_customers = set()
    for d in deals:
        if d["status"] == "Won":
            won_customers.add(d["customer_id"])
    won_list = [c["contoso_id"] for c in customers if c["contoso_id"] in won_customers]
    patterns["onboarding_problems"] = won_list[:3]

    # Churn risk: pick customers with open deals not in deals_at_risk
    churn_candidates = [c["contoso_id"] for c in customers
                        if c["contoso_id"] not in set(patterns["deals_at_risk"])
                        and any(d["customer_id"] == c["contoso_id"] and d["status"] == "Open" for d in deals)]
    patterns["churn_risk"] = churn_candidates[:3]

    # Competitive intel: one customer with a lost deal
    lost_customers = [d["customer_id"] for d in deals if d["status"] == "Lost"]
    if lost_customers:
        patterns["competitive_intel"] = lost_customers[0]

    return patterns

# ============================================================
# HubSpot Database
# ============================================================

def create_hubspot_db(customers, contacts, employees, deals, patterns):
    db_path = os.path.join(DB_DIR, "hubspot.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # hs_companies
    c.execute("""CREATE TABLE hs_companies (
        company_id INTEGER PRIMARY KEY, contoso_id TEXT, name TEXT, domain TEXT,
        industry TEXT, city TEXT, state TEXT, country TEXT, num_employees INTEGER,
        annual_revenue REAL, lifecycle_stage TEXT, hs_lead_status TEXT,
        createdate TEXT, lastmodifieddate TEXT, hubspot_owner_id INTEGER
    )""")

    # hs_contacts
    c.execute("""CREATE TABLE hs_contacts (
        contact_id INTEGER PRIMARY KEY, contoso_id TEXT, email TEXT UNIQUE,
        firstname TEXT, lastname TEXT, phone TEXT, jobtitle TEXT,
        company_id INTEGER, lifecyclestage TEXT, hs_lead_status TEXT,
        lastmodifieddate TEXT, createdate TEXT
    )""")

    # hs_deals
    c.execute("""CREATE TABLE hs_deals (
        deal_id INTEGER PRIMARY KEY, contoso_id TEXT, dealname TEXT, amount REAL,
        dealstage TEXT, pipeline TEXT, closedate TEXT, createdate TEXT,
        company_id INTEGER, hubspot_owner_id INTEGER, deal_type TEXT, hs_priority TEXT
    )""")

    # hs_deal_contacts
    c.execute("""CREATE TABLE hs_deal_contacts (
        deal_id INTEGER, contact_id INTEGER, role TEXT
    )""")

    # hs_owners
    c.execute("""CREATE TABLE hs_owners (
        owner_id INTEGER PRIMARY KEY, email TEXT, firstname TEXT, lastname TEXT
    )""")

    # hs_marketing_emails
    c.execute("""CREATE TABLE hs_marketing_emails (
        event_id INTEGER PRIMARY KEY, contact_id INTEGER, email_campaign_id INTEGER,
        event_type TEXT, event_timestamp TEXT
    )""")

    # hs_campaigns
    c.execute("""CREATE TABLE hs_campaigns (
        campaign_id INTEGER PRIMARY KEY, name TEXT, type TEXT,
        start_date TEXT, end_date TEXT
    )""")

    # --- Populate ---
    lifecycle_stages = ["subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead",
                        "opportunity", "customer"]
    lead_statuses = ["NEW", "OPEN", "IN_PROGRESS", "CONNECTED"]

    # Owners (employees who are in sales/marketing)
    sales_emps = [e for e in employees if e["dept"] in ("Sales", "Marketing", "Pre-Sales", "Customer Success")]
    for emp in sales_emps:
        c.execute("INSERT INTO hs_owners VALUES (?,?,?,?)",
                  (emp["hs_owner_id"], emp["email"], emp["first"], emp["last"]))

    # Companies — all customers go into HubSpot
    company_id_map = {}  # contoso_id -> hs company_id
    for i, cust in enumerate(customers):
        hs_id = 1001 + i
        company_id_map[cust["contoso_id"]] = hs_id
        owner = random.choice(sales_emps)
        create = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 400))).strftime("%Y-%m-%dT%H:%M:%SZ")
        modified = (datetime(2025, 9, 1) + timedelta(days=random.randint(0, 120))).strftime("%Y-%m-%dT%H:%M:%SZ")
        c.execute("INSERT INTO hs_companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (hs_id, cust["contoso_id"], cust["name"], cust["domain"],
                   cust["industry"], cust["city"], cust["state"], cust["country"],
                   cust["employees"], cust["revenue"],
                   random.choice(lifecycle_stages), random.choice(lead_statuses),
                   create, modified, owner["hs_owner_id"]))

    # Contacts
    contact_id_map = {}  # contoso_id -> hs contact_id
    for i, contact in enumerate(contacts):
        hs_contact_id = 5001 + i
        contact_id_map[contact["contoso_id"]] = hs_contact_id
        hs_company_id = company_id_map.get(contact["customer_id"])
        create = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 400))).strftime("%Y-%m-%dT%H:%M:%SZ")
        modified = (datetime(2025, 9, 1) + timedelta(days=random.randint(0, 120))).strftime("%Y-%m-%dT%H:%M:%SZ")
        c.execute("INSERT INTO hs_contacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (hs_contact_id, contact["contoso_id"], contact["email"],
                   contact["first"], contact["last"], contact["phone"],
                   contact["title"], hs_company_id,
                   random.choice(lifecycle_stages), random.choice(lead_statuses),
                   modified, create))

    # Deals
    hs_stage_map = {
        "Qualify": random.choice(["appointmentscheduled", "qualifiedtobuy"]),
        "Develop": random.choice(["presentationscheduled", "decisionmakerboughtin"]),
        "Propose": "contractsent",
        "Close": None,  # handled per status
    }
    deal_id_map = {}
    for i, deal in enumerate(deals):
        hs_deal_id = 8001 + i
        deal_id_map[deal["contoso_id"]] = hs_deal_id
        hs_company_id = company_id_map.get(deal["customer_id"])
        owner = random.choice(sales_emps)

        if deal["status"] == "Won":
            hs_stage = "closedwon"
        elif deal["status"] == "Lost":
            hs_stage = "closedlost"
        else:
            stage_options = {
                "Qualify": ["appointmentscheduled", "qualifiedtobuy"],
                "Develop": ["presentationscheduled", "decisionmakerboughtin"],
                "Propose": ["contractsent"],
                "Close": ["contractsent"],
            }
            hs_stage = random.choice(stage_options.get(deal["stage"], ["contractsent"]))

        priority = random.choice(["high", "medium", "low"])
        deal_type = random.choice(["newbusiness", "existingbusiness"])

        c.execute("INSERT INTO hs_deals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (hs_deal_id, deal["contoso_id"], deal["name"], deal["amount"],
                   hs_stage, "default", deal["close_date"], deal["create_date"],
                   hs_company_id, owner["hs_owner_id"], deal_type, priority))

    # Deal-contact associations
    roles = ["DECISION_MAKER", "CHAMPION", "INFLUENCER", "BLOCKER", "END_USER"]
    for deal in deals:
        hs_deal_id = deal_id_map[deal["contoso_id"]]
        cust_contacts = [ct for ct in contacts if ct["customer_id"] == deal["customer_id"]]
        if cust_contacts:
            n_assoc = min(len(cust_contacts), random.randint(1, 3))
            for ct in random.sample(cust_contacts, n_assoc):
                hs_ct_id = contact_id_map[ct["contoso_id"]]
                c.execute("INSERT INTO hs_deal_contacts VALUES (?,?,?)",
                          (hs_deal_id, hs_ct_id, random.choice(roles)))

    # Campaigns
    for i, (name, ctype, start, end) in enumerate(CAMPAIGN_NAMES):
        c.execute("INSERT INTO hs_campaigns VALUES (?,?,?,?,?)",
                  (601 + i, name, ctype, start, end))

    # Marketing email events
    event_types = ["SENT", "DELIVERED", "OPEN", "CLICK", "BOUNCE", "UNSUBSCRIBE"]
    event_weights = [30, 25, 20, 10, 10, 5]
    event_id = 30001
    all_contact_ids = list(contact_id_map.values())
    churn_risk_contacts = set()
    for cust_id in patterns.get("churn_risk", []):
        for ct in contacts:
            if ct["customer_id"] == cust_id:
                churn_risk_contacts.add(contact_id_map[ct["contoso_id"]])

    for _ in range(2000):
        ct_id = random.choice(all_contact_ids)
        campaign = random.choice(CAMPAIGN_NAMES)
        campaign_id = 601 + CAMPAIGN_NAMES.index(campaign)

        if ct_id in churn_risk_contacts:
            # Churn risk: no opens in last 3 months, only SENT/DELIVERED
            etype = random.choice(["SENT", "DELIVERED"])
            ts = datetime(2025, 7, 1) + timedelta(days=random.randint(0, 90))
        else:
            etype = random.choices(event_types, weights=event_weights)[0]
            ts = datetime(2025, 7, 1) + timedelta(days=random.randint(0, 240))

        c.execute("INSERT INTO hs_marketing_emails VALUES (?,?,?,?,?)",
                  (event_id, ct_id, campaign_id, etype, ts.strftime("%Y-%m-%dT%H:%M:%SZ")))
        event_id += 1

    conn.commit()
    conn.close()
    print(f"  Created {db_path}")
    return company_id_map, contact_id_map

# ============================================================
# Jira Database
# ============================================================

def create_jira_db(customers, contacts, employees, deals, patterns):
    db_path = os.path.join(DB_DIR, "jira.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""CREATE TABLE jira_projects (
        project_id INTEGER PRIMARY KEY, project_key TEXT UNIQUE, name TEXT,
        project_type TEXT, lead_account_id TEXT
    )""")

    c.execute("""CREATE TABLE jira_issues (
        issue_id INTEGER PRIMARY KEY, issue_key TEXT UNIQUE, project_id INTEGER,
        summary TEXT, description TEXT, issue_type TEXT, status TEXT, priority TEXT,
        assignee_account_id TEXT, reporter_account_id TEXT,
        created TEXT, updated TEXT, resolved TEXT, resolution TEXT,
        story_points INTEGER, sprint_id INTEGER, labels TEXT, components TEXT
    )""")

    c.execute("""CREATE TABLE jira_issue_customer_link (
        issue_id INTEGER, contoso_customer_id TEXT, customer_name TEXT, link_type TEXT
    )""")

    c.execute("""CREATE TABLE jira_users (
        account_id TEXT PRIMARY KEY, display_name TEXT, email TEXT, active INTEGER
    )""")

    c.execute("""CREATE TABLE jira_sprints (
        sprint_id INTEGER PRIMARY KEY, name TEXT, state TEXT,
        start_date TEXT, end_date TEXT, project_id INTEGER
    )""")

    c.execute("""CREATE TABLE jira_comments (
        comment_id INTEGER PRIMARY KEY, issue_id INTEGER, author_account_id TEXT,
        body TEXT, created TEXT
    )""")

    # --- Projects ---
    projects = [
        (10001, "ENG", "Engineering", "software"),
        (10002, "PLATFORM", "Platform", "software"),
        (10003, "SUP", "Support", "service_desk"),
        (10004, "DOCS", "Documentation", "software"),
    ]
    eng_emp = next(e for e in employees if e["dept"] == "Engineering")
    sup_emp = next(e for e in employees if e["dept"] == "Support")
    project_leads = {
        "ENG": eng_emp["jira_account_id"],
        "PLATFORM": next(e for e in employees if "Platform" in e["title"])["jira_account_id"],
        "SUP": sup_emp["jira_account_id"],
        "DOCS": next(e for e in employees if "Writer" in e["title"])["jira_account_id"],
    }
    for pid, key, name, ptype in projects:
        c.execute("INSERT INTO jira_projects VALUES (?,?,?,?,?)",
                  (pid, key, name, ptype, project_leads[key]))

    # --- Jira Users ---
    for emp in employees:
        c.execute("INSERT INTO jira_users VALUES (?,?,?,?)",
                  (emp["jira_account_id"], f"{emp['first']} {emp['last']}",
                   emp["email"], 1))

    # --- Sprints ---
    sprint_id = 401
    sprint_base = datetime(2025, 9, 1)
    for proj_id in [10001, 10002]:
        for s in range(4):
            start = sprint_base + timedelta(weeks=s*2)
            end = start + timedelta(weeks=2)
            state = "closed" if s < 2 else ("active" if s == 2 else "future")
            c.execute("INSERT INTO jira_sprints VALUES (?,?,?,?,?,?)",
                      (sprint_id, f"Sprint {s+1}", state,
                       start.strftime("%Y-%m-%dT00:00:00Z"),
                       end.strftime("%Y-%m-%dT00:00:00Z"), proj_id))
            sprint_id += 1

    # --- Engineering Issues (~200) ---
    eng_types = ["Bug", "Story", "Task", "Epic", "Sub-task"]
    eng_statuses = ["To Do", "In Progress", "In Review", "Done", "Closed"]
    eng_priorities = ["Highest", "High", "Medium", "Low", "Lowest"]
    eng_employees = [e for e in employees if e["dept"] in ("Engineering", "Product", "Documentation")]
    components_list = ["api", "frontend", "backend", "auth", "sso", "database", "search", "notifications"]

    issue_id = 20001
    eng_issue_counter = {"ENG": 0, "PLATFORM": 0, "DOCS": 0}

    for i in range(200):
        proj_key = random.choices(["ENG", "PLATFORM", "DOCS"], weights=[60, 25, 15])[0]
        proj_id = {"ENG": 10001, "PLATFORM": 10002, "DOCS": 10004}[proj_key]
        eng_issue_counter[proj_key] += 1
        issue_key = f"{proj_key}-{eng_issue_counter[proj_key]}"

        itype = random.choices(eng_types, weights=[25, 35, 25, 5, 10])[0]
        status = random.choices(eng_statuses, weights=[15, 25, 15, 30, 15])[0]
        priority = random.choices(eng_priorities, weights=[5, 20, 40, 25, 10])[0]

        assignee = random.choice(eng_employees)
        reporter = random.choice(eng_employees)
        summary = random.choice(ENG_SUMMARIES)
        description = f"As a user, I need {summary.lower()} to improve the platform."

        created = (datetime(2025, 6, 1) + timedelta(days=random.randint(0, 240))).strftime("%Y-%m-%dT%H:%M:%SZ")
        updated = (datetime(2025, 10, 1) + timedelta(days=random.randint(0, 120))).strftime("%Y-%m-%dT%H:%M:%SZ")
        resolved = None
        resolution = None
        if status in ("Done", "Closed"):
            resolved = updated
            resolution = random.choice(["Fixed", "Done", "Won't Fix"])

        sp = random.choice([1, 2, 3, 5, 8, 13]) if itype in ("Story", "Bug") else None
        sprint = random.choice([401, 402, 403, 404, 405, 406, 407, 408, None])

        # ~20% are customer-reported
        labels_list = []
        if random.random() < 0.2:
            labels_list.append("customer-reported")
        if random.random() < 0.15:
            labels_list.append("regression")
        labels = ",".join(labels_list) if labels_list else None

        comps = ",".join(random.sample(components_list, random.randint(1, 3)))

        c.execute("INSERT INTO jira_issues VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (issue_id, issue_key, proj_id, summary, description, itype, status,
                   priority, assignee["jira_account_id"], reporter["jira_account_id"],
                   created, updated, resolved, resolution, sp, sprint, labels, comps))
        issue_id += 1

    # --- Support Issues (~150) ---
    sup_types = ["Service Request", "Incident", "Bug"]
    sup_statuses = ["To Do", "In Progress", "In Review", "Done", "Closed",
                    "Waiting for Customer", "Escalated"]
    sup_employees = [e for e in employees if e["dept"] in ("Support", "Engineering")]
    sup_issue_counter = 0

    deals_at_risk_custs = set(patterns.get("deals_at_risk", []))
    onboarding_custs = set(patterns.get("onboarding_problems", []))
    competitive_cust = patterns.get("competitive_intel")

    for i in range(150):
        sup_issue_counter += 1
        issue_key = f"SUP-{sup_issue_counter}"

        # Pick customer — bias toward pattern customers
        if i < 20 and deals_at_risk_custs:
            cust_id = random.choice(list(deals_at_risk_custs))
        elif i < 30 and onboarding_custs:
            cust_id = random.choice(list(onboarding_custs))
        elif i < 35 and competitive_cust:
            cust_id = competitive_cust
        else:
            cust_id = random.choice(customers)["contoso_id"]

        cust = next(cu for cu in customers if cu["contoso_id"] == cust_id)
        itype = random.choices(sup_types, weights=[40, 40, 20])[0]

        # Deals-at-risk customers get escalated tickets
        if cust_id in deals_at_risk_custs and i < 20:
            status = random.choice(["Escalated", "In Progress", "To Do"])
            priority = random.choice(["Highest", "High"])
        elif cust_id == competitive_cust and i < 35:
            status = random.choice(["In Progress", "To Do", "Escalated"])
            priority = "High"
        else:
            status = random.choices(sup_statuses, weights=[10, 25, 10, 20, 15, 10, 10])[0]
            priority = random.choices(eng_priorities, weights=[5, 20, 40, 25, 10])[0]

        assignee = random.choice(sup_employees)
        reporter = random.choice(sup_employees)
        summary = random.choice(SUPPORT_SUMMARIES)

        # Competitive intel: reference competitor features
        if cust_id == competitive_cust and i >= 30 and i < 35:
            summary = random.choice([
                "Feature parity request: Competitor X has real-time collaboration",
                "Customer comparing us to CompetitorPro - missing bulk import",
                "Lost deal follow-up: customer wants features from AlternativeSoft",
                "Feature request based on competitor evaluation - advanced reporting",
                "Customer requesting capabilities seen in rival product demo",
            ])

        description = f"Customer {cust['name']} reported: {summary}"

        created = (datetime(2025, 9, 1) + timedelta(days=random.randint(0, 150))).strftime("%Y-%m-%dT%H:%M:%SZ")
        updated = (datetime(2025, 11, 1) + timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%dT%H:%M:%SZ")
        resolved = None
        resolution = None
        if status in ("Done", "Closed"):
            resolved = updated
            resolution = random.choice(["Fixed", "Done", "Cannot Reproduce", "Won't Fix"])

        labels = "customer-reported" if random.random() < 0.7 else None
        comps = random.choice(["auth,sso", "api", "frontend", "backend", "notifications", "search"])

        c.execute("INSERT INTO jira_issues VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (issue_id, issue_key, 10003, summary, description, itype, status,
                   priority, assignee["jira_account_id"], reporter["jira_account_id"],
                   created, updated, resolved, resolution, None, None, labels, comps))

        # Customer link
        link_type = random.choice(["REPORTED_BY", "AFFECTS", "REQUESTED_BY"])
        c.execute("INSERT INTO jira_issue_customer_link VALUES (?,?,?,?)",
                  (issue_id, cust_id, cust["name"], link_type))

        issue_id += 1

    # --- Comments (~800 across all issues) ---
    comment_id = 40001
    all_issue_ids = list(range(20001, issue_id))
    for iss_id in all_issue_ids:
        n_comments = random.choices([0, 1, 2, 3, 4, 5], weights=[10, 20, 30, 20, 15, 5])[0]
        for _ in range(n_comments):
            author = random.choice(employees)
            body = fake.paragraph(nb_sentences=random.randint(1, 4))
            ts = (datetime(2025, 10, 1) + timedelta(days=random.randint(0, 120))).strftime("%Y-%m-%dT%H:%M:%SZ")
            c.execute("INSERT INTO jira_comments VALUES (?,?,?,?,?)",
                      (comment_id, iss_id, author["jira_account_id"], body, ts))
            comment_id += 1

    conn.commit()
    conn.close()
    print(f"  Created {db_path}")

# ============================================================
# Dynamics 365 Database
# ============================================================

def create_dynamics365_db(customers, contacts, employees, deals):
    db_path = os.path.join(DB_DIR, "dynamics365.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("""CREATE TABLE d365_accounts (
        accountid TEXT PRIMARY KEY, contoso_id TEXT, name TEXT, accountnumber TEXT,
        revenue REAL, numberofemployees INTEGER, industrycode INTEGER,
        address1_city TEXT, address1_stateorprovince TEXT, address1_country TEXT,
        telephone1 TEXT, websiteurl TEXT, ownerid TEXT, statecode INTEGER,
        createdon TEXT, modifiedon TEXT, customertypecode INTEGER, accountratingcode INTEGER
    )""")

    c.execute("""CREATE TABLE d365_contacts (
        contactid TEXT PRIMARY KEY, contoso_id TEXT, firstname TEXT, lastname TEXT,
        emailaddress1 TEXT, telephone1 TEXT, jobtitle TEXT,
        parentcustomerid TEXT, ownerid TEXT, statecode INTEGER, createdon TEXT
    )""")

    c.execute("""CREATE TABLE d365_opportunities (
        opportunityid TEXT PRIMARY KEY, contoso_id TEXT, name TEXT,
        estimatedvalue REAL, actualvalue REAL, estimatedclosedate TEXT,
        actualclosedate TEXT, stepname TEXT, statecode INTEGER, statuscode INTEGER,
        parentaccountid TEXT, parentcontactid TEXT, ownerid TEXT,
        createdon TEXT, modifiedon TEXT, closeprobability INTEGER,
        budgetamount REAL, purchaseprocess TEXT, purchasetimeframe TEXT
    )""")

    c.execute("""CREATE TABLE d365_products (
        productid TEXT PRIMARY KEY, name TEXT, productnumber TEXT,
        description TEXT, price REAL, productstructure TEXT, statecode INTEGER
    )""")

    c.execute("""CREATE TABLE d365_opportunityproducts (
        opportunityproductid TEXT PRIMARY KEY, opportunityid TEXT, productid TEXT,
        quantity REAL, priceperunit REAL, extendedamount REAL, description TEXT
    )""")

    c.execute("""CREATE TABLE d365_orders (
        salesorderid TEXT PRIMARY KEY, name TEXT, ordernumber TEXT,
        totalamount REAL, customerid TEXT, opportunityid TEXT,
        statecode INTEGER, createdon TEXT, submitdate TEXT
    )""")

    c.execute("""CREATE TABLE d365_systemusers (
        systemuserid TEXT PRIMARY KEY, fullname TEXT, internalemailaddress TEXT,
        title TEXT, businessunitid TEXT, isdisabled INTEGER
    )""")

    # --- System Users ---
    for emp in employees:
        c.execute("INSERT INTO d365_systemusers VALUES (?,?,?,?,?,?)",
                  (emp["d365_user_id"], f"{emp['first']} {emp['last']}",
                   emp["email"], emp["title"], "contoso-bu-001", 0))

    # --- Accounts ---
    account_id_map = {}  # contoso_id -> d365 accountid
    sales_emps = [e for e in employees if e["dept"] in ("Sales", "Customer Success")]
    for cust in customers:
        acc_guid = f"acc-{uuid.uuid4().hex[:8]}"
        account_id_map[cust["contoso_id"]] = acc_guid
        owner = random.choice(sales_emps)
        industry_code = INDUSTRY_TO_D365_CODE.get(cust["industry"], 12)
        acc_number = f"ACC-{cust['name'][:3].upper()}-{random.randint(100,999)}"
        create = (datetime(2023, 1, 1) + timedelta(days=random.randint(0, 700))).strftime("%Y-%m-%dT%H:%M:%SZ")
        modified = (datetime(2025, 9, 1) + timedelta(days=random.randint(0, 120))).strftime("%Y-%m-%dT%H:%M:%SZ")
        cust_type = 3  # Customer
        rating = random.choice([1, 2, 3])

        c.execute("INSERT INTO d365_accounts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (acc_guid, cust["contoso_id"], cust["name"], acc_number,
                   cust["revenue"], cust["employees"], industry_code,
                   cust["city"], cust["state"], cust["country"],
                   fake.phone_number(), f"https://{cust['domain']}",
                   owner["d365_user_id"], 0, create, modified, cust_type, rating))

    # --- Contacts ---
    contact_guid_map = {}  # contoso_id -> d365 contactid
    for contact in contacts:
        ct_guid = f"ct-{uuid.uuid4().hex[:8]}"
        contact_guid_map[contact["contoso_id"]] = ct_guid
        parent_acc = account_id_map.get(contact["customer_id"])
        owner = random.choice(sales_emps)
        create = (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 400))).strftime("%Y-%m-%dT%H:%M:%SZ")

        c.execute("INSERT INTO d365_contacts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (ct_guid, contact["contoso_id"], contact["first"], contact["last"],
                   contact["email"], contact["phone"], contact["title"],
                   parent_acc, owner["d365_user_id"], 0, create))

    # --- Opportunities ---
    opp_guid_map = {}  # contoso_id -> d365 opportunityid
    for deal in deals:
        opp_guid = f"opp-{uuid.uuid4().hex[:8]}"
        opp_guid_map[deal["contoso_id"]] = opp_guid
        parent_acc = account_id_map.get(deal["customer_id"])

        # Pick a contact from this customer
        cust_contacts = [ct for ct in contacts if ct["customer_id"] == deal["customer_id"]]
        parent_ct = contact_guid_map[random.choice(cust_contacts)["contoso_id"]] if cust_contacts else None

        owner = random.choice(sales_emps)
        statecode = {"Open": 0, "Won": 1, "Lost": 2}[deal["status"]]
        statuscode = {0: 1, 1: 3, 2: 4}[statecode]
        modified = (datetime(2025, 10, 1) + timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%dT%H:%M:%SZ")

        purchase_process = random.choice(["Individual", "Committee", "Unknown"])
        purchase_timeframe = random.choice(["Immediate", "ThisQuarter", "ThisYear", "Unknown"])
        budget = deal["amount"] * random.uniform(1.0, 1.5)

        c.execute("INSERT INTO d365_opportunities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (opp_guid, deal["contoso_id"], deal["name"],
                   deal["amount"], deal.get("actual_value"),
                   deal["close_date"], deal.get("actual_close"),
                   deal["stage"], statecode, statuscode,
                   parent_acc, parent_ct, owner["d365_user_id"],
                   deal["create_date"], modified, deal["probability"],
                   budget, purchase_process, purchase_timeframe))

    # --- Products ---
    product_guid_map = {}
    for i, (pname, pnum, pdesc, pprice) in enumerate(PRODUCTS):
        pguid = f"prod-{uuid.uuid4().hex[:8]}"
        product_guid_map[pnum] = pguid
        pstructure = "Product" if not pname.startswith("Implementation") and not pname.startswith("Training") and not pname.startswith("Annual") else "Product"
        c.execute("INSERT INTO d365_products VALUES (?,?,?,?,?,?,?)",
                  (pguid, pname, pnum, pdesc, pprice, pstructure, 0))

    # --- Opportunity Products (~150 line items, 1-3 per opp) ---
    product_guids = list(product_guid_map.values())
    for deal in deals:
        opp_guid = opp_guid_map[deal["contoso_id"]]
        n_items = random.randint(1, 3)
        selected_products = random.sample(product_guids, min(n_items, len(product_guids)))
        for pguid in selected_products:
            op_guid = f"oprod-{uuid.uuid4().hex[:8]}"
            qty = random.randint(1, 50)
            # Find price
            prod_row = next((p for p in PRODUCTS if product_guid_map[p[1]] == pguid), None)
            price = prod_row[3] if prod_row else 1000.0
            # Vary price slightly
            unit_price = price * random.uniform(0.8, 1.2)
            ext = qty * unit_price
            c.execute("INSERT INTO d365_opportunityproducts VALUES (?,?,?,?,?,?,?)",
                      (op_guid, opp_guid, pguid, qty, round(unit_price, 2),
                       round(ext, 2), f"Line item for {prod_row[0] if prod_row else 'product'}"))

    # --- Orders (for won deals, ~30) ---
    won_deals = [d for d in deals if d["status"] == "Won"]
    for i, deal in enumerate(won_deals):
        order_guid = f"order-{uuid.uuid4().hex[:8]}"
        acc_guid = account_id_map.get(deal["customer_id"])
        opp_guid = opp_guid_map[deal["contoso_id"]]
        order_num = f"ORD-{i+1:04d}"
        create = deal.get("actual_close") or deal["close_date"]
        c.execute("INSERT INTO d365_orders VALUES (?,?,?,?,?,?,?,?,?)",
                  (order_guid, f"Order for {deal['name']}", order_num,
                   deal["amount"], acc_guid, opp_guid, 3, create, create))

    conn.commit()
    conn.close()
    print(f"  Created {db_path}")

# ============================================================
# Notion-style Meeting Notes Database
# ============================================================

def create_notion_db(customers, contacts, employees, deals, patterns):
    """Create a Notion-style database with unstructured meeting notes."""
    db_path = os.path.join(DB_DIR, "notion.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Create notes table
    cur.execute("""
        CREATE TABLE notion_notes (
            note_id TEXT PRIMARY KEY,
            title TEXT,
            content TEXT,
            author TEXT,
            created_date TEXT,
            updated_date TEXT,
            tags TEXT
        )
    """)

    # Generate meeting notes with unstructured references to customers
    notes = []
    note_templates = [
        {
            "title": "Weekly sync with {customer_short}",
            "content": "Met with {contact_first} and {contact_last} from {customer_name}. They mentioned {topic}. {observation}",
            "tags": "customer-meeting,sales"
        },
        {
            "title": "Account review: {customer_short}",
            "content": "{contact_first} at {customer_name} raised concerns about {issue}. Need to follow up on {action}.",
            "tags": "account-review,action-item"
        },
        {
            "title": "Demo notes - {customer_short}",
            "content": "Presented {product} to the team at {customer_name}. {contact_first} {contact_last} was impressed by {feature}. Next steps: {next_step}",
            "tags": "demo,sales"
        },
        {
            "title": "Support escalation - {customer_short}",
            "content": "{customer_name} is experiencing {problem}. Spoke with {contact_first}, they're concerned about impact on {business_area}.",
            "tags": "support,escalation"
        }
    ]

    topics = ["expanding to new regions", "API performance", "integrating with Datadog", "migrating from legacy systems",
              "security compliance", "mobile app requirements", "data privacy concerns", "custom integrations"]
    observations = ["Team seemed very engaged.", "Budget approved for Q2.", "Waiting on legal review.",
                   "Competitor mentioned (Salesforce).", "Timeline is tight.", "Very positive feedback."]
    issues = ["API rate limits", "slow dashboard load times", "missing SSO integration", "unclear pricing"]
    actions = ["scheduling technical deep-dive", "sending proposal", "looping in solutions engineering"]
    products = ["Contoso Platform", "Analytics Module", "API Gateway", "Security Suite"]
    features = ["real-time analytics", "the new dashboard", "SSO integration", "API performance"]
    next_steps = ["send follow-up email", "schedule technical call", "prepare custom demo", "draft SOW"]
    problems = ["intermittent API timeouts", "data sync issues", "login errors", "slow query performance"]
    business_areas = ["quarterly reporting", "customer-facing dashboards", "internal analytics", "compliance auditing"]

    # Create notes for pattern customers with clear references
    # Use 5 different customers to create variety
    at_risk_customers = patterns["deals_at_risk"][:5]

    for idx, cust_id in enumerate(at_risk_customers):
        cust = next(c for c in customers if c["contoso_id"] == cust_id)
        cust_contacts = [c for c in contacts if c["customer_id"] == cust_id]
        if cust_contacts:
            contact = random.choice(cust_contacts)
            # Assign different issue types to different customers for variety
            if idx == 0:
                issue = "API rate limits"
                problem = "intermittent API timeouts"
            elif idx == 1:
                issue = "slow dashboard load times"
                problem = "slow query performance"
            elif idx == 2:
                issue = "missing SSO integration"
                problem = "authentication errors"
            elif idx == 3:
                issue = "data sync issues"
                problem = "data sync failures"
            else:
                issue = "unclear pricing"
                problem = "billing discrepancies"

            template = random.choice(note_templates)

            customer_short = cust["name"].split()[0]  # Just first word

            note_id = f"NOTE-{len(notes)+1:04d}"
            created = fake.date_time_between(start_date="-60d", end_date="-10d")

            title = template["title"].format(customer_short=customer_short)
            content = template["content"].format(
                customer_name=cust["name"],
                customer_short=customer_short,
                contact_first=contact["first"],
                contact_last=contact["last"],
                topic=random.choice(topics),
                observation=random.choice(observations),
                issue=issue,
                action=random.choice(actions),
                product=random.choice(products),
                feature=random.choice(features),
                next_step=random.choice(next_steps),
                problem=problem,
                business_area=random.choice(business_areas)
            )

            author = random.choice(employees)["email"]

            notes.append({
                "note_id": note_id,
                "title": title,
                "content": content,
                "author": author,
                "created_date": created.isoformat(),
                "updated_date": created.isoformat(),
                "tags": template["tags"]
            })

    # Add more general notes for other customers (10-15 total notes)
    random_customers = random.sample([c for c in customers if c["contoso_id"] not in patterns["deals_at_risk"][:5]], 8)
    for cust in random_customers:
        cust_contacts = [c for c in contacts if c["customer_id"] == cust["contoso_id"]]
        if cust_contacts:
            contact = random.choice(cust_contacts)
            template = random.choice(note_templates)

            customer_short = cust["name"].split()[0]

            note_id = f"NOTE-{len(notes)+1:04d}"
            created = fake.date_time_between(start_date="-90d", end_date="-5d")

            title = template["title"].format(customer_short=customer_short)
            content = template["content"].format(
                customer_name=cust["name"],
                customer_short=customer_short,
                contact_first=contact["first"],
                contact_last=contact["last"],
                topic=random.choice(topics),
                observation=random.choice(observations),
                issue=random.choice(issues),
                action=random.choice(actions),
                product=random.choice(products),
                feature=random.choice(features),
                next_step=random.choice(next_steps),
                problem=random.choice(problems),
                business_area=random.choice(business_areas)
            )

            author = random.choice(employees)["email"]

            notes.append({
                "note_id": note_id,
                "title": title,
                "content": content,
                "author": author,
                "created_date": created.isoformat(),
                "updated_date": created.isoformat(),
                "tags": template["tags"]
            })

    # Insert notes
    for note in notes:
        cur.execute("""
            INSERT INTO notion_notes (note_id, title, content, author, created_date, updated_date, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (note["note_id"], note["title"], note["content"], note["author"],
              note["created_date"], note["updated_date"], note["tags"]))

    conn.commit()
    conn.close()
    print(f"  Created {db_path}")

# ============================================================
# Main
# ============================================================

def main():
    print("Generating master entity lists...")
    customers = generate_customers()
    contacts = generate_contacts(customers)
    employees = generate_employees()
    deals = generate_deals(customers)
    patterns = select_pattern_customers(customers, deals)

    print(f"  Customers: {len(customers)}")
    print(f"  Contacts: {len(contacts)}")
    print(f"  Employees: {len(employees)}")
    print(f"  Deals: {len(deals)}")
    print(f"  Deals at risk customers: {patterns['deals_at_risk']}")
    print(f"  Onboarding problem customers: {patterns['onboarding_problems']}")
    print(f"  Churn risk customers: {patterns['churn_risk']}")
    print(f"  Competitive intel customer: {patterns['competitive_intel']}")

    print("\nGenerating databases...")
    create_hubspot_db(customers, contacts, employees, deals, patterns)
    create_jira_db(customers, contacts, employees, deals, patterns)
    create_dynamics365_db(customers, contacts, employees, deals)
    create_notion_db(customers, contacts, employees, deals, patterns)

    # Verify counts
    print("\nVerifying...")
    for db_name in ["hubspot.db", "jira.db", "dynamics365.db", "notion.db"]:
        db_path = os.path.join(DB_DIR, db_name)
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"\n  {db_name}:")
        for (tname,) in tables:
            count = cur.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
            print(f"    {tname}: {count} rows")
        conn.close()

    print("\nDone!")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Simple DataFinder Demo - Focused on queries and data sources
Shows which sources are queried and how joins work
"""

import os
import sys
import time
import json
import subprocess
from translator.templates import match_template, get_template
from translator.value_mapper import map_values
from translator.plan_executor import PlanExecutor

# Load API keys from set_keys.sh
set_keys_path = os.path.join(os.path.dirname(__file__), "..", "AskAgent", "set_keys.sh")
if os.path.exists(set_keys_path):
    result = subprocess.run(
        f'source "{set_keys_path}" && env',
        shell=True,
        capture_output=True,
        text=True,
        executable="/bin/bash"
    )
    for line in result.stdout.split('\n'):
        if '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

MAPPINGS_DIR = "mappings"
DATABASES_DIR = "databases"

# Speed control
FAST_MODE = "--fast" in sys.argv
CHAR_DELAY = 0.015 if not FAST_MODE else 0.003
PAUSE_MULTIPLIER = 1.0 if not FAST_MODE else 0.3

# ANSI color codes for "thought trace" background
THOUGHT_BG = "\033[48;5;235m"  # Dark gray background
THOUGHT_RESET = "\033[0m"

def pause(seconds=2):
    """Pause for effect"""
    time.sleep(seconds * PAUSE_MULTIPLIER)

def type_print(text, delay=None):
    """Print text with typewriter effect"""
    if delay is None:
        delay = CHAR_DELAY
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()

def say(text):
    """Print commentary with typewriter effect"""
    print()
    print("💬 ", end='', flush=True)
    type_print(text, CHAR_DELAY * 0.8)
    pause(1.2)

def header(text):
    """Print section header"""
    print(f"\n\n{'='*80}")
    print(f"  ", end='', flush=True)
    type_print(text)
    print(f"{'='*80}\n")
    pause(1.5)

def thought_print(text):
    """Print text with thought trace background"""
    print(f"{THOUGHT_BG}{text}{THOUGHT_RESET}")

def run_query(question):
    """Run a query and show sources + results"""
    print(f"\n{'─'*80}")
    print(f"❓ QUERY: ", end='', flush=True)
    type_print(f'"{question}"', CHAR_DELAY * 1.2)
    print(f"{'─'*80}\n")
    pause(1)

    # Start thought trace section
    print(f"\n{THOUGHT_BG}{'═'*80}")
    print(f"  🧠 DataFinder Trace")
    print(f"{'═'*80}{THOUGHT_RESET}\n")

    # Match template
    match = match_template(question)
    template = get_template(match["template_id"]) if match["score"] >= 50 else None

    if not template:
        thought_print("💭 Using LLM to plan this query...")
        _run_fallback(question)
        return

    # Show which data sources will be used from the steps
    sources = []
    semantic_queries = []
    for step in template.get("steps", []):
        query = step.get("query", {})
        entity = query.get("primary_entity", "")
        if entity:
            sources.append(entity)
            semantic_queries.append(query)

    if sources:
        source_names = [s.split(':')[-1] for s in sources]  # Strip prefixes like "ent:"
        thought_print(f"💭 This query needs data from: {', '.join(source_names)}")

    # Show semantic query
    pause(1)
    thought_print("\n💭 Semantic Query (common schema):")
    for i, sq in enumerate(semantic_queries[:1], 1):  # Show first semantic query
        entity = sq.get('primary_entity', '')
        thought_print(f"  Entity: {entity}")

        # Map entity to actual databases
        entity_sources = []
        if "SalesOpportunity" in entity or "Deal" in entity:
            entity_sources.append("Dynamics 365")
        if "SupportTicket" in entity:
            entity_sources.append("Jira")
        if "Organization" in entity or "Company" in entity:
            entity_sources.append("HubSpot")
        if "Note" in entity or "Document" in entity:
            entity_sources.append("Notion")

        if entity_sources:
            thought_print(f"  Data sources: {', '.join(entity_sources)}")

        if sq.get('select'):
            thought_print(f"  Select: {', '.join(sq['select'][:3])}...")
        if sq.get('filters'):
            for f in sq['filters'][:2]:  # Show first 2 filters
                thought_print(f"  Filter: {f.get('property')} {f.get('operator')} {f.get('value')}")
    pause(1)

    # Check if cross-system join and detect soft joins
    source_systems = set()
    has_unstructured = False
    for entity in sources:
        if "Deal" in entity or "Company" in entity or "Contact" in entity or "Organization" in entity:
            source_systems.add("HubSpot")
        if "Ticket" in entity or "Issue" in entity:
            source_systems.add("Jira")
        if "Opportunity" in entity or "Account" in entity:
            source_systems.add("Dynamics")
        if "Note" in entity or "Document" in entity:
            source_systems.add("Notion")
            has_unstructured = True

    if has_unstructured:
        thought_print(f"💭 SOFT JOIN: LLM reads unstructured text to derive values")
        thought_print(f"💭 Example: analyzing meeting notes to classify account risk")
    elif len(source_systems) > 1:
        thought_print(f"💭 Hard join: {' + '.join(source_systems)}")
        thought_print(f"💭 Using shared 'contoso_id' foreign key")
    else:
        thought_print(f"💭 Single system query: {list(source_systems)[0] if source_systems else 'Unknown'}")

    pause(1)

    # Map values and execute
    mapped_values = map_values(match.get("slots", {}), template)
    executor = PlanExecutor(MAPPINGS_DIR, DATABASES_DIR)
    output = executor.execute(question, template, mapped_values)

    # Show SQL (just first few lines)
    if output.get("sql_queries"):
        thought_print("\n💭 SQL Query:")
        for step_id, sql in output.get("sql_queries", []):
            lines = sql.split("\n")
            # Show first 3 lines
            for line in lines[:3]:
                thought_print(f"  {line}")
            if len(lines) > 3:
                thought_print(f"  ... ({len(lines) - 3} more lines)")

        # Check for JOIN
        sql_upper = sql.upper()
        if "JOIN" in sql_upper:
            pause(2)
            if "LEFT JOIN" in sql_upper or "LEFT OUTER JOIN" in sql_upper:
                thought_print("💭 This is a SOFT JOIN - includes deals even without matching tickets")
            else:
                thought_print("💭 This is an INNER JOIN - only deals with matching data in both systems")
        pause(2)

    # Show raw results count
    results = output["results"]
    thought_print(f"\n💭 Retrieved {len(results)} records from database")
    pause(1)

    # End thought trace section
    print(f"\n{THOUGHT_BG}{'═'*80}{THOUGHT_RESET}\n")
    pause(1)

    # Format and display results with LLM
    if results:
        from translator.llm_client import chat

        # Format results for LLM
        results_text = ""
        for i, r in enumerate(results[:20], 1):  # Send up to 20 records to LLM
            result_dict = dict(r)
            results_text += f"{i}. {json.dumps(result_dict, default=str)}\n"

        thought_print(f"💭 Formatting {len(results)} results with LLM...\n")
        pause(1)

        format_prompt = f"""Format these query results as a clean text table with the most important columns.
Show ONLY the first 3 result rows (plus header).
Add a brief 1-sentence summary at the top.

Query: {question}

Results:
{results_text}

Format as:
Summary: [one sentence about what the data shows]

[Table header]
[Row 1]
[Row 2]
[Row 3]

Keep it concise and readable."""

        formatted_output = chat(
            system="You are a data analyst formatting query results into clean, readable tables.",
            user=format_prompt,
            temperature=0.2,
            max_tokens=600
        )

        print("✅ Results:\n")
        # Print formatted output normally (not typewriter)
        for line in formatted_output.strip().split('\n'):
            print("  " + line)
        print()
    else:
        print("✅ No results found\n")

    pause(2)

def _run_soft_join_query(question):
    """Execute a soft join query - analyze notes with LLM to derive risk"""
    import sqlite3
    from translator.llm_client import chat

    thought_print("💭 Reading meeting notes from Notion...")
    pause(1)

    # Read notes from Notion
    notes_db = os.path.join(DATABASES_DIR, "notion.db")
    conn = sqlite3.connect(notes_db)
    cur = conn.cursor()
    notes = cur.execute("SELECT note_id, title, content FROM notion_notes").fetchall()
    conn.close()

    thought_print(f"💭 Found {len(notes)} meeting notes")
    pause(1)

    thought_print("💭 Analyzing each note with LLM to derive risk level and extract company names...")
    pause(1)

    # Analyze each note with LLM
    analyzed_notes = []
    for note_id, title, content in notes[:10]:  # Limit to 10 for demo speed
        analysis_prompt = f"""Analyze this meeting note and extract:
1. Company name mentioned (full name, e.g., "Woodgrove Bank")
2. Risk level (high/medium/low) based on sentiment, issues, competitive mentions

Meeting note: "{content}"

Respond with JSON only:
{{"company_name": "...", "risk_level": "high|medium|low", "reason": "brief explanation"}}"""

        result = chat(
            system="You extract structured data from meeting notes.",
            user=analysis_prompt,
            temperature=0.2,
            max_tokens=150
        )

        try:
            analysis = json.loads(result.strip())
            analyzed_notes.append({
                "note_id": note_id,
                "title": title,
                "content": content,
                "company_name": analysis.get("company_name"),
                "risk_level": analysis.get("risk_level"),
                "reason": analysis.get("reason")
            })
        except:
            pass

    thought_print(f"💭 Analyzed {len(analyzed_notes)} notes with LLM-derived risk levels")
    pause(1)

    # Get high-risk accounts
    high_risk_accounts = [n for n in analyzed_notes if n["risk_level"] == "high"]

    thought_print(f"💭 Found {len(high_risk_accounts)} high-risk accounts based on note analysis")
    pause(1)

    # Match to deals
    thought_print("💭 Matching company names to deals in HubSpot...")
    pause(1)

    deals_db = os.path.join(DATABASES_DIR, "hubspot.db")
    conn = sqlite3.connect(deals_db)
    cur = conn.cursor()

    results = []
    for note in high_risk_accounts:
        # Fuzzy match company name
        company_pattern = f"%{note['company_name'].split()[0]}%"  # Match first word
        deals = cur.execute("""
            SELECT d.dealname, d.amount, c.name as company_name, d.dealstage
            FROM hs_deals d
            JOIN hs_companies c ON d.company_id = c.company_id
            WHERE c.name LIKE ?
        """, (company_pattern,)).fetchall()

        for deal in deals:
            results.append({
                "deal_name": deal[0],
                "amount": deal[1],
                "company": deal[2],
                "stage": deal[3],
                "risk_reason": note["reason"],
                "note_content": note["content"][:100] + "..."
            })

    conn.close()

    thought_print(f"💭 Matched to {len(results)} deals")
    pause(1)

    # End thought trace
    print(f"\n{THOUGHT_BG}{'═'*80}{THOUGHT_RESET}\n")
    pause(1)

    # Format and display results
    if results:
        thought_print(f"💭 Formatting {len(results)} results with LLM...\n")
        pause(1)

        results_text = ""
        for i, r in enumerate(results[:10], 1):
            results_text += f"{i}. {json.dumps(r, default=str)}\n"

        format_prompt = f"""Format these at-risk deals as a clean table showing the key information.
Show ONLY the first 3 result rows (plus header).

Query: {question}

Results (deals flagged as at-risk based on LLM analysis of meeting notes):
{results_text}

Format as:
Summary: [one sentence about findings]

[Table header]
[Row 1]
[Row 2]
[Row 3]

Keep concise."""

        formatted_output = chat(
            system="You format query results into clean, readable tables.",
            user=format_prompt,
            temperature=0.2,
            max_tokens=600
        )

        print("✅ Results:\n")
        for line in formatted_output.strip().split('\n'):
            print("  " + line)
        print()
    else:
        print("✅ No high-risk deals found\n")

    pause(2)

def _run_fallback(question):
    """Fallback to LLM planner"""
    from translator.nl_to_semantic import translate_to_semantic
    from translator.semantic_to_sql import SemanticToSQLCompiler
    from translator.execute import run_query

    semantic_query = translate_to_semantic(question)
    compiler = SemanticToSQLCompiler(MAPPINGS_DIR, DATABASES_DIR)
    sql, db_config = compiler.compile(semantic_query)

    print("\n📊 SQL Query:")
    for line in sql.split("\n"):
        print(f"  {line}")
    pause(2)

    results = run_query(sql, db_config)
    print(f"\n✅ Results: {len(results)} records found\n")

    for i, r in enumerate(results[:5], 1):
        print(f"{i}. {dict(r)}\n")
    pause(2)

def main():
    """Run the demo"""

    # Title
    header("DataFinder: Natural Language Queries Across Enterprise Systems")
    pause(2)

    # Introduction
    print("""
DataFinder lets you query multiple enterprise systems using natural language.

How it works:
  1. Natural language query → Translated to common semantic schema
  2. Common schema → Mapped to specific database schemas (HubSpot, Jira, etc)
  3. Semantic query → Compiled to SQL for each data source
  4. Results joined and returned

This semantic layer decouples your questions from database-specific schemas.

""")
    pause(5)

    # Show available data sources
    header("Available Data Sources")

    print("""
📦 HUBSPOT (CRM)
   • Companies - 50+ customer accounts
   • Contacts - 200+ people
   • Deals - 80+ opportunities in pipeline

🎫 JIRA (Support & Projects)
   • Issues - 300+ tickets across 4 projects
   • Support Tickets - 150+ customer support cases

💼 DYNAMICS 365 (Sales)
   • Accounts - Customer organizations
   • Opportunities - Sales pipeline
   • Products - Line items and pricing

📊 SALESFORCE (Enterprise CRM)
   • Accounts - Global customer records
   • Opportunities - Enterprise deals
   • Cases - Customer service tickets

📧 ZENDESK (Customer Support)
   • Tickets - Customer inquiries and issues
   • Organizations - Customer accounts
   • Users - Support contacts and agents

📝 NOTION (Meeting Notes)
   • Notes - Unstructured meeting notes and documents
   • No structured risk/sentiment fields - just free text
   • LLM reads and derives insights (e.g., "is account at risk?")

Each system has different schemas and IDs.
DataFinder uses a semantic layer to join them.
""")
    pause(5)

    # Show all three demos upfront
    header("Demo Overview")

    print("""
📋 DEMO 1: Cross-System Hard Join
   Query: "Show me top 5 deals by revenue with more than 3 support tickets"

   Joins HubSpot deals with Jira tickets using database foreign keys (contoso_id).
   Traditional deterministic join - matching records by shared identifiers.

📋 DEMO 2: Soft Join with LLM Classification
   Query: "Which accounts are at risk based on meeting notes?"

   Reads unstructured Notion meeting notes (plain text, no risk fields).
   LLM analyzes each note and DERIVES risk classification from content.
   Semantic join - no foreign keys, values inferred by reading text.

📋 DEMO 3: LLM Map-Reduce for Scale
   Query: "Which deals are at risk based on support tickets?"

   Shows scalable pattern: JOIN → MAP (parallel LLM calls) → REDUCE (code) → SYNTHESIZE.
   Each deal gets tiny context (hundreds of tokens), small models, parallel execution.
   Avoids stuffing all data into one giant LLM call.

""")
    pause(8)

    # Demo 1: Simple cross-system query
    header("Demo 1: Cross-System Hard Join")

    say("Let's start with a query joining two data sources from different apps...")

    run_query("show me top 5 deals by revenue with more than 3 support tickets in the last month")

    pause(3)

    # Demo 2: LLM classification (soft join)
    header("Demo 2: LLM Classification - Soft Join")

    say("Now a 'soft join' - where values are DERIVED from unstructured text by an LLM...")
    pause(1)

    # Show example notes
    print("\n📝 Example meeting notes:\n")
    print('  1. "Woodgrove Bank raised concerns about slow dashboard load times."')
    print('  2. "Fourth Coffee impressed by real-time analytics demo."')
    print('  3. "Meridian mentioned they\'re talking to Datadog (competitor)."\n')
    pause(3)

    say("These notes have NO 'risk_level' field. But an LLM can READ the text...")
    pause(1)
    say("Note 1: concerns about performance → risk = HIGH")
    pause(0.8)
    say("Note 2: impressed by demo → risk = LOW")
    pause(0.8)
    say("Note 3: talking to competitor → risk = HIGH")
    pause(1.5)

    say("Now we can query: 'which accounts are at risk based on meeting notes?'")
    pause(1)
    say("The 'at risk' value is DERIVED by LLM reading text, not from a database column.")
    pause(2)

    # Execute the soft join query
    print(f"\n{'─'*80}")
    print(f"❓ QUERY: ", end='', flush=True)
    type_print(f'"which accounts are at risk based on meeting notes?"', CHAR_DELAY * 1.2)
    print(f"{'─'*80}\n")
    pause(1)

    print(f"\n{THOUGHT_BG}{'═'*80}")
    print(f"  🧠 DataFinder Trace")
    print(f"{'═'*80}{THOUGHT_RESET}\n")

    _run_soft_join_query("which accounts are at risk based on meeting notes?")

    pause(3)

    # Demo 3: Map-reduce pattern
    header("Demo 3: LLM Map-Reduce for Scale")

    say("Final demo: map-reduce pattern for analyzing many entities at scale...")
    pause(1)
    say("The WRONG approach: feed all 50 deals + 300 tickets into one giant LLM call")
    pause(1)
    say("  → Context too large, quality degrades, assessment buried in narrative")
    pause(2)

    say("The RIGHT approach: MAP-REDUCE")
    pause(1)
    say("  1. JOIN: Group tickets under deals (deterministic SQL)")
    pause(0.7)
    say("  2. MAP: 50 parallel small LLM calls, one per deal + its tickets")
    pause(0.7)
    say("  3. REDUCE: Pure code - filter high-risk, sort by value, take top 10")
    pause(0.7)
    say("  4. SYNTHESIZE (optional): One final LLM call over just the top 10")
    pause(2)

    say("Each MAP call has tiny context (hundreds of tokens, not thousands).")
    pause(1)
    say("Small models, cheap, fast. 50 calls in parallel = wall-clock time of ONE call.")
    pause(1.5)

    # Execute actual map-reduce
    print(f"\n{'─'*80}")
    print(f"❓ QUERY: ", end='', flush=True)
    type_print(f'"which deals are at risk based on support tickets?"', CHAR_DELAY * 1.2)
    print(f"{'─'*80}\n")
    pause(1)

    print(f"\n{THOUGHT_BG}{'═'*80}")
    print(f"  🧠 DataFinder Trace - Map-Reduce Execution")
    print(f"{'═'*80}{THOUGHT_RESET}\n")

    # Phase 1: JOIN with SQL
    thought_print("💭 Phase 1: JOIN - Grouping tickets under deals with SQL")
    pause(1)

    import sqlite3
    from translator.llm_client import chat
    import concurrent.futures

    deals_db = os.path.join(DATABASES_DIR, "hubspot.db")
    tickets_db = os.path.join(DATABASES_DIR, "jira.db")

    conn_deals = sqlite3.connect(deals_db)
    conn_tickets = sqlite3.connect(tickets_db)

    # Get deals with their tickets grouped
    deals = conn_deals.execute("""
        SELECT d.dealname, d.amount, c.name as company_name, c.contoso_id
        FROM hs_deals d
        JOIN hs_companies c ON d.company_id = c.company_id
        WHERE d.dealstage NOT IN ('closedwon', 'closedlost')
        ORDER BY d.amount DESC
        LIMIT 15
    """).fetchall()

    # Group tickets by customer
    deals_with_tickets = []
    for deal in deals:
        deal_name, amount, company, contoso_id = deal
        tickets = conn_tickets.execute("""
            SELECT i.summary, i.priority, i.status, i.created
            FROM jira_issues i
            JOIN jira_issue_customer_link l ON i.issue_id = l.issue_id
            WHERE l.contoso_customer_id = ?
            AND i.project_id IN (SELECT project_id FROM jira_projects WHERE project_key = 'SUP')
        """, (contoso_id,)).fetchall()

        deals_with_tickets.append({
            "deal_name": deal_name,
            "amount": amount,
            "company": company,
            "tickets": tickets
        })

    conn_deals.close()
    conn_tickets.close()

    thought_print(f"  Result: {len(deals_with_tickets)} deals with tickets grouped")
    pause(1)

    # Phase 2: MAP - Parallel LLM calls
    thought_print(f"\n💭 Phase 2: MAP - {len(deals_with_tickets)} parallel LLM calls")
    pause(1)
    thought_print(f"  Starting parallel analysis...")
    pause(0.5)

    def assess_deal_risk(deal_info):
        """Assess one deal's risk with LLM - small context"""
        deal_name = deal_info["deal_name"]
        company = deal_info["company"]
        tickets = deal_info["tickets"]

        ticket_summary = f"{len(tickets)} tickets: " + ", ".join([
            f"{t[1]} priority {t[2]}" for t in tickets[:5]
        ]) if tickets else "No tickets"

        prompt = f"""Assess risk for this deal based on support tickets.

Deal: {deal_name} (${deal_info['amount']:,.0f})
Tickets: {ticket_summary}

Respond with JSON only:
{{"risk_level": "high|medium|low", "reason": "brief explanation"}}"""

        try:
            result = chat(
                system="You assess deal risk based on support ticket patterns.",
                user=prompt,
                temperature=0.2,
                max_tokens=100
            )
            assessment = json.loads(result.strip())
            risk = assessment.get("risk_level", "low")

            # Print completion with result
            thought_print(f"  ✓ {company}: ${deal_info['amount']:,.0f} → {risk} risk")

            return {
                **deal_info,
                "risk_level": risk,
                "reason": assessment.get("reason", "No significant issues")
            }
        except Exception as e:
            thought_print(f"  ✗ {company}: assessment failed")
            return {**deal_info, "risk_level": "low", "reason": "Assessment failed"}

    # Actually run parallel LLM calls with live progress
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        assessed_deals = list(executor.map(assess_deal_risk, deals_with_tickets))

    thought_print(f"\n  Completed {len(assessed_deals)} parallel assessments")
    pause(1)

    # Phase 3: REDUCE - Pure code
    thought_print("\n💭 Phase 3: REDUCE - Pure code (no LLM)")
    pause(1)
    thought_print("  Filter: risk_level == 'high'")

    high_risk = [d for d in assessed_deals if d["risk_level"] == "high"]
    high_risk.sort(key=lambda x: x["amount"], reverse=True)
    top_deals = high_risk[:3]

    thought_print(f"  Sort: by amount DESC")
    thought_print(f"  Limit: top 3")
    thought_print(f"  Result: {len(top_deals)} high-risk deals")
    pause(2)

    # Phase 4: SYNTHESIZE (optional - skip for demo speed)
    thought_print("\n💭 Phase 4: SYNTHESIZE - Skipped for demo speed")
    pause(1)

    print(f"\n{THOUGHT_BG}{'═'*80}{THOUGHT_RESET}\n")
    pause(1)

    # Show results
    print("✅ Results:\n")
    print("  Summary: High-risk deals identified through parallel LLM analysis.\n")
    print("  | Deal                                  | Value      | Tickets | Risk   | Reason                          |")
    print("  |---------------------------------------|------------|---------|--------|---------------------------------|")
    for deal in top_deals:
        print(f"  | {deal['deal_name'][:37]:<37} | ${deal['amount']:>9,.0f} | {len(deal['tickets']):>7} | {deal['risk_level']:<6} | {deal['reason'][:31]:<31} |")
    print()

    pause(3)

    # Closing
    header("Summary")

    print("""
Key Capabilities Demonstrated:

✅ Natural language queries - no SQL required
✅ Automatic source selection - picks the right databases
✅ Cross-system joins - uses shared identifiers
✅ Soft joins - includes records even when data is missing
✅ Unified results - single view across all systems

DataFinder makes enterprise data accessible through simple questions.

""")
    pause(4)

    print(f"\n{'='*80}")
    print("  Demo Complete")
    print(f"{'='*80}\n")
    pause(2)

    print("\n\n⏹️  To stop recording: Click the stop button in your menu bar (top-right)")
    print("   Or press: Cmd+Control+Esc\n")
    pause(3)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏸️  Demo stopped")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

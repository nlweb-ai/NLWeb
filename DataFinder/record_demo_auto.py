#!/usr/bin/env python3
"""
Automated DataFinder Demo Script with Scrolling Commentary
Self-narrating demo for video recording - no voiceover needed!

Usage: python record_demo_auto.py
       python record_demo_auto.py --fast   (reduced pauses for testing)
"""

import sys
import time
import json
from translator.templates import match_template, get_template
from translator.value_mapper import map_values
from translator.plan_executor import PlanExecutor

MAPPINGS_DIR = "mappings"
DATABASES_DIR = "databases"

# Speed control
FAST_MODE = "--fast" in sys.argv
CHAR_DELAY = 0.015 if not FAST_MODE else 0.003
PAUSE_MULTIPLIER = 1.0 if not FAST_MODE else 0.3

def pause(seconds=2):
    """Pause for dramatic effect"""
    time.sleep(seconds * PAUSE_MULTIPLIER)

def type_print(text, delay=None):
    """Print text with typewriter effect"""
    if delay is None:
        delay = CHAR_DELAY
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()

def commentary(text, typing=True):
    """Print commentary with typewriter effect"""
    print()
    prefix = "💬 "
    if typing:
        print(prefix, end='', flush=True)
        type_print(text, CHAR_DELAY * 0.8)
    else:
        print(f"{prefix}{text}")
    pause(1.5)

def narrate(text, pause_after=2):
    """Print major narration"""
    print(f"\n{'='*80}")
    print("  ", end='', flush=True)
    type_print(text.upper())
    print(f"{'='*80}\n")
    pause(pause_after)

def section_header(title):
    """Print section header"""
    print(f"\n\n{'#'*80}")
    print(f"##  ", end='', flush=True)
    type_print(title)
    print(f"{'#'*80}\n")
    pause(1)

def run_query(question, show_sql=True, show_all_results=False):
    """Run a query and display results with commentary"""
    print(f"\n📝 Question: ", end='', flush=True)
    type_print(f'"{question}"', CHAR_DELAY * 1.5)
    print()
    pause(1)

    commentary("Let's see how DataFinder processes this question...")

    # Phase 1a: Template Matching
    print("🔍 PHASE 1A: TEMPLATE MATCHING")
    print("-" * 80)
    match = match_template(question)
    print(f"✓ Matched template: {match['template_id']}")
    print(f"✓ Confidence score: {match['score']}/100")
    if match.get('slots'):
        print(f"✓ Extracted slots: {json.dumps(match['slots'], indent=2)}")
    pause(2)

    if match["template_id"] == "none" or match["score"] < 50:
        commentary("No template matched - falling back to LLM query planner")
        _run_fallback(question)
        return

    template = get_template(match["template_id"])
    if not template:
        commentary(f"Template '{match['template_id']}' not found - falling back")
        _run_fallback(question)
        return

    commentary("The system matched this to a predefined query pattern!")

    # Phase 1b: Value Mapping
    print("\n🗺️  PHASE 1B: VALUE MAPPING")
    print("-" * 80)
    mapped_values = map_values(match.get("slots", {}), template)
    for key, value in mapped_values.items():
        if isinstance(value, list):
            print(f"✓ {key}: {', '.join(map(str, value))}")
        else:
            print(f"✓ {key}: {value}")
    pause(2)

    commentary("Values mapped from natural language to database constraints")

    # Phase 2: Execute Plan
    print("\n⚙️  PHASE 2: EXECUTING QUERY PLAN")
    print("-" * 80)
    executor = PlanExecutor(MAPPINGS_DIR, DATABASES_DIR)
    output = executor.execute(question, template, mapped_values)

    commentary("Generating SQL and querying the databases...")

    # Show SQL
    if show_sql and output.get("sql_queries"):
        print("\n📊 Generated SQL:\n")
        for step_id, sql in output.get("sql_queries", []):
            print(f"  [{step_id}]")
            for line in sql.split("\n"):
                print(f"    {line}")
        pause(3)

        if "JOIN" in sql.upper():
            commentary("Notice the JOIN - this query spans multiple databases!")

    # Display results
    results = output["results"]
    print(f"\n✅ RESULTS: Found {len(results)} matching records")
    print("-" * 80)

    display_count = len(results) if show_all_results else min(5, len(results))
    for i, r in enumerate(results[:display_count], 1):
        result_dict = dict(r)
        print(f"\n{i}. ", end="")
        items = list(result_dict.items())
        print(f"{items[0][0]}: {items[0][1]}")
        for k, v in items[1:]:
            print(f"   {k}: {v}")

    if len(results) > display_count:
        print(f"\n   ... and {len(results) - display_count} more")

    pause(2)
    commentary(f"Retrieved {len(results)} results from the database(s)")

    # Show summary if available
    if output.get("summary"):
        print(f"\n💡 SUMMARY:")
        print("-" * 80)
        print(output['summary'])
        pause(2)

def _run_fallback(question: str):
    """Fall back to LLM query planner"""
    from translator.nl_to_semantic import translate_to_semantic
    from translator.semantic_to_sql import SemanticToSQLCompiler
    from translator.execute import run_query
    from translator.summarize_results import summarize

    print("\n🤖 Translating to semantic query...")
    semantic_query = translate_to_semantic(question)
    print(json.dumps(semantic_query, indent=2))
    pause(2)

    commentary("The LLM converts the question to a structured semantic query")

    print("\n🔧 Compiling to SQL...")
    compiler = SemanticToSQLCompiler(MAPPINGS_DIR, DATABASES_DIR)
    sql, db_config = compiler.compile(semantic_query)
    print(sql)
    pause(2)

    commentary("The compiler uses TMCF mappings to generate SQL")

    print("\n⚙️  Executing query...")
    results = run_query(sql, db_config)
    print(f"✅ Found {len(results)} results")
    for i, r in enumerate(results[:5], 1):
        print(f"\n{i}. {dict(r)}")
    pause(2)

    print("\n💡 Generating summary...")
    summary = summarize(question, results)
    print(f"\n{summary}")
    pause(2)

def main():
    """Run the complete demo"""

    # Introduction
    narrate("DataFinder: Enterprise Semantic Layer Demo", 2)

    commentary("Welcome! This is DataFinder - a semantic layer for enterprise data.")
    commentary("Watch as we query multiple business systems using natural language.")
    pause(1)

    print("""
THE CHALLENGE:
• Customer data scattered across HubSpot (CRM), Jira (Support), Dynamics (Sales)
• Each system has different schemas, column names, and IDs
• Normally requires custom integration code to join data

THE SOLUTION:
• Semantic layer based on Schema.org
• Natural language to SQL translation
• Automatic cross-system joins

Let's see it in action...
""")
    pause(5)

    # Demo 1: Simple Query
    section_header("DEMO 1: SIMPLE QUERY - FIND AT-RISK DEALS")

    commentary("Let's start with a basic question about deals in our pipeline")

    run_query("which deals are at risk?")

    commentary("That's it! No SQL required - just ask the question in English.")
    commentary("The template matched, values mapped, and SQL generated automatically.")
    pause(3)

    # Demo 2: Cross-System Query
    section_header("DEMO 2: CROSS-SYSTEM QUERY - JOINING MULTIPLE DATABASES")

    commentary("Now for something more powerful - a question spanning multiple systems")
    commentary("This requires joining HubSpot deals with Jira support tickets")
    pause(2)

    run_query("which deals are at risk based on support tickets?")

    commentary("Notice how it automatically:")
    pause(0.5)
    commentary("  ✓ Identified we need TWO systems (HubSpot + Jira)")
    pause(0.5)
    commentary("  ✓ Joined them using the shared 'contoso_id' identifier")
    pause(0.5)
    commentary("  ✓ Combined deal stages + ticket priority to define 'at risk'")
    pause(0.5)
    commentary("  ✓ Generated complex SQL with joins and filters")
    pause(2)

    commentary("This normally requires custom integration code!")
    commentary("With DataFinder, it's just a natural language question.")
    pause(4)

    # Demo 3: How It Works
    section_header("DEMO 3: HOW IT WORKS - THE SEMANTIC LAYER")

    commentary("Let me explain the architecture behind this magic...")
    pause(2)

    print("\n📁 LAYER 1: SOURCE DATABASES\n")
    print("""
Three separate SQLite databases:
• hubspot.db  - CRM data (companies, contacts, deals)
• jira.db     - Support tickets and projects
• dynamics.db - Sales opportunities and accounts

Each has different schemas, column names, and IDs.
""")
    pause(4)

    print("\n🏗️  LAYER 2: SHARED ONTOLOGY\n")
    print("""
Based on Schema.org vocabulary:
• Organization - represents companies across all systems
• Person - represents contacts
• Offer - represents deals/opportunities
• SupportTicket - custom extension for support data

Provides the common language that bridges all systems.
""")
    pause(4)

    print("\n🗺️  LAYER 3: TMCF MAPPINGS\n")
    print("""
Declarative mappings from native schemas to ontology:

HubSpot:
  hs_companies → schema:Organization
  company_id → @id
  name → schema:name

Dynamics:
  Account → schema:Organization
  AccountId → @id
  Name → schema:name

These mappings are just YAML - no code required!
""")
    pause(5)

    commentary("The mappings tell the system how to translate between schemas")

    print("\n🤖 LAYER 4: NL TRANSLATOR\n")
    print("""
Two-stage translation:

1. Template Matching (Fast)
   → Predefined patterns for common queries
   → Instant matching, no LLM call needed

2. LLM Fallback (Flexible)
   → Handles novel questions
   → Converts English → Semantic → SQL
""")
    pause(4)

    commentary("This hybrid approach gives us speed AND flexibility")
    pause(2)

    # Demo 4: LLM Fallback
    section_header("DEMO 4: LLM FALLBACK - HANDLING NOVEL QUESTIONS")

    commentary("What happens when there's no matching template?")
    commentary("The system falls back to the LLM to plan the query...")
    pause(2)

    run_query("show me the largest deals in Washington state")

    commentary("Even without a predefined template, we got results!")
    commentary("The LLM understood the question and generated the right query.")
    pause(3)

    # Demo 5: Transparency
    section_header("DEMO 5: TRANSPARENCY - TRUST BUT VERIFY")

    commentary("Enterprise users need to trust the results")
    commentary("DataFinder provides full transparency at every step:")
    pause(2)

    print("""
Every query shows:

📊 Template Match & Confidence Score
   → See how confident the system is (0-100)

🗺️  Value Mapping Details
   → How 'at risk' maps to specific database values

📝 Actual SQL Generated
   → Technical users can verify correctness

📈 Raw Results + LLM Summary
   → Data scientists can audit the data

This transparency is crucial for enterprise adoption.
""")
    pause(5)

    # Architecture Summary
    section_header("WHAT WE'VE BUILT - POC STATS")

    print("""
This proof-of-concept demonstrates:

✅ 3 databases (HubSpot, Jira, Dynamics)
✅ 300+ synthetic records across systems
✅ 150 entities mapped to shared ontology
✅ 10+ query templates
✅ Full cross-system join capability
✅ ~2,000 lines of Python

All in a self-contained demo you can run locally!
""")
    pause(5)

    # Use Cases
    section_header("REAL-WORLD USE CASES")

    commentary("Where would you use this in the real world?")
    pause(1)

    print("""
💼 SALES OPERATIONS
   "Show me deals closing this quarter with open support issues"
   → Identify risks before they impact revenue

🎯 CUSTOMER SUCCESS
   "Which customers haven't logged a ticket in 90 days?"
   → Proactive engagement with quiet customers

📊 EXECUTIVE DASHBOARDS
   "What's our pipeline by region with customer health scores?"
   → Cross-functional insights without a data warehouse

🔍 AD-HOC ANALYSIS
   "Compare win rates for deals with vs without support tickets"
   → Answer one-off questions instantly

All without writing SQL or building custom integrations!
""")
    pause(6)

    # Benefits
    section_header("KEY BENEFITS")

    commentary("Why does this matter?")
    pause(1)

    print("""
✅ DATA QUALITY
   → Validated mappings ensure correctness
   → Type safety catches errors early

✅ SECURITY
   → Row-level security enforced in mappings
   → Users only see data they're authorized for

✅ AUDITABILITY
   → Full transparency of query logic
   → Track what data was accessed and when

✅ SCALABILITY
   → Template caching for common queries
   → SQL optimization built in

✅ MAINTAINABILITY
   → Declarative YAML mappings, no code
   → Add new systems without changing core logic

✅ DEVELOPER VELOCITY
   → Self-service analytics
   → No more waiting for data team
""")
    pause(6)

    # Closing
    section_header("CONCLUSION")

    commentary("DataFinder makes enterprise data accessible through natural language")
    pause(2)

    print("""
The semantic layer approach:

🔓 Decouples consumers from source schemas
🚀 Enables self-service analytics
🔧 Reduces integration complexity
⚡ Accelerates time-to-insight

Traditional Approach:
  Question → Ask data team → Custom query → Wait days → Get answer

DataFinder Approach:
  Question → Instant answer

""")
    pause(5)

    commentary("Try it yourself - the code is open source!")
    pause(2)

    print("""
GitHub: https://github.com/nlweb-ai/NLWeb/tree/main/DataFinder

Thank you for watching!
""")
    pause(3)

    print("\n\n")
    print("="*80)
    print("  DEMO COMPLETE")
    print("="*80)
    print("\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏸️  Demo paused by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

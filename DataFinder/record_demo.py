#!/usr/bin/env python3
"""
Automated DataFinder Demo Script
Records a complete demo with narration and pauses for video recording.

Usage: python record_demo.py
"""

import sys
import time
import json
from translator.templates import match_template, get_template
from translator.value_mapper import map_values
from translator.plan_executor import PlanExecutor

MAPPINGS_DIR = "mappings"
DATABASES_DIR = "databases"

def pause(seconds=2):
    """Pause for dramatic effect"""
    time.sleep(seconds)

def narrate(text, pause_after=1.5):
    """Print narration with pause"""
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")
    pause(pause_after)

def section_header(title):
    """Print section header"""
    print(f"\n\n{'#'*80}")
    print(f"##  {title}")
    print(f"{'#'*80}\n")
    pause(1)

def run_query(question, show_sql=True, show_all_results=False):
    """Run a query and display results with commentary"""
    print(f"\n📝 Question: \"{question}\"\n")
    pause(1)

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
        print("\n⚠️  No template matched - falling back to LLM query planner")
        pause(1)
        _run_fallback(question)
        return

    template = get_template(match["template_id"])
    if not template:
        print(f"\n⚠️  Template '{match['template_id']}' not found - falling back")
        pause(1)
        _run_fallback(question)
        return

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

    # Phase 2: Execute Plan
    print("\n⚙️  PHASE 2: EXECUTING QUERY PLAN")
    print("-" * 80)
    executor = PlanExecutor(MAPPINGS_DIR, DATABASES_DIR)
    output = executor.execute(question, template, mapped_values)

    # Show SQL
    if show_sql and output.get("sql_queries"):
        print("\n📊 Generated SQL:\n")
        for step_id, sql in output.get("sql_queries", []):
            print(f"  [{step_id}]")
            for line in sql.split("\n"):
                print(f"    {line}")
        pause(3)

    # Display results
    results = output["results"]
    print(f"\n✅ RESULTS: Found {len(results)} matching records")
    print("-" * 80)

    display_count = len(results) if show_all_results else min(5, len(results))
    for i, r in enumerate(results[:display_count], 1):
        result_dict = dict(r)
        print(f"\n{i}. ", end="")
        # Format result nicely
        items = list(result_dict.items())
        print(f"{items[0][0]}: {items[0][1]}")
        for k, v in items[1:]:
            print(f"   {k}: {v}")

    if len(results) > display_count:
        print(f"\n   ... and {len(results) - display_count} more")

    pause(3)

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

    print("\n🔧 Compiling to SQL...")
    compiler = SemanticToSQLCompiler(MAPPINGS_DIR, DATABASES_DIR)
    sql, db_config = compiler.compile(semantic_query)
    print(sql)
    pause(2)

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
    narrate("DATAFINDER: ENTERPRISE SEMANTIC LAYER DEMO", 2)

    print("""
Welcome to DataFinder - an enterprise semantic layer that lets you query
multiple business systems using natural language.

The Challenge:
- Customer data scattered across HubSpot (CRM), Jira (Support), Dynamics (Sales)
- Each system has different schemas, column names, and IDs
- Normally requires custom integration code to join data

The Solution:
- Semantic layer based on Schema.org
- Natural language to SQL translation
- Automatic cross-system joins

Let's see it in action...
""")
    pause(4)

    # Demo 1: Simple Query
    section_header("DEMO 1: SIMPLE QUERY - FIND AT-RISK DEALS")

    narrate("Let's start with a basic question about deals in our pipeline", 2)

    run_query("which deals are at risk?")

    print("""
Notice what just happened:
✓ Matched a predefined template pattern
✓ Mapped 'at risk' to specific deal stages
✓ Generated SQL automatically
✓ Retrieved results from HubSpot database

No SQL required - just ask the question!
""")
    pause(4)

    # Demo 2: Cross-System Query
    section_header("DEMO 2: CROSS-SYSTEM QUERY - JOINS ACROSS DATABASES")

    narrate("Now let's ask something more powerful - a question spanning multiple systems", 2)

    print("""
This question requires joining:
- HubSpot deals table (sales data)
- Jira tickets table (support data)

Watch how the semantic layer handles this automatically...
""")
    pause(3)

    run_query("which deals are at risk based on support tickets?")

    print("""
🎯 Key Points:
✓ Automatically identified we need TWO systems (HubSpot + Jira)
✓ Joined them using the shared 'contoso_id' identifier
✓ Combined deal stages + ticket priority to define "at risk"
✓ Generated complex SQL with joins and filters

This normally requires custom integration code.
With DataFinder, it's just a natural language question.
""")
    pause(5)

    # Demo 3: Show How It Works
    section_header("DEMO 3: UNDER THE HOOD - THE SEMANTIC LAYER")

    narrate("How does this work? Let me show you the components...", 2)

    print("\n📁 TMCF MAPPINGS (Schema Translation)\n")
    print("""
Each system's native schema maps to our shared Schema.org ontology:

HubSpot:
  hs_companies → schema:Organization
  company_id → @id
  name → schema:name

Dynamics:
  Account → schema:Organization
  AccountId → @id
  Name → schema:name

Jira:
  Issues → schema:SupportTicket (custom extension)
  key → @id
  summary → schema:description

The ontology provides the common vocabulary that bridges all systems.
""")
    pause(5)

    print("\n📋 QUERY TEMPLATES (Pattern Matching)\n")
    print("""
Templates define common query patterns:

Template: "deals_at_risk_with_tickets"
  Pattern: "deals at risk based on support tickets"
  Entities: [Deal, SupportTicket]
  Joins: Deal.account_id = Ticket.account_id
  Filters:
    - Deal stage in [contractsent, decisionmaker...]
    - Ticket status = "Open"
    - Ticket priority in ["High", "Critical"]

Templates give us:
✓ Fast matching (no LLM call needed)
✓ Reliable queries (tested patterns)
✓ Type safety (validated schemas)
""")
    pause(5)

    # Demo 4: LLM Fallback
    section_header("DEMO 4: LLM FALLBACK - HANDLING NOVEL QUESTIONS")

    narrate("What happens when there's no matching template?", 2)

    print("""
The system falls back to having the LLM plan the query directly.
This gives us flexibility for unexpected questions...
""")
    pause(2)

    run_query("show me the largest deals in Washington state")

    print("""
🔄 Hybrid Approach Benefits:
✓ Templates = Speed + Reliability for common questions
✓ LLM Fallback = Flexibility for novel questions
✓ Best of both worlds

The LLM:
1. Translates English → Semantic query structure
2. Compiler converts Semantic → SQL using mappings
3. System executes and returns results
""")
    pause(4)

    # Demo 5: Transparency
    section_header("DEMO 5: TRANSPARENCY - TRUST BUT VERIFY")

    narrate("Enterprise users need to trust the results. DataFinder provides full transparency...", 2)

    print("""
Every query shows:

📊 Template Match & Confidence Score
   → Users see how confident the system is

🗺️  Value Mapping Details
   → Shows how 'at risk' → specific stages

📝 Actual SQL Generated
   → Technical users can verify correctness

📈 Raw Results + Summary
   → Data scientists can audit the data

This transparency is crucial for enterprise adoption.
Users can verify exactly what happened at each step.
""")
    pause(5)

    # Architecture Summary
    section_header("ARCHITECTURE SUMMARY")

    print("""
DataFinder has 4 layers:

1️⃣  SOURCE DATABASES
    → HubSpot, Jira, Dynamics with native schemas
    → Each has different column names, IDs, conventions

2️⃣  ONTOLOGY (Shared Vocabulary)
    → Based on Schema.org
    → Extended for enterprise concepts
    → Provides common language

3️⃣  TMCF MAPPINGS (Schema Bridge)
    → Declarative mappings: Native Schema → Ontology
    → Handles joins, type conversions, defaults
    → No code required - just YAML

4️⃣  NL TRANSLATOR (Query Engine)
    → Template matching for common queries
    → LLM fallback for novel questions
    → Generates SQL from semantic queries

This POC demonstrates:
✅ 3 databases (HubSpot, Jira, Dynamics)
✅ 300+ synthetic records
✅ 150 entities mapped across systems
✅ 10+ query templates
✅ Full cross-system joins
✅ ~2,000 lines of Python
""")
    pause(6)

    # Use Cases
    section_header("REAL-WORLD USE CASES")

    print("""
💼 SALES OPERATIONS
   "Show me deals closing this quarter with open support issues"
   → Identify risks before they impact revenue

🎯 CUSTOMER SUCCESS
   "Which customers haven't logged a ticket in 90 days?"
   → Proactive engagement with quiet customers

📊 EXECUTIVE DASHBOARDS
   "What's our pipeline by region with customer health scores?"
   → Cross-functional insights without data warehouse

🔍 AD-HOC ANALYSIS
   "Compare win rates for deals with vs without support tickets"
   → Answer one-off questions instantly

All without writing SQL or building custom integrations!
""")
    pause(5)

    # Closing
    section_header("CONCLUSION")

    print("""
DataFinder makes enterprise data accessible through natural language
while maintaining:

✅ Data Quality - Validated mappings ensure correctness
✅ Security - Row-level security can be enforced in mappings
✅ Auditability - Full transparency of query logic
✅ Scalability - Template caching + SQL optimization
✅ Maintainability - Declarative mappings, no code

The semantic layer approach:
• Decouples consumers from source schemas
• Enables self-service analytics
• Reduces integration complexity
• Accelerates time-to-insight

Try it yourself - the code is open source!

GitHub: https://github.com/nlweb-ai/NLWeb/tree/main/DataFinder
""")
    pause(3)

    print("\n\n")
    print("="*80)
    print("  DEMO COMPLETE - Thank you for watching!")
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

# DataFinder Video Demo Script

## Overview
Duration: 5-7 minutes
Purpose: Demonstrate how DataFinder's semantic layer enables natural language queries across multiple enterprise systems

---

## Setup (Pre-recording)

1. Open terminal in DataFinder directory
2. Verify databases exist: `ls databases/`
3. Have demo.py ready: `python demo.py --help`
4. Prepare 3-4 example questions

---

## Script

### Introduction (30 seconds)

**[Screen: Terminal ready, demo.py visible in editor]**

"Hi, I'm going to show you DataFinder - an enterprise semantic layer that lets you ask questions in plain English across multiple business systems.

The challenge: Most companies have customer data scattered across different systems - HubSpot for marketing, Jira for support tickets, Dynamics for sales. Each system has its own schema, different column names, different IDs. Normally, joining data across these systems requires custom integration code.

DataFinder solves this using a semantic layer based on Schema.org that provides a unified view."

---

### Demo 1: Simple Query (1 minute)

**[Screen: Show terminal]**

"Let's start with a simple question about our deals."

```bash
python demo.py "which deals are at risk?"
```

**[Wait for output, then explain]**

"Notice what happened:
1. **Template Matching** - The system matched this to a predefined query pattern
2. **Value Mapping** - It understood 'at risk' means deals in certain stages
3. **SQL Generation** - It generated SQL to query the right database
4. **Results** - We get a list of deals with their status and owners

All from a natural language question - no SQL required."

---

### Demo 2: Cross-System Query (2 minutes)

**[Screen: Terminal]**

"Now let's ask something more powerful - a question that spans multiple systems:"

```bash
python demo.py "which deals are at risk based on support tickets?"
```

**[Point to output as it appears]**

"This is where the semantic layer really shines. Watch what happens:

1. **Template Match** - Score 90+, it found the right pattern
2. **Extracted Slots** - It identified we want deals + support tickets
3. **Value Mapping** - Maps 'at risk' and 'support tickets' to actual database values
4. **Multi-System Join** - Look at the SQL - it's joining:
   - HubSpot deals table
   - Jira tickets table

The semantic layer knows:
- Which database has deals (HubSpot)
- Which has support tickets (Jira)
- How to join them using the shared 'contoso_id'

**[Show results]**

And here are our results - deals that have related high-priority support tickets. Each result shows:
- Deal name and amount
- Current stage
- Number of related tickets
- Deal owner

This normally requires writing custom integration code. With DataFinder, it's just a question."

---

### Demo 3: Show the Semantic Layer (1.5 minutes)

**[Screen: Switch to show files]**

"How does this work? Let me show you the semantic layer components."

**[Open mappings directory]**

```bash
ls mappings/
cat mappings/hubspot_tmcf.yaml
```

**[Show excerpt]**

"These are TMCF mappings - they describe how each system's native schema maps to our shared Schema.org ontology:

- HubSpot calls it 'hs_companies' → Schema.org Organization
- Dynamics calls it 'Account' → Also Schema.org Organization
- 'company_id' vs 'AccountId' → Both map to @id

The ontology provides the common vocabulary."

**[Open templates]**

```bash
cat translator/templates.py | head -50
```

"And templates define common query patterns:
- 'Which deals are at risk?'
- 'Show me customers in {region}'
- 'What support tickets are urgent?'

The LLM matches user questions to these patterns, extracts the variable parts (like 'at risk' or region name), and the system handles the rest."

---

### Demo 4: Fallback to LLM (1 minute)

**[Screen: Terminal]**

"What if there's no matching template? The system falls back to having the LLM plan the query directly:"

```bash
python demo.py "show me the largest deals in Washington state"
```

**[Point to output]**

"No template matched, so it says 'Falling back to direct LLM query planning.'

The LLM then:
1. Translates the question to a semantic query structure
2. The compiler generates SQL using the mappings
3. We still get results

So you get the speed and reliability of templates when available, with LLM flexibility as a fallback."

---

### Demo 5: Show Transparency (1 minute)

**[Screen: Terminal, scroll back to previous query]**

"One key feature: full transparency. Every query shows you:

- The matched template and confidence score
- Extracted values and how they were mapped
- The actual SQL that ran
- Raw results plus LLM-generated summary

This is crucial for enterprise adoption - users can trust the results because they can see exactly what happened."

**[Show SQL]**

"Look at this SQL - it's joining three tables across two databases, filtering by multiple conditions. Most business users couldn't write this. But they CAN ask the question in English."

---

### Architecture Summary (1 minute)

**[Screen: Show ARCHITECTURE.md or diagram]**

"The architecture has four layers:

1. **Source Databases** - HubSpot, Jira, Dynamics with their native schemas
2. **Ontology** - Schema.org-based vocabulary
3. **TMCF Mappings** - Declarative mapping from native schemas to ontology
4. **NL Translator** - Converts questions to semantic queries to SQL

This POC has:
- 3 databases with 300+ records
- 150 mapped entities across systems
- 10+ query templates
- Full join capability across systems

All in about 2,000 lines of Python."

---

### Use Cases & Wrap-up (30 seconds)

**[Screen: Terminal or slides]**

"Real-world use cases:

- **Sales Ops**: 'Show deals closing this quarter with open support issues'
- **Customer Success**: 'Which customers haven't logged a ticket in 90 days?'
- **Executive**: 'What's our pipeline by region with engagement scores?'

DataFinder makes enterprise data accessible through natural language while maintaining data quality, security, and auditability.

The code is open source - check the link in the description. Thanks for watching!"

---

## Key Points to Emphasize

1. **Problem**: Data scattered across systems with different schemas
2. **Solution**: Semantic layer with shared ontology
3. **Result**: Natural language queries across all systems
4. **Transparency**: Users see the SQL and can verify results
5. **Hybrid Approach**: Templates for speed + LLM for flexibility

## Visual Tips

- Use terminal with good contrast/font size
- Highlight key parts of output with mouse/cursor
- Pause briefly after each major output to let viewers read
- Use split screen when showing code + terminal
- Keep demo data realistic but clear (easy to understand company names)

## Questions to Anticipate

- "What if data isn't clean?" → Show value mapping handling variations
- "How fast is it?" → Mention template matching is instant, LLM adds 2-3s
- "Does it work with my systems?" → Explain TMCF can map any SQL database
- "What about security?" → Note mappings can enforce row-level security


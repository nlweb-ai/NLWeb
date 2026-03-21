"""
Plan executor: runs execution plans from matched templates.

Handles retrieval steps (compiled via SemanticToSQLCompiler) and
assembly stages: join, map (per-entity LLM), reduce, synthesize.
"""

import json
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from typing import List, Dict, Any, Optional

from .semantic_to_sql import SemanticToSQLCompiler
from .execute import run_query
from .llm_client import chat


class PlanExecutor:
    """Executes template-based query plans."""

    def __init__(self, mappings_dir: str, databases_dir: str):
        self.compiler = SemanticToSQLCompiler(mappings_dir, databases_dir)

    def execute(self, question: str, template: dict, mapped_values: dict) -> dict:
        """Execute a template's plan with mapped values.

        Returns dict with:
            results: list of result dicts
            summary: optional narrative summary
            sql_queries: list of (step_id, sql) for transparency
        """
        # Handle dimension_select_map for pipeline_by_dimension template
        template = self._apply_dimension_mapping(template, mapped_values)

        # 1. Execute retrieval steps
        step_results, sql_queries = self._execute_steps(
            template["steps"], mapped_values, template.get("slot_to_step", {})
        )

        # 2. Assembly
        assemble = template.get("assemble", {"type": "direct"})

        if assemble.get("type") == "direct":
            results = step_results.get("results", list(step_results.values())[0])
            return {"results": results, "summary": None, "sql_queries": sql_queries}

        # Complex assembly: join → map → reduce → synthesize
        output = step_results

        if "join" in assemble:
            output = self._join(step_results, assemble["join"])

        if "map" in assemble:
            output = self._map(output, assemble["map"])

        if "reduce" in assemble:
            output = self._reduce(output, assemble["reduce"])

        summary = None
        if "synthesize" in assemble:
            summary = self._synthesize(question, output, assemble["synthesize"])

        return {"results": output, "summary": summary, "sql_queries": sql_queries}

    def _apply_dimension_mapping(self, template: dict, mapped_values: dict) -> dict:
        """For templates with dimension_select_map, update the query's SELECT."""
        dim_map = template.get("dimension_select_map")
        if not dim_map:
            return template

        dimension = mapped_values.get("dimension")
        if not dimension:
            # Check slots for dimension value
            return template

        template = copy.deepcopy(template)
        # Find best matching dimension
        dim_lower = dimension[0]["value"].lower() if isinstance(dimension, list) else str(dimension).lower()
        for key, select_prop in dim_map.items():
            if key in dim_lower:
                template["steps"][0]["query"]["select"] = [select_prop]
                break

        return template

    def _execute_steps(self, steps: list, mapped_values: dict,
                       slot_to_step: dict) -> tuple:
        """Execute retrieval steps. Returns (step_results, sql_queries)."""
        step_results = {}
        sql_queries = []

        for step in steps:
            step_id = step["id"]
            query = copy.deepcopy(step["query"])

            # Apply mapped value filters to this step
            for slot_name, step_target in slot_to_step.items():
                if step_target == step_id and slot_name in mapped_values:
                    filters = mapped_values[slot_name]
                    if isinstance(filters, list) and filters:
                        query.setdefault("filters", []).extend(filters)

            # Compile and execute
            try:
                sql, db_config = self.compiler.compile(query)
                sql_queries.append((step_id, sql))
                results = run_query(sql, db_config)
                step_results[step_id] = results
            except Exception as e:
                print(f"  Step '{step_id}' failed: {e}")
                sql_queries.append((step_id, f"ERROR: {e}"))
                step_results[step_id] = []

        return step_results, sql_queries

    def _join(self, step_results: dict, join_spec: dict) -> dict:
        """Join results from two steps by a common key.

        Returns dict: {entity_key: {"entity": left_row, "associated": [right_rows]}}
        """
        left_data = step_results[join_spec["left"]]
        right_data = step_results[join_spec["right"]]
        left_key = join_spec["left_key"]
        right_key = join_spec["right_key"]

        # Group right data by key
        right_groups = defaultdict(list)
        for row in right_data:
            key = row.get(right_key, "")
            if key:
                right_groups[key].append(row)

        # Each left row gets its associated right rows
        joined = {}
        for row in left_data:
            key = row.get(left_key, "")
            if key:
                joined[key] = {
                    "entity": row,
                    "associated": right_groups.get(key, [])
                }

        return joined

    def _map(self, joined: dict, map_spec: dict) -> list:
        """Run per-entity LLM calls in parallel for assessment.

        Takes joined {key: {entity, associated}} or list of results.
        Returns list of assessed entities.
        """
        extract_spec = map_spec["extract"]
        prompt_template = map_spec["prompt"]

        # Build per-entity prompts
        entities_to_assess = []
        for key, data in joined.items():
            entity = data["entity"]
            associated = data["associated"]

            deal_info = ", ".join(f"{k}: {v}" for k, v in entity.items())

            if associated:
                ticket_lines = []
                for t in associated[:20]:  # Cap at 20
                    ticket_lines.append(", ".join(f"{k}: {v}" for k, v in t.items()))
                ticket_info = "\n".join(f"  - {line}" for line in ticket_lines)
            else:
                ticket_info = "  (no associated records)"

            prompt = prompt_template.format(
                deal_info=deal_info,
                ticket_info=ticket_info
            )
            entities_to_assess.append((key, entity, associated, prompt))

        # Run LLM calls in parallel
        system = (
            "You are assessing entities based on associated data.\n"
            f"Respond with JSON only matching this schema: {json.dumps(extract_spec)}\n"
            "Be concise in string fields."
        )

        def assess_entity(item):
            key, entity, associated, prompt = item
            try:
                response = chat(system=system, user=prompt, temperature=0, max_tokens=200)
                text = response.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    lines = [l for l in lines if not l.startswith("```")]
                    text = "\n".join(lines)
                assessment = json.loads(text)
                result = dict(entity)
                result.update(assessment)
                return result
            except Exception as e:
                result = dict(entity)
                result["risk_level"] = "unknown"
                result["reason"] = f"Assessment failed: {e}"
                result["ticket_count"] = len(associated)
                return result

        assessed = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(assess_entity, item): item
                       for item in entities_to_assess}
            for future in as_completed(futures):
                assessed.append(future.result())

        return assessed

    def _reduce(self, results: list, reduce_spec: dict) -> list:
        """Filter, sort, and limit assessed results."""
        # Filter
        if "filter" in reduce_spec:
            filt = reduce_spec["filter"]
            field = filt["field"]
            op = filt["operator"]
            value = filt["value"]
            if op == "in":
                results = [r for r in results if r.get(field) in value]
            elif op == "eq":
                results = [r for r in results if r.get(field) == value]
            elif op == "neq":
                results = [r for r in results if r.get(field) != value]

        # Sort
        if "sort" in reduce_spec:
            risk_order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
            sort_fields = [s.strip() for s in reduce_spec["sort"].split(",")]

            def sort_key(r):
                keys = []
                for field in sort_fields:
                    reverse = field.startswith("-")
                    fname = field.lstrip("-")
                    val = r.get(fname, "")

                    if "risk_level" in fname:
                        val = risk_order.get(str(val), 3)
                    elif isinstance(val, (int, float)):
                        pass
                    elif isinstance(val, str):
                        try:
                            val = float(val)
                        except (ValueError, TypeError):
                            val = 0

                    if reverse and isinstance(val, (int, float)):
                        val = -val
                    keys.append(val)
                return keys

            results.sort(key=sort_key)

        # Limit
        if "limit" in reduce_spec:
            results = results[:reduce_spec["limit"]]

        return results

    def _synthesize(self, question: str, results: list, synth_spec: dict) -> str:
        """Generate narrative summary from assessed results."""
        if not results:
            return "No results to summarize."

        # Format as table for the LLM
        headers = list(results[0].keys())
        table_lines = [" | ".join(headers)]
        table_lines.append(" | ".join(["---"] * len(headers)))
        for r in results[:30]:
            table_lines.append(" | ".join(str(r.get(h, "")) for h in headers))
        results_table = "\n".join(table_lines)

        system = "You are a business analyst providing concise, actionable summaries."
        user = (
            f'The user asked: "{question}"\n\n'
            f"After analysis, here are the results ({len(results)} items):\n\n"
            f"{results_table}\n\n"
            f"{synth_spec['prompt']}\n\n"
            "Keep it to 2-4 paragraphs. Use specific names and numbers."
        )

        return chat(system=system, user=user, temperature=0.3, max_tokens=1000)

"""
Deterministic compiler: SemanticQuery JSON -> SQL.

Uses the MappingParser to resolve ontology types/properties to source
database tables/columns, and enum_mappings for value translation.
Generates cross-database queries using SQLite ATTACH.
"""

import os
from typing import Any, Dict, List, Optional, Set, Tuple
from .mapping_parser import MappingParser


# Alias used in generated SQL for each database
DB_ALIASES = {
    "hubspot.db": "hubspot",
    "jira.db": "jira",
    "dynamics365.db": "d365",
}


class SemanticToSQLCompiler:
    def __init__(self, mappings_dir: str, databases_dir: str):
        self.parser = MappingParser(mappings_dir)
        self.databases_dir = databases_dir

    def compile(self, semantic_query: dict) -> Tuple[str, dict]:
        """Compile a semantic query JSON into SQL.

        Returns (sql_string, db_config) where db_config has:
          - primary_db: path to the main database file
          - attach: list of (alias, path) for ATTACH DATABASE statements
        """
        attached_dbs: Set[str] = set()
        joined_tables: Set[str] = set()  # "alias.table" strings already joined

        primary_type = semantic_query["primary_entity"]
        primary_mapping = self.parser.get_canonical_mapping(primary_type)
        if not primary_mapping:
            raise ValueError(f"No mapping found for type: {primary_type}")

        primary_db = primary_mapping["database"]
        primary_table = primary_mapping["table"]
        primary_alias = DB_ALIASES.get(primary_db, "main")
        attached_dbs.add(primary_db)
        joined_tables.add(f"{primary_alias}.{primary_table}")

        select_parts = []
        join_parts = []
        where_parts = []
        group_by_parts = []
        having_parts = []
        order_parts = []

        # Primary table filter (e.g., SUP project filter for SupportTicket)
        if primary_mapping.get("filter"):
            filter_sql = self.parser.get_filter_sql(
                primary_mapping["filter"], db_alias=primary_alias
            )
            if filter_sql:
                where_parts.append(filter_sql)

        # --- SELECT ---
        for prop in semantic_query.get("select", []):
            col_expr, new_joins = self._resolve_select_property(
                prop, primary_type, primary_mapping, primary_alias,
                joined_tables, attached_dbs
            )
            select_parts.append(col_expr)
            join_parts.extend(new_joins)

        # --- FILTERS ---
        for filt in semantic_query.get("filters", []):
            where_parts.append(self._resolve_filter(
                filt, primary_type, primary_mapping, primary_alias
            ))

        # --- JOINS ---
        for join_spec in semantic_query.get("joins", []):
            join_sql = self._resolve_join(
                join_spec, primary_type, primary_mapping, primary_alias,
                joined_tables, attached_dbs
            )
            join_parts.append(join_sql)

        # --- AGGREGATIONS ---
        for agg in semantic_query.get("aggregations", []):
            select_parts.append(self._resolve_aggregation(
                agg, primary_type, primary_mapping, primary_alias
            ))

        # --- GROUP BY ---
        if semantic_query.get("aggregations"):
            for prop in semantic_query.get("select", []):
                ref = self._resolve_column_ref(
                    prop, primary_type, primary_mapping, primary_alias,
                    attached_dbs
                )
                if ref:
                    group_by_parts.append(ref)

        # --- HAVING ---
        for hav in semantic_query.get("having", []):
            having_parts.append(
                f"{hav['alias']} {_sql_op(hav['operator'])} {hav['value']}"
            )

        # --- ORDER BY ---
        agg_aliases = {a["alias"] for a in semantic_query.get("aggregations", [])}
        for ob in semantic_query.get("order_by", []):
            prop = ob["property"]
            direction = ob.get("direction", "asc").upper()
            if prop in agg_aliases:
                order_parts.append(f"{prop} {direction}")
            else:
                ref = self._resolve_column_ref(
                    prop, primary_type, primary_mapping, primary_alias,
                    attached_dbs
                )
                order_parts.append(f"{ref or prop} {direction}")

        # --- Build ATTACH statements ---
        db_config = {"primary_db": os.path.join(self.databases_dir, primary_db), "attach": []}
        attach_stmts = []
        for db_file in sorted(attached_dbs):
            alias = DB_ALIASES.get(db_file, db_file.replace(".db", ""))
            db_path = os.path.join(self.databases_dir, db_file)
            attach_stmts.append(f"ATTACH DATABASE '{db_path}' AS {alias}")
            db_config["attach"].append((alias, db_path))

        # --- Assemble SQL ---
        sql_lines = []
        for s in attach_stmts:
            sql_lines.append(f"{s};")
        if attach_stmts:
            sql_lines.append("")

        sql_lines.append("SELECT")
        sql_lines.append("    " + ",\n    ".join(select_parts))
        sql_lines.append(f"FROM {primary_alias}.{primary_table}")
        sql_lines.extend(j for j in join_parts if j)

        if where_parts:
            sql_lines.append("WHERE " + "\n    AND ".join(where_parts))
        if group_by_parts:
            sql_lines.append("GROUP BY " + ", ".join(group_by_parts))
        if having_parts:
            sql_lines.append("HAVING " + " AND ".join(having_parts))
        if order_parts:
            sql_lines.append("ORDER BY " + ", ".join(order_parts))
        if semantic_query.get("limit"):
            sql_lines.append(f"LIMIT {semantic_query['limit']}")

        return "\n".join(sql_lines) + ";", db_config

    # ----------------------------------------------------------------
    # SELECT resolution
    # ----------------------------------------------------------------

    def _resolve_select_property(
        self, prop: str, primary_type: str, primary_mapping: dict,
        primary_alias: str, joined_tables: Set[str], attached_dbs: Set[str]
    ) -> Tuple[str, List[str]]:
        """Returns (select_expression, list_of_new_join_clauses)."""
        new_joins = []
        alias_safe = prop.replace(".", "_").replace(":", "_")

        if "." in prop:
            fk_prop, target_prop = prop.split(".", 1)
            fk_info = self.parser.resolve_column(
                primary_type, fk_prop, primary_mapping["database"]
            )
            if fk_info and fk_info["type"] == "fk_ref":
                ref = fk_info["ref"]
                ref_table = ref["references"]["table"]
                ref_col = ref["references"]["column"]
                fk_col = ref["column"]
                ref_db = fk_info["database"]
                ref_alias = DB_ALIASES.get(ref_db, "main")
                attached_dbs.add(ref_db)

                qualified_ref = f"{ref_alias}.{ref_table}"
                if qualified_ref not in joined_tables:
                    joined_tables.add(qualified_ref)
                    new_joins.append(
                        f"JOIN {qualified_ref}\n"
                        f"    ON {primary_alias}.{primary_mapping['table']}.{fk_col} = "
                        f"{qualified_ref}.{ref_col}"
                    )

                target_col = self._find_column_in_table(ref_db, ref_table, target_prop)
                if not target_col:
                    target_col = target_prop.split(":")[-1]

                return f"{qualified_ref}.{target_col} AS {alias_safe}", new_joins

            # Handle join-type FK properties (e.g., affectedCustomer via link table)
            if fk_info and fk_info["type"] == "join":
                join_info = fk_info["join"]
                link_table = join_info["table"]
                link_col = join_info["column"]
                link_on = join_info["on"]
                fk_db = fk_info["database"]
                fk_alias = DB_ALIASES.get(fk_db, "main")

                # Join the link table
                link_qualified = f"{fk_alias}.{link_table}"
                if link_qualified not in joined_tables:
                    joined_tables.add(link_qualified)
                    on_parts = " AND ".join(
                        f"{primary_alias}.{primary_mapping['table']}.{tc} = {link_qualified}.{lc}"
                        for tc, lc in link_on.items()
                    )
                    new_joins.append(f"JOIN {link_qualified}\n    ON {on_parts}")

                # Join the target entity table (Organization) to get the property
                org_mapping = self.parser.get_canonical_mapping("schema:Organization")
                if org_mapping:
                    org_table = org_mapping["table"]
                    org_db = org_mapping["database"]
                    org_alias = DB_ALIASES.get(org_db, "main")
                    attached_dbs.add(org_db)
                    org_qualified = f"{org_alias}.{org_table}"

                    if org_qualified not in joined_tables:
                        joined_tables.add(org_qualified)
                        org_id = org_mapping.get("identifier", "contoso_id")
                        new_joins.append(
                            f"JOIN {org_qualified}\n"
                            f"    ON {link_qualified}.{link_col} = {org_qualified}.{org_id}"
                        )

                    target_col = self._find_column_in_table(org_db, org_table, target_prop)
                    if not target_col:
                        target_col = target_prop.split(":")[-1]

                    return f"{org_qualified}.{target_col} AS {alias_safe}", new_joins

        # Direct property
        col_info = self.parser.resolve_column(
            primary_type, prop, primary_mapping["database"]
        )
        if col_info and col_info["type"] == "direct":
            return (
                f"{primary_alias}.{primary_mapping['table']}.{col_info['column']} AS {alias_safe}",
                new_joins,
            )

        # Fallback
        col_name = prop.split(":")[-1]
        return f"{primary_alias}.{primary_mapping['table']}.{col_name} AS {alias_safe}", new_joins

    def _resolve_column_ref(
        self, prop: str, primary_type: str, primary_mapping: dict,
        primary_alias: str, attached_dbs: Set[str]
    ) -> Optional[str]:
        """Column reference for GROUP BY / ORDER BY (no alias)."""
        if "." in prop:
            fk_prop, target_prop = prop.split(".", 1)
            fk_info = self.parser.resolve_column(
                primary_type, fk_prop, primary_mapping["database"]
            )
            if fk_info and fk_info["type"] == "fk_ref":
                ref = fk_info["ref"]
                ref_table = ref["references"]["table"]
                ref_db = fk_info["database"]
                ref_alias = DB_ALIASES.get(ref_db, "main")
                target_col = self._find_column_in_table(ref_db, ref_table, target_prop)
                if not target_col:
                    target_col = target_prop.split(":")[-1]
                return f"{ref_alias}.{ref_table}.{target_col}"

        col_info = self.parser.resolve_column(
            primary_type, prop, primary_mapping["database"]
        )
        if col_info and col_info["type"] == "direct":
            return f"{primary_alias}.{primary_mapping['table']}.{col_info['column']}"
        return None

    # ----------------------------------------------------------------
    # FILTER resolution
    # ----------------------------------------------------------------

    def _resolve_filter(self, filt: dict, primary_type: str,
                        primary_mapping: dict, primary_alias: str) -> str:
        prop = filt["property"]
        op = filt["operator"]
        value = filt["value"]

        col_info = self.parser.resolve_column(
            primary_type, prop, primary_mapping["database"]
        )
        if col_info and col_info["type"] == "direct":
            qualified = f"{primary_alias}.{primary_mapping['table']}.{col_info['column']}"
        else:
            col_name = prop.split(":")[-1]
            qualified = f"{primary_alias}.{primary_mapping['table']}.{col_name}"

        # Enum translation for the value
        if isinstance(value, str):
            source_value = self.parser.resolve_enum_value(
                primary_type, prop, value, primary_mapping["database"]
            )
            if isinstance(source_value, dict) and "_not_in" in source_value:
                quoted = ", ".join(f"'{v}'" for v in source_value["_not_in"])
                return f"{qualified} NOT IN ({quoted})"
            if isinstance(source_value, (list,)):
                quoted = ", ".join(f"'{v}'" for v in source_value)
                return f"{qualified} IN ({quoted})"
            value = source_value

        if op == "eq":
            return f"{qualified} = {_sql_val(value)}"
        elif op == "neq":
            return f"{qualified} != {_sql_val(value)}"
        elif op in ("gt", "lt", "gte", "lte"):
            return f"{qualified} {_sql_op(op)} {_sql_val(value)}"
        elif op == "in" and isinstance(value, list):
            translated = []
            for v in value:
                sv = self.parser.resolve_enum_value(
                    primary_type, prop, v, primary_mapping["database"]
                )
                if isinstance(sv, list):
                    translated.extend(sv)
                elif isinstance(sv, str):
                    translated.append(sv)
                else:
                    translated.append(v)
            quoted = ", ".join(f"'{v}'" for v in translated)
            return f"{qualified} IN ({quoted})"
        elif op == "like":
            return f"{qualified} LIKE {_sql_val(value)}"
        elif op == "is_null":
            return f"{qualified} IS NULL"
        elif op == "is_not_null":
            return f"{qualified} IS NOT NULL"

        return f"{qualified} = {_sql_val(value)}"

    # ----------------------------------------------------------------
    # JOIN resolution
    # ----------------------------------------------------------------

    def _resolve_join(
        self, join_spec: dict, primary_type: str, primary_mapping: dict,
        primary_alias: str, joined_tables: Set[str], attached_dbs: Set[str]
    ) -> str:
        target_type = join_spec["entity"]
        join_kw = join_spec.get("type", "inner").upper() + " JOIN"
        target_mapping = self.parser.get_canonical_mapping(target_type)
        if not target_mapping:
            raise ValueError(f"No mapping for join target: {target_type}")

        target_db = target_mapping["database"]
        target_table = target_mapping["table"]
        target_alias = DB_ALIASES.get(target_db, "main")
        attached_dbs.add(target_db)
        target_qualified = f"{target_alias}.{target_table}"

        # Skip if this table is already joined (e.g., from SELECT dotted path)
        if target_qualified in joined_tables:
            return ""

        on_spec = join_spec["on"]
        left_prop = on_spec["left"].split(".")[-1]
        right_prop = on_spec["right"].split(".")[-1]

        left_info = self.parser.resolve_column(
            primary_type, left_prop, primary_mapping["database"]
        )
        right_info = self.parser.resolve_column(
            target_type, right_prop, target_mapping["database"]
        )

        # Build optional target filter (e.g., SUP project)
        target_filter = ""
        if target_mapping.get("filter"):
            fsql = self.parser.get_filter_sql(
                target_mapping["filter"], db_alias=target_alias
            )
            if fsql:
                target_filter = f"\n    AND {fsql}"

        # Case 1: right side is a cross-table join (affectedCustomer via link table)
        if right_info and right_info["type"] == "join":
            join_info = right_info["join"]
            link_qualified = f"{target_alias}.{join_info['table']}"
            link_col = join_info["column"]

            # Join conditions between target table and link table
            on_parts = [
                f"{target_qualified}.{tc} = {link_qualified}.{lc}"
                for tc, lc in join_info["on"].items()
            ]
            link_on = " AND ".join(on_parts)

            # Build link table ON clause (e.g., issue_id = issue_id)
            link_on_parts = list(join_info["on"].items())

            # Case 1a: left side is FK (e.g., SalesOpportunity.customer → accounts → link)
            if left_info and left_info["type"] == "fk_ref":
                ref = left_info["ref"]
                ref_table = ref["references"]["table"]
                ref_col = ref["references"]["column"]
                id_col = ref["references"].get("identifierColumn", "contoso_id")
                fk_col = ref["column"]
                ref_alias = DB_ALIASES.get(left_info["database"], "main")
                ref_qualified = f"{ref_alias}.{ref_table}"
                attached_dbs.add(left_info["database"])

                accounts_join = ""
                if ref_qualified not in joined_tables:
                    joined_tables.add(ref_qualified)
                    accounts_join = (
                        f"JOIN {ref_qualified}\n"
                        f"    ON {primary_alias}.{primary_mapping['table']}.{fk_col} = "
                        f"{ref_qualified}.{ref_col}\n"
                    )

                joined_tables.add(link_qualified)
                joined_tables.add(target_qualified)

                link_join_conds = " AND ".join(
                    f"{link_qualified}.{lc} = {target_qualified}.{tc}"
                    for tc, lc in link_on_parts
                )

                return (
                    f"{accounts_join}"
                    f"{join_kw} {link_qualified}\n"
                    f"    ON {ref_qualified}.{id_col} = {link_qualified}.{link_col}\n"
                    f"{join_kw} {target_qualified}\n"
                    f"    ON {link_join_conds}{target_filter}"
                )

            # Case 1b: primary IS the org table (e.g., Organization → link → SupportTicket)
            id_col = primary_mapping.get("identifier", "contoso_id")
            joined_tables.add(link_qualified)
            joined_tables.add(target_qualified)

            link_join_conds = " AND ".join(
                f"{link_qualified}.{lc} = {target_qualified}.{tc}"
                for tc, lc in link_on_parts
            )

            return (
                f"{join_kw} {link_qualified}\n"
                f"    ON {primary_alias}.{primary_mapping['table']}.{id_col} = "
                f"{link_qualified}.{link_col}\n"
                f"{join_kw} {target_qualified}\n"
                f"    ON {link_join_conds}{target_filter}"
            )

        # Case 2: right side is a direct column
        if right_info and right_info["type"] == "direct":
            right_col = f"{target_qualified}.{right_info['column']}"

            if left_info and left_info["type"] == "fk_ref":
                ref = left_info["ref"]
                ref_table = ref["references"]["table"]
                ref_col = ref["references"]["column"]
                id_col = ref["references"].get("identifierColumn", "contoso_id")
                fk_col = ref["column"]
                ref_alias = DB_ALIASES.get(left_info["database"], "main")
                ref_qualified = f"{ref_alias}.{ref_table}"
                attached_dbs.add(left_info["database"])

                accounts_join = ""
                if ref_qualified not in joined_tables:
                    joined_tables.add(ref_qualified)
                    accounts_join = (
                        f"JOIN {ref_qualified}\n"
                        f"    ON {primary_alias}.{primary_mapping['table']}.{fk_col} = "
                        f"{ref_qualified}.{ref_col}\n"
                    )

                joined_tables.add(target_qualified)
                return (
                    f"{accounts_join}"
                    f"{join_kw} {target_qualified}\n"
                    f"    ON {ref_qualified}.{id_col} = {right_col}{target_filter}"
                )

        # Fallback: join on identifier columns
        joined_tables.add(target_qualified)
        left_id = primary_mapping.get("identifier", "contoso_id")
        right_id = target_mapping.get("identifier", "contoso_id")
        return (
            f"{join_kw} {target_qualified}\n"
            f"    ON {primary_alias}.{primary_mapping['table']}.{left_id} = "
            f"{target_qualified}.{right_id}{target_filter}"
        )

    # ----------------------------------------------------------------
    # AGGREGATION resolution
    # ----------------------------------------------------------------

    def _resolve_aggregation(self, agg: dict, primary_type: str,
                              primary_mapping: dict, primary_alias: str) -> str:
        func = agg["function"].upper()
        alias = agg["alias"]
        target_type = agg.get("entity", primary_type)
        target_mapping = self.parser.get_canonical_mapping(target_type)
        if not target_mapping:
            return f"{func}(*) AS {alias}"

        target_db = target_mapping["database"]
        target_table = target_mapping["table"]
        target_alias_name = DB_ALIASES.get(target_db, "main")
        tq = f"{target_alias_name}.{target_table}"

        if func == "COUNT":
            agg_filters = agg.get("filters", [])
            if agg_filters:
                conds = []
                for f in agg_filters:
                    prop = f["property"]
                    col_info = self.parser.resolve_column(
                        target_type, prop, target_mapping["database"]
                    )
                    col = f"{tq}.{col_info['column']}" if col_info and col_info["type"] == "direct" else f"{tq}.{prop.split(':')[-1]}"

                    if f["operator"] == "in":
                        translated = []
                        for v in f["value"]:
                            sv = self.parser.resolve_enum_value(
                                target_type, prop, v, target_mapping["database"]
                            )
                            if isinstance(sv, list):
                                translated.extend(sv)
                            elif isinstance(sv, str):
                                translated.append(sv)
                            else:
                                translated.append(v)
                        quoted = ", ".join(f"'{v}'" for v in translated)
                        conds.append(f"{col} IN ({quoted})")
                    elif f["operator"] == "eq":
                        sv = self.parser.resolve_enum_value(
                            target_type, prop, f["value"], target_mapping["database"]
                        )
                        conds.append(f"{col} = {_sql_val(sv)}")

                return f"COUNT(CASE WHEN {' AND '.join(conds)} THEN 1 END) AS {alias}"
            return f"COUNT({tq}.rowid) AS {alias}"

        if func in ("SUM", "AVG", "MIN", "MAX"):
            agg_prop = agg.get("property")
            if not agg_prop:
                # Infer property from alias name or type
                agg_prop = self._infer_numeric_property(target_type, alias)
            if agg_prop:
                col_info = self.parser.resolve_column(
                    target_type, agg_prop, target_mapping["database"]
                )
                if col_info and col_info["type"] == "direct":
                    return f"{func}({tq}.{col_info['column']}) AS {alias}"
            return f"{func}(*) AS {alias}"

        return f"{func}(*) AS {alias}"

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    def _infer_numeric_property(self, ont_type: str, alias: str) -> Optional[str]:
        """Infer a numeric property for SUM/AVG based on alias and type."""
        alias_lower = alias.lower()
        # Map common alias patterns to ontology properties
        hints = {
            "value": "ent:estimatedValue",
            "pipeline": "ent:estimatedValue",
            "revenue": "ent:annualRevenue",
            "amount": "ent:estimatedValue",
            "points": "ent:storyPoints",
        }
        for keyword, prop in hints.items():
            if keyword in alias_lower:
                col = self.parser.resolve_column(ont_type, prop)
                if col:
                    return prop
        return None

    def _find_column_in_table(self, database: str, table: str,
                               ont_property: str) -> Optional[str]:
        for entries in self.parser.type_registry.values():
            for entry in entries:
                if entry["database"] == database and entry["table"] == table:
                    if ont_property in entry["columns"]:
                        return entry["columns"][ont_property]
        return None


def _sql_op(op: str) -> str:
    return {"eq": "=", "neq": "!=", "gt": ">", "lt": "<", "gte": ">=", "lte": "<="}.get(op, op)


def _sql_val(value) -> str:
    if isinstance(value, (int, float)):
        return str(value)
    return f"'{value}'"

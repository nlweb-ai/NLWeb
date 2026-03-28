"""
Parses JSON-LD mapping files from mappings/ directory and provides
lookup structures for the SQL compiler.

Each .jsonld file maps one source database's tables to ontology types/properties.
"""

import json
import os
from typing import Dict, List, Optional, Any


class MappingParser:
    """Loads JSON-LD mapping files and provides lookup methods for the SQL compiler."""

    # Canonical (preferred) source for each ontology type when multiple sources exist
    CANONICAL_SOURCES = {
        "ent:SalesOpportunity": "dynamics365.db",
        "ent:SupportTicket": "jira.db",
        "schema:Organization": "dynamics365.db",
        "schema:Person": "dynamics365.db",
        "ent:MarketingCampaign": "hubspot.db",
        "ent:MarketingEngagement": "hubspot.db",
        "schema:Product": "dynamics365.db",
        "schema:Order": "dynamics365.db",
        "schema:OrderItem": "dynamics365.db",
        "ent:EngineeringIssue": "jira.db",
        "ent:Project": "jira.db",
    }

    def __init__(self, mappings_dir: str):
        self.type_registry: Dict[str, List[dict]] = {}
        self.property_registry: Dict[str, List[tuple]] = {}
        self._load_all(mappings_dir)

    def _load_all(self, mappings_dir: str):
        for filename in sorted(os.listdir(mappings_dir)):
            if filename.endswith('.jsonld'):
                filepath = os.path.join(mappings_dir, filename)
                with open(filepath) as f:
                    data = json.load(f)
                self._process_file(data)

    def _process_file(self, data: dict):
        database = data["sourceDatabase"]
        for mapping in data["mappings"]:
            self._process_mapping(database, mapping)

    def _process_mapping(self, database: str, mapping: dict):
        ont_type = mapping["ontologyType"]
        table = mapping["sourceTable"]
        identifier = mapping.get("identifier")
        filter_spec = mapping.get("filter")
        enum_mappings = mapping.get("enumMappings", {})

        direct_columns = {}
        fk_refs = {}
        joins = {}

        for prop, value in mapping.get("columnMappings", {}).items():
            if isinstance(value, str):
                direct_columns[prop] = value
                self.property_registry.setdefault(prop, []).append(
                    (database, table, value)
                )
            elif isinstance(value, dict):
                if "references" in value:
                    fk_refs[prop] = value
                elif "join" in value:
                    joins[prop] = value["join"]

        entry = {
            "database": database,
            "table": table,
            "identifier": identifier,
            "filter": filter_spec,
            "columns": direct_columns,
            "fk_refs": fk_refs,
            "joins": joins,
            "enums": enum_mappings,
        }
        self.type_registry.setdefault(ont_type, []).append(entry)

    def get_canonical_mapping(self, ont_type: str) -> Optional[dict]:
        """Get the canonical (preferred) mapping for an ontology type."""
        entries = self.type_registry.get(ont_type, [])
        if not entries:
            return None
        canonical_db = self.CANONICAL_SOURCES.get(ont_type)
        if canonical_db:
            for entry in entries:
                if entry["database"] == canonical_db:
                    return entry
        return entries[0]

    def get_mapping_for_db(self, ont_type: str, database: str) -> Optional[dict]:
        """Get the mapping for an ontology type from a specific database."""
        entries = self.type_registry.get(ont_type, [])
        for entry in entries:
            if entry["database"] == database:
                return entry
        return None

    def _normalize_property(self, ont_property: str, entry: dict) -> str:
        """Try to find the full prefixed name for a property if given without prefix."""
        if ":" in ont_property:
            return ont_property
        # Try common prefixes
        for prefix in ("ent:", "schema:"):
            candidate = prefix + ont_property
            if (candidate in entry["columns"] or candidate in entry["fk_refs"]
                    or candidate in entry["joins"] or candidate in entry["enums"]):
                return candidate
        return ont_property

    def resolve_column(self, ont_type: str, ont_property: str,
                       database: str = None) -> Optional[dict]:
        """Resolve an ontology property to source column info for a given type.

        Returns dict with 'type' key: 'direct', 'fk_ref', or 'join'.
        """
        entries = self.type_registry.get(ont_type, [])
        for entry in entries:
            if database and entry["database"] != database:
                continue
            prop = self._normalize_property(ont_property, entry)
            if prop in entry["columns"]:
                return {
                    "database": entry["database"],
                    "table": entry["table"],
                    "column": entry["columns"][prop],
                    "type": "direct",
                }
            if prop in entry["fk_refs"]:
                return {
                    "database": entry["database"],
                    "table": entry["table"],
                    "ref": entry["fk_refs"][prop],
                    "type": "fk_ref",
                }
            if prop in entry["joins"]:
                return {
                    "database": entry["database"],
                    "table": entry["table"],
                    "join": entry["joins"][prop],
                    "type": "join",
                }
        return None

    def resolve_enum_value(self, ont_type: str, ont_property: str,
                           ontology_value: str, database: str = None) -> Any:
        """Reverse-map an ontology enum value to source system's native value(s).

        Returns:
            - A single source value (string) if exactly one source value maps to the ontology value
            - A list of source values if multiple map to the same ontology value
            - {"_not_in": [values]} if this is the _default mapping
            - The ontology_value unchanged if no mapping exists (pass-through)
        """
        entries = self.type_registry.get(ont_type, [])
        for entry in entries:
            if database and entry["database"] != database:
                continue
            prop = self._normalize_property(ont_property, entry)
            enum_map = entry["enums"].get(prop, {})
            if not enum_map:
                return ontology_value  # No mapping, pass through

            # Reverse lookup: find all source values that map to this ontology value
            source_values = [k for k, v in enum_map.items()
                             if v == ontology_value and k != "_default"]
            if source_values:
                return source_values if len(source_values) > 1 else source_values[0]

            # Check if this is the default value
            if enum_map.get("_default") == ontology_value:
                explicit = [k for k in enum_map if k != "_default"]
                return {"_not_in": explicit}

        return ontology_value

    def get_all_types(self) -> List[str]:
        """Return all registered ontology types."""
        return list(self.type_registry.keys())

    def get_filter_sql(self, filter_spec: list, db_alias: str = None) -> str:
        """Convert a filter spec to SQL WHERE clause fragment."""
        if not filter_spec:
            return ""
        clauses = []
        for f in filter_spec:
            col = f["column"]
            op = f["operator"]
            if op == "in_subquery":
                lookup = f["lookup"]
                where_parts = []
                for wcol, wvals in lookup["where"].items():
                    if isinstance(wvals, list):
                        quoted = ", ".join(f"'{v}'" for v in wvals)
                        where_parts.append(f"{wcol} IN ({quoted})")
                    else:
                        where_parts.append(f"{wcol} = '{wvals}'")
                where_clause = " AND ".join(where_parts)
                tbl = lookup["table"]
                if db_alias:
                    tbl = f"{db_alias}.{tbl}"
                clauses.append(
                    f"{col} IN (SELECT {lookup['matchColumn']} FROM {tbl} WHERE {where_clause})"
                )
            elif op == "eq":
                clauses.append(f"{col} = '{f['value']}'")
            elif op == "in":
                quoted = ", ".join(f"'{v}'" for v in f["value"])
                clauses.append(f"{col} IN ({quoted})")
        return " AND ".join(clauses)

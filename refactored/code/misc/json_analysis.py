import json
from typing import Dict
from collections import Counter

def extract_types(obj) -> Counter:
    """Recursively extract all @type values from a JSON object"""
    types = Counter()
    
    if isinstance(obj, dict):
        # Get type(s) from current object
        if "@type" in obj:
            if isinstance(obj["@type"], list):
                types.update(obj["@type"])
            else:
                types[obj["@type"]] += 1
                
        # Recursively check all values
        for value in obj.values():
            if isinstance(value, (dict, list)):
                types.update(extract_types(value))
                
    elif isinstance(obj, list):
        # Recursively check all items in list
        for item in obj:
            if isinstance(item, (dict, list)):
                types.update(extract_types(item))
                
    return types

def analyze_schema_types(filename: str) -> Counter:
    """Analyze a JSONL file containing schema.org markup and return all types found with counts"""
    all_types = Counter()
    
    with open(filename) as f:
        for line in f:
            items = line.strip().split('\t')
            if (len(items) < 2):
                continue
            js = json.loads(items[1])
            try:
                all_types.update(extract_types(js))
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON line: {line[:100]}...")
                continue
            
    return all_types

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python json_analysis.py <jsonl_file>")
        sys.exit(1)
        
    types = analyze_schema_types(sys.argv[1])
    print("\nFound types and counts:")
    for t, count in sorted(types.items()):
        print(f"- {t}: {count}")

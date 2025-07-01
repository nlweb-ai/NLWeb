import json
from typing import Any, Dict, List, Union


# ============= JSON Trimming Functions (from trim.py) =============

def listify(item):
    if not isinstance(item, list):
        return [item]
    else:
        return item
    
def jsonify(obj):
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            return obj
    return obj

def trim_json(obj):
    obj = jsonify(obj)
    objType = obj["@type"] if "@type" in obj else ["Thing"]
    if not isinstance(objType, list):
        objType = [objType]
    if (objType == ["Thing"]):
        return obj
    if ("Recipe" in objType):
        return trim_recipe(obj)
    if ("Movie" in objType or "TVSeries" in objType):
        return trim_movie(obj)
    return obj

def trim_json_hard(obj):
    obj = jsonify(obj)
    objType = obj["@type"] if "@type" in obj else ["Thing"]
    if not isinstance(objType, list):
        objType = [objType]
    if (objType == ["Thing"]):
        return obj
    if ("Recipe" in objType):
        return trim_recipe_hard(obj)
    if ("Movie" in objType or "TVSeries" in objType):
        return trim_movie(obj, hard=True)
    return obj
   

def trim_recipe(obj):
    obj = jsonify(obj)
    items = collateObjAttr(obj)
    js = {}
    skipAttrs = ["mainEntityOfPage", "publisher", "image", "datePublished", "dateModified", 
                 "author"]
    for attr in items.keys():
        if (attr in skipAttrs):
            continue
        js[attr] = items[attr]
    return js

def trim_recipe_hard(obj):
    items = collateObjAttr(obj)
    js = {}
    skipAttrs = ["mainEntityOfPage", "publisher", "image", "datePublished", "dateModified", "review",
                 "author", "recipeYield", "recipeInstructions", "nutrition"]
    for attr in items.keys():
        if (attr in skipAttrs):
            continue
        js[attr] = items[attr]
    return js



def trim_movie(obj, hard=False):
    items = collateObjAttr(obj)
    js = {}
    skipAttrs = ["mainEntityOfPage", "publisher", "image", "datePublished", "dateModified", "author", "trailer"]
    if (hard):
        skipAttrs.extend(["actor", "director", "creator", "review"])
    for attr in items.keys():
        if (attr in skipAttrs):
            continue
        elif (attr == "actor" or attr == "director" or attr == "creator"):
            if ("name" in items[attr]):
                if (attr not in js):
                    js[attr] = []
                js[attr].append(items[attr]["name"])
        elif (attr == "review"):
            items['review'] = []
            for review in items['review']:
                if ("reviewBody" in review):    
                    js[attr].append(review["reviewBody"])
        else:
            js[attr] = items[attr]
    return js

def collateObjAttr(obj):
    items = {}
    for attr in obj.keys():
        if (attr in items):
            items[attr].append(obj[attr])
        else:
            items[attr] = [obj[attr]]
    return items


# ============= JSON Merging Functions =============

def merge_json_objects(obj1: Union[str, Dict, List], obj2: Union[str, Dict, List]) -> Dict[str, Any]:
    """
    Merge two JSON objects according to specific rules.
    
    Args:
        obj1: First JSON object (can be string, dict, or list of dicts)
        obj2: Second JSON object (can be string, dict, or list of dicts)
        
    Returns:
        Merged dictionary combining data from both objects
    """
    # Parse strings to JSON if needed
    obj1 = jsonify(obj1)
    obj2 = jsonify(obj2)
    
    # Extract first dict if either is an array
    if isinstance(obj1, list):
        obj1 = obj1[0] if obj1 else {}
    if isinstance(obj2, list):
        obj2 = obj2[0] if obj2 else {}
    
    # Ensure both are dicts
    if not isinstance(obj1, dict):
        obj1 = {}
    if not isinstance(obj2, dict):
        obj2 = {}
    
    # Merge the dictionaries
    return _merge_dicts(obj1, obj2)


def _merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge two dictionaries.
    
    Rules:
    - If attribute exists in only one dict, copy it
    - If attribute exists in both:
        - If both values are dicts, recursively merge
        - If both values are lists, concatenate them
        - Otherwise, create array with both values
    """
    merged = {}
    
    # Get all unique keys from both dicts
    all_keys = set(dict1.keys()) | set(dict2.keys())
    
    for key in all_keys:
        val1 = dict1.get(key)
        val2 = dict2.get(key)
        
        # Case 1: Key only exists in dict1
        if key in dict1 and key not in dict2:
            merged[key] = val1
            
        # Case 2: Key only exists in dict2
        elif key not in dict1 and key in dict2:
            merged[key] = val2
            
        # Case 3: Key exists in both
        else:
            # Both are dicts - recursively merge
            if isinstance(val1, dict) and isinstance(val2, dict):
                merged[key] = _merge_dicts(val1, val2)
                
            # Both are lists - concatenate
            elif isinstance(val1, list) and isinstance(val2, list):
                merged[key] = val1 + val2
                
            # Different types or scalar values - create array
            else:
                # Handle None values
                if val1 is None and val2 is None:
                    merged[key] = None
                elif val1 is None:
                    merged[key] = val2
                elif val2 is None:
                    merged[key] = val1
                # If values are identical, keep single value
                elif val1 == val2:
                    merged[key] = val1
                else:
                    # Create array with both values
                    merged[key] = [val1, val2]
    
    return merged


def merge_json_array(json_array: List[Union[str, Dict]]) -> Dict[str, Any]:
    """
    Merge an array of JSON objects into a single object.
    
    Args:
        json_array: List of JSON objects (strings or dicts)
        
    Returns:
        Single merged dictionary
    """
    if not json_array:
        return {}
    
    # Start with the first object
    result = jsonify(json_array[0])
    if isinstance(result, list):
        result = result[0] if result else {}
    if not isinstance(result, dict):
        result = {}
    
    # Merge each subsequent object
    for obj in json_array[1:]:
        result = merge_json_objects(result, obj)
    
    return result


# ============= Testing Functions =============

def test_merge():
    """Test the JSON merging functionality"""
    
    # Test case 1: Simple merge
    obj1 = {
        "name": "Recipe 1",
        "cookTime": "30 min",
        "ingredients": ["salt", "pepper"]
    }
    obj2 = {
        "name": "Recipe 1",
        "prepTime": "10 min",
        "ingredients": ["oil", "garlic"]
    }
    
    print("Test 1 - Simple merge:")
    print("Object 1:", json.dumps(obj1, indent=2))
    print("Object 2:", json.dumps(obj2, indent=2))
    merged = merge_json_objects(obj1, obj2)
    print("Merged:", json.dumps(merged, indent=2))
    print()
    
    # Test case 2: Nested dicts
    obj1 = {
        "name": "Product",
        "details": {
            "price": 10,
            "color": "red"
        }
    }
    obj2 = {
        "name": "Product",
        "details": {
            "price": 12,
            "size": "large"
        }
    }
    
    print("Test 2 - Nested dicts:")
    print("Object 1:", json.dumps(obj1, indent=2))
    print("Object 2:", json.dumps(obj2, indent=2))
    merged = merge_json_objects(obj1, obj2)
    print("Merged:", json.dumps(merged, indent=2))
    print()
    
    # Test case 3: Array inputs
    obj1 = [{"name": "Item 1", "value": 100}]
    obj2 = {"name": "Item 1", "category": "electronics"}
    
    print("Test 3 - Array inputs:")
    print("Object 1:", json.dumps(obj1, indent=2))
    print("Object 2:", json.dumps(obj2, indent=2))
    merged = merge_json_objects(obj1, obj2)
    print("Merged:", json.dumps(merged, indent=2))


if __name__ == "__main__":
    test_merge()
"""JSON utilities for schema.org data processing.

Copied from NLWeb core/utils/json_utils.py to ensure consistent behavior.
"""

import json


def jsonify(obj):
    """Convert string to dict if needed."""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            return obj
    return obj


def collateObjAttr(obj):
    """Collate object attributes into a dict of lists."""
    items = {}
    for attr in obj.keys():
        if attr in items:
            items[attr].append(obj[attr])
        else:
            items[attr] = [obj[attr]]
    return items


def trim_recipe(obj):
    """Trim recipe JSON to essential fields."""
    obj = jsonify(obj)
    items = collateObjAttr(obj)
    js = {}
    skipAttrs = ["mainEntityOfPage", "publisher", "image", "datePublished", "dateModified",
                 "author"]
    for attr in items.keys():
        if attr in skipAttrs:
            continue
        js[attr] = items[attr]
    return js


def trim_movie(obj, hard=False):
    """Trim movie/TV JSON to essential fields."""
    items = collateObjAttr(obj)
    js = {}
    skipAttrs = ["mainEntityOfPage", "publisher", "image", "datePublished", "dateModified", "author", "trailer"]
    if hard:
        skipAttrs.extend(["actor", "director", "creator", "review"])
    for attr in items.keys():
        if attr in skipAttrs:
            continue
        elif attr in ("actor", "director", "creator"):
            if "name" in items[attr]:
                if attr not in js:
                    js[attr] = []
                js[attr].append(items[attr]["name"])
        elif attr == "review":
            items['review'] = []
            for review in items['review']:
                if "reviewBody" in review:
                    js[attr].append(review["reviewBody"])
        else:
            js[attr] = items[attr]
    return js


def trim_json(obj):
    """Trim schema.org JSON to remove unnecessary fields.

    This matches NLWeb's trim_json function exactly.
    """
    obj = jsonify(obj)
    if not isinstance(obj, dict):
        return obj

    objType = obj.get("@type", ["Thing"])
    if not isinstance(objType, list):
        objType = [objType]

    if objType == ["Thing"]:
        return obj
    if "Recipe" in objType:
        return trim_recipe(obj)
    if "Movie" in objType or "TVSeries" in objType:
        return trim_movie(obj)

    return obj

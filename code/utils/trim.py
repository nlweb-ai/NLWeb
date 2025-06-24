import json

def listify (item):
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
                 "author", "copyrightHolder", "copyrightYear", "thumbnail", "transcript", "video"]
    for attr in items.keys():
        if (attr in skipAttrs):
            continue
        js[attr] = items[attr]
    return js

def trim_recipe_hard(obj):
    items = collateObjAttr(obj)
    js = {}
    skipAttrs = ["mainEntityOfPage", "publisher", "image", "datePublished", "dateModified", "review", "transcript", "video",
                 "author", "recipeYield", "recipeInstructions", "nutrition", "copyrightHolder", "copyrightYear"]
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

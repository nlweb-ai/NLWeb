
recipe_sites = ['seriouseats', 'hebbarskitchen', 'latam_recipes',
                'woksoflife', 'cheftariq',  'spruce', 'nytimes']

all_sites = recipe_sites + ["imdb", "npr podcasts", "neurips", "backcountry", "tripadvisor"]

def siteToItemType(site):
    # For any single site's deployment, this can stay in code. But for the
    # multi-tenant, it should move to the database
    namespace = "http://nlweb.ai/base"
    et = "Item"
    if site == "imdb":
        et = "Movie"
    elif site in recipe_sites:
        et = "Recipe"
    elif site == "npr podcasts":
        et = "Thing"
    elif site == "neurips":
        et = "Paper"
    elif site == "backcountry":
        et = "Outdoor Gear"
    elif site == "tripadvisor":
        et = "Restaurant"
    elif site == "zillow":
        et = "RealEstate"
    else:
        et = "Items"
    return f"{{{namespace}}}{et}"
    

def itemTypeToSite(item_type):
    # this is used to route queries that this site cannot answer,
    # but some other site can answer. Needs to be generalized.
    sites = []
    for site in all_sites:
        if siteToItemType(site) == item_type:
            sites.append(site)
    return sites
    

def visibleUrlLink(url):
    from urllib.parse import urlparse

def visibleUrl(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc.replace('www.', '')

def get_param(query_params, param_name, param_type=str, default_value=None):
    value = query_params.get(param_name, default_value)
    if (value is not None and len(value) == 1):
        value = value[0]
        if param_type == str:
            if value is None:
                return ""
            return value    
        elif param_type == int:
            if value is None:
                return 0
            return int(value)
        elif param_type == float:
            if value is None:
                return 0.0
            return float(value) 
        elif param_type == bool:
            if value is None:
                return False
            return value.lower() == "true"
        elif param_type == list:
            if value is None:
                return []
            return [item.strip() for item in value.strip('[]').split(',') if item.strip()]
        else:
            raise ValueError(f"Unsupported parameter type: {param_type}")
    return default_value

def log(message):
    print(message)
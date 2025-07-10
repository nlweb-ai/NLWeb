
from core.config import CONFIG

recipe_sites = ['seriouseats', 'hebbarskitchen', 'latam_recipes',
                'woksoflife', 'cheftariq',  'spruce', 'nytimes']

all_sites = recipe_sites + ["imdb", "npr podcasts", "neurips", "backcountry", "tripadvisor", "DataCommons"]

def siteToItemType(site):
    # Get item type from configuration
    namespace = "http://nlweb.ai/base"
    
    # Try to get from configuration
    try:
        site_config = CONFIG.get_site_config(site.lower())
        if site_config and site_config.item_types:
            # Return the first item type for the site
            return f"{{{namespace}}}{site_config.item_types[0]}"
    except:
        pass
    
    # Default to Item if not found in configuration
    return f"{{{namespace}}}Item"
    

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
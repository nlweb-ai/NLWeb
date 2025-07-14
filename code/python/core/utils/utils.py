
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
    parsed = urlparse(url)
    return f"<a href='{url}'>{parsed.netloc.replace('www.', '')}</a>"

def visibleUrl(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc.replace('www.', '')

def get_param(query_params, param_name, param_type=str, default_value=None):
    value = query_params.get(param_name, default_value)
    if (value is not None):
        if param_type == str:
            if isinstance(value, list):
                return value[0] if value else ""
            return value
        elif param_type == int:
            return int(value)
        elif param_type == float:
            return float(value) 
        elif param_type == bool:
            if isinstance(value, list):
                return value[0].lower() == "true"
            return value.lower() == "true"
        elif param_type == list:
            if isinstance(value, list):
                return value
            return [item.strip() for item in value.strip('[]').split(',') if item.strip()]
        else:
            raise ValueError(f"Unsupported parameter type: {param_type}")
    return default_value

def log(message):
    print(message)
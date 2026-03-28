
from core.config import CONFIG
import json
from urllib.parse import quote


def sanitize_log(value):
    """Sanitize value for safe logging by removing newlines and control characters."""
    if isinstance(value, str):
        return value.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    return value

recipe_sites = ['seriouseats', 'hebbarskitchen', 'latam_recipes',
                'woksoflife', 'cheftariq',  'spruce', 'nytimes']

all_sites = recipe_sites + ["imdb", "npr podcasts", "neurips", "backcountry", "tripadvisor", "DataCommons"]

def build_nlweb_gateway_url(site_url, query, site_type=None):
    """
    Build a complete URL to the NLWeb gateway with query parameters.

    Args:
        site_url: The site domain (will be cleaned of https:// if present)
        query: The search query
        site_type: Optional site type (e.g., 'ShopifyStore', 'Shopify')

    Returns:
        Complete URL string to the gateway
    """
    # Use nlweb_gateway from config
    gateway = CONFIG.nlweb_gateway
    # Ensure gateway doesn't have trailing slash
    gateway = gateway.rstrip('/')
    # Add https:// if not present
    if not gateway.startswith(('http://', 'https://')):
        gateway = f"https://{gateway}"

    # Remove https:// or http:// from site_url if present
    clean_site_url = site_url
    if clean_site_url.startswith('https://'):
        clean_site_url = clean_site_url[8:]
    elif clean_site_url.startswith('http://'):
        clean_site_url = clean_site_url[7:]

    params = []
    params.append(f"site={quote(clean_site_url)}")

    # Add the query
    if query:
        params.append(f"query={quote(query)}")

    # Check if it's a Shopify site and add db parameter
    if site_type in ['ShopifyStore', 'Shopify'] or 'shopify' in site_url.lower():
        params.append("db=shopify")

    # Add tool parameter to go directly to search
    params.append("tool=search")

    # Construct the full URL
    return f"{gateway}/?{'&'.join(params)}"

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

llm_recording_file = None
recording_llm_calls = None

def set_recording_llm_calls (file_str):
    global recording_llm_calls
    recording_llm_calls = file_str

def record_llm_call (ans_str, prompt, query):
    global llm_recording_file
    if (recording_llm_calls):
        if (not llm_recording_file):
            llm_recording_file = open(recording_llm_calls, "w")
        ans_str["prompt"] = prompt
        ans_str["query"] = query
        llm_recording_file.write(json.dumps(ans_str) + "\n")
        llm_recording_file.flush()

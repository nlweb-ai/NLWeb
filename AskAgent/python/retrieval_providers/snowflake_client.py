import httpx
import json
from core.config import CONFIG, RetrievalProviderConfig
from core.retriever import RetrievalClientBase
from typing import Any, Dict, List, Optional, Tuple, Union
from retrieval_providers.utils import snowflake

class SnowflakeCortexSearchClient(RetrievalClientBase):
    """
    Adapts the Snowflake Cortex Search API to the VectorDBClientInterface.

    See: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/query-cortex-search-service#rest-api
    """
    _cfg = None

    def __init__(self, endpoint_name: Optional[str] = None):
        super().__init__()  # Initialize the base class with caching
        self._cfg = CONFIG.retrieval_endpoints[endpoint_name]

    async def deleted_documents_by_site(self, site: str, **kwargs) -> int:
        raise NotImplementedError("Not implemented yet, requires translation to a DELETE statement in Snowflake")

    async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs) -> int:
        raise NotImplementedError("Incremental updates not implemented here yet, see snowflake.sql and docs/Snowflake.md for how to bulk upload datasets")

    async def search(self, query: str, site: Union[str, List[str]], num_results: int=50, query_params: Optional[Dict[str, Any]] = None, **kwargs) -> List[List[str]]:
        return await search(query, site=site, top_n=num_results, cfg=self._cfg)

    async def search_by_url(self, url: str, **kwargs) -> Optional[List[str]]:
        return await search(query="a", url=url, top_n=1, cfg=self._cfg)

    async def search_all_sites(self, query: str, num_results: int = 50, **kwargs) -> List[List[str]]:
        return await search(query, top_n=num_results, cfg=self._cfg)
    
    async def get_sites(self, **kwargs) -> List[str]:
        """
        Get a list of unique site names from the Snowflake Cortex Search Service.
        
        Returns:
            List[str]: Sorted list of unique site names
        """
        return await get_unique_sites(cfg=self._cfg)


def get_cortex_search_service(cfg: RetrievalProviderConfig) -> Tuple[str,str,str]:
    """
    Retrieve the Cortex Search Service (database, schema, service) to use from the configuration, or raise an error.
    """
    if not cfg:
        raise snowflake.ConfigurationError("Unable to determine Snowflake configuration")
    index_name = cfg.index_name
    if not index_name:
        raise snowflake.ConfigurationError("Unable to determine Snowflake Cortex Search Service, is SNOWFLAKE_CORTEX_SEARCH_SERVICE set?")
    parts = index_name.split(".")
    if len(parts) != 3:
        raise snowflake.ConfigurationError(f"Invalid SNOWFLAKE_CORTEX_SEARCH_SERVICE, expected format:<database>.<schema>.<service>, got {index_name}")
    return (parts[0], parts[1], parts[2])

async def search(query: str, site: str|List[str]|None=None, url: str|None=None, top_n: int=10, cfg: RetrievalProviderConfig|None=None) -> dict:
    """
    Send a search request to a Cortex Search Service which has the columns
    URL and SCHEMA.

    See: https://docs.snowflake.com/developer-guide/snowflake-rest-api/reference/cortex-search-service
    """

    # Filtering language:
    # https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/query-cortex-search-service#filter-syntax
    filter = None
    if url and not site:
        filter = {"@eq": {"url": url}}
    elif not url and site:
        filter = {"@eq": {"site": site}}
    elif url and site:
        filter = {
            "@and": [
                {"@eq": {"url": url}},
                {"@eq": {"site": site}},
            ]
        }

    (database, schema, service) = get_cortex_search_service(cfg)
    async with httpx.AsyncClient() as client:
        response =  await client.post(
            snowflake.get_account_url(cfg) + f"/api/v2/databases/{database}/schemas/{schema}/cortex-search-services/{service}:query",
            json={
                "query": query,
                "limit": max(1, min(top_n, 1000)),
                "columns": ["url", "site", "schema_json"],
                "filter": filter,
            },
            headers={
                    "Authorization": f"Bearer {snowflake.get_pat(cfg)}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
            },
            timeout=60,
        )
        if response.status_code == 400:
            raise Exception(response.json())
        response.raise_for_status()
        results = response.json().get("results", [])
        return list(map(_process_result, results))

def _process_result(r: Dict[str, str]) -> List[str]:
    url = r.get("url", "")
    schema_json = r.get("schema_json", "{}")
    name = _name_from_schema_json(schema_json)
    site = r.get("site", "")
    return [url, schema_json, name, site]

def _name_from_schema_json(schema_json: str) -> str:
    try:
        return json.loads(schema_json).get("name", "")
    except Exception as e:
        return ""

async def get_unique_sites(cfg: RetrievalProviderConfig) -> List[str]:
    """
    Get unique site values from the Snowflake Cortex Search Service using CORTEX_SEARCH_DATA_SCAN.
    
    Args:
        cfg: The Snowflake configuration
        
    Returns:
        List[str]: Sorted list of unique site names
    """
    if not cfg:
        raise snowflake.ConfigurationError("Unable to determine Snowflake configuration")
    
    # Get the service configuration
    (database, schema, service) = get_cortex_search_service(cfg)
    
    # Use CORTEX_SEARCH_DATA_SCAN as recommended by sfc-gh-ashankar
    query = f"SELECT DISTINCT site FROM TABLE(CORTEX_SEARCH_DATA_SCAN(SERVICE_NAME=>'{database}.{schema}.{service}')) ORDER BY site"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            snowflake.get_account_url(cfg) + "/api/v2/statements",
            json={
                "statement": query,
                "timeout": 60,
            },
            headers={
                "Authorization": f"Bearer {snowflake.get_pat(cfg)}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=60,
        )
        
        if response.status_code == 400:
            raise Exception(response.json())
        response.raise_for_status()
        
        # Use concise list comprehension as recommended by sfc-gh-ashankar
        return [x[0] for x in response.json().get("data", [])]

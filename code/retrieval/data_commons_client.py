import httpx
import json
from typing import Any, Dict, List, Optional, Union
from utils.logging_config_helper import get_configured_logger
from config.config import CONFIG
from utils.logger import LogLevel

logger = get_configured_logger("data_commons_client")

_BASE_URL = 'https://nl.datacommons.org/nodejs/query'
_POINT_PARAMS = f'allCharts=1&mode=toolformer_rig&idx=base_uae_mem'

class DataCommonsSearchClient:
    """
    Adapts the DC NL API to the VectorDBClientInterface.
    """
    _cfg = None

    def __init__(self, endpoint_name: Optional[str] = None):
        self._cfg = CONFIG.retrieval_endpoints[endpoint_name]

    async def deleted_documents_by_site(self, site: str, **kwargs) -> int:
        raise NotImplementedError("Deletion not implemented yet")

    async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs) -> int:
        raise NotImplementedError("Incremental updates not implemented yet")

    async def search(self, query: str, site: Union[str, List[str]], num_results: int=50, **kwargs) -> List[List[str]]:
        query = query.strip().replace(' ', '+')
        try:
            async with httpx.AsyncClient() as client:
                response =  await client.get(
                    f'{_BASE_URL}/?&q={query}&key={self._cfg.api_key}&{_POINT_PARAMS}',
                    timeout=60,
                )
                response.raise_for_status()
                results = []

                for c in response.json().get('charts', []):
                    ctype = c.get('type')
                    if ctype == 'HIGHLIGHT':
                        continue
                    results.append([
                        c.get('dcUrl', ''), json.dumps(c), c.get('title', ''), "",
                    ])
                return results
        except Exception as e:
            logger.exception(f"Error in DataCommonsSearchClient.search")
            logger.log_with_context(
                LogLevel.ERROR,
                "Data Commons Search retrieval failed",
                {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }
            )
            raise

    async def search_by_url(self, url: str, **kwargs) -> Optional[List[str]]:
        raise NotImplementedError("Search by url not implemented yet")

    async def search_all_sites(self, query: str, num_results: int = 50, **kwargs) -> List[List[str]]:
        return await self.search(query, site="", num_results=num_results, **kwargs)
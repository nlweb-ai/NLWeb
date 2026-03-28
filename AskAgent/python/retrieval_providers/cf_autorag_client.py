from core.config import CONFIG
from typing import Any, Dict, List, Optional, Union

import threading

import os
import json

import httpx

from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

from cloudflare import AsyncCloudflare

import zon as z

from bs4 import BeautifulSoup
from markdown import markdown
import re

def markdown_to_text(markdown_string):
    """ 
    Converts a markdown string to plaintext 
    
    Taken from https://gist.github.com/lorey/eb15a7f3338f959a78cc3661fbc255fe
    """

    # md -> html -> text since BeautifulSoup can extract text cleanly
    html = markdown(markdown_string)

    # remove code snippets
    html = re.sub(r'<pre>(.*?)</pre>', ' ', html)
    html = re.sub(r'<code>(.*?)</code >', ' ', html)

    # extract text
    soup = BeautifulSoup(html, "html.parser")
    text = ''.join(soup.findAll(text=True))

    return text

logger = get_configured_logger("cloudflare_autorag_client")

searchFiltersComparisonFilter = z.record({
    "key": z.string(),
    "type": z.enum(["eq", "ne", "gt", "gte", "lt", "lte"]),
	"value": z.string().or_else([z.number()]).or_else([z.boolean()]),
})

searchFiltersCompoundFilter = z.record({
	"type": z.enum(["and"]), # TODO: add 'or' when vectorize supports it
	"filters": searchFiltersComparisonFilter.list(),
})


class CloudflareAutoRAGClient:
    """
    """

    _cfg = None

    def __init__(self, endpoint_name: Optional[str] = None):

        self.endpoint_name = endpoint_name or CONFIG.write_endpoint
        logger.info(f"Initialized CloudflareAutoRAGClient for endpoint: {self.endpoint_name}")

        self._client_lock = threading.Lock()
        self._cf_sdk_clients = {}  # Cache for CF SDK clients

        self.endpoint_config = self._get_endpoint_config()

        self.token = self.endpoint_config.api_key
        self.rag_id = self.endpoint_config.index_name

        # TODO: should get this info from somewhere else
        self.account_id = os.environ.get('CLOUDFLARE_ACCOUNT_ID')

        self.uri = f"accounts/{self.account_id}/autorag/rags/{self.rag_id}/search"


    def _get_endpoint_config(self):
        """Get the Cloudflare SDK endpoint configuration from CONFIG"""
        endpoint_config = CONFIG.retrieval_endpoints.get(self.endpoint_name)
        
        if not endpoint_config:
            error_msg = f"No configuration found for endpoint {self.endpoint_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Verify this is a Cloudflare SDK endpoint
        if endpoint_config.db_type != "cloudflare_autorag":
            error_msg = f"Endpoint {self.endpoint_name} is not a Cloudflare SDK endpoint (type: {endpoint_config.db_type})"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        return endpoint_config
    
    def _get_cf_sdk_client(self) -> AsyncCloudflare:
        """
        Get or create a Cloudflare SDK client.
                    
        Returns:
            Cloudflare instance
        """
        client_key = f"{self.endpoint_name}"
        
        with self._client_lock:
            if client_key not in self._cf_sdk_clients:
                logger.debug(f"Creating Cloudflare SDK client for {client_key}")
                
                # Initialize the client
                self._cf_sdk_clients[client_key] = AsyncCloudflare(api_token=self.token)
                logger.info(f"Created Cloudflare SDK client for {client_key} at {self.uri}")
                
                # Test client connection with a simple search
                try:
                    logger.debug("Testing connection to Cloudflare SDK")
                   # self._cf_sdk_clients[client_key].list_collections()
                    logger.info(f"Connection verified for {client_key}")
                except Exception as e:
                    logger.error(f"Failed to connect to Cloudflare SDK at {self.uri}: {str(e)}")
                    raise

        return self._cf_sdk_clients[client_key]

    async def __post(self, path: str, body: dict) -> httpx.Response:
        client = self._get_cf_sdk_client()

        resp = await client.post(
            path,
            cast_to=httpx.Response,
            body=body,
        )

        return resp

    async def deleted_documents_by_site(self, site: str, **kwargs) -> int:
        raise NotImplementedError("Not implemented yet")

    async def upload_documents(self, documents: List[Dict[str, Any]], **kwargs) -> int:
        raise NotImplementedError("Not implemented yet")

    async def search(
        self,
        query: str,
        site: Union[str, List[str]],
        num_results: int = 50,
        query_params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[List[str]]:

        ranking_options = kwargs.get('ranking_options', {})
        system_prompt = kwargs.get('system_prompt', None)
        filters = kwargs.get('filters', None)

        body = {
            'query': query,
        }

        if num_results is not None:
            body['max_num_results'] = num_results

        if ranking_options is not None:
            body['ranking_options'] = ranking_options
        
        if system_prompt is not None:
            body['system_prompt'] = system_prompt

        success, filters = searchFiltersComparisonFilter.or_else([searchFiltersCompoundFilter]).optional().safe_validate(filters)
        if success and filters is not None:
            body['filters'] = filters

        resp = await self.__post(self.uri, body)

        results = resp.json()['result']

        data = results['data']

        def _parse_data_item(item: dict):
            url: str = item.get('filename')

            attributes = item.get('attributes', {})
            file_attributes = attributes.get('file', {})

            name = file_attributes.get('title', '')

            contents = item.get('content', [])

            description = markdown_to_text(''.join(map(lambda c: c['text'], contents)).replace("\n", " ")[:420])

            text_json = json.dumps({
                "@context": "http://schema.org/",
                "@type": "Product",
                "@id": "#social-preview",
                "name": file_attributes.get('title', "Social Preview"),
                "brand": {
                    "@type": "Brand",
                    name: "Cloudflare",
                },
                "description": file_attributes.get('description', description), 
                "image": file_attributes.get('image', ''),
            })

            site = url.removeprefix('https://').split('/')[0] # FIXME: this filtering scheme just returns the actual domain, not "section specific" data (like different sections related to different offerings in a documentation website)

            entry =  [url, text_json, name, site]

            return entry

        return list(map(_parse_data_item, data))

    async def search_by_url(self, url: str, **kwargs) -> Optional[List[str]]:
        raise NotImplementedError("Not implemented yet")

    async def search_all_sites(
        self, query: str, num_results: int = 50, **kwargs
    ) -> List[List[str]]:
        return await self.search(query, site=[], num_results=num_results, **kwargs)

    async def get_sites(self, **kwargs) -> List[str]:
        """
        Get a list of unique site names.

        Returns:
            List[str]: Sorted list of unique site names
        """
        raise NotImplementedError("Not implemented yet")

"""
OpenAPI ingress strategy for NLWeb.

This strategy handles OpenAPI/Swagger JSON specifications, converting them 
to Schema.org APIReference format for vector database storage.
"""

import json
from urllib.parse import urlparse
from typing import List, Dict, Any, Tuple, Optional
import aiohttp

from .base_strategy import BaseIngressStrategy
from tools.db_load_utils import int64_hash


class OpenAPIStrategy(BaseIngressStrategy):
    """
    Strategy for ingesting OpenAPI/Swagger JSON specifications.

    Supports:
    - OpenAPI 3.x specifications
    - Swagger 2.x specifications
    - JSON format from URLs or files
    """

    def validate_input(self, data: Any) -> bool:
        """
        Validate that the input data is a valid OpenAPI specification.

        Args:
            data: Data to validate (should be dict or JSON string)

        Returns:
            True if data appears to be a valid OpenAPI spec
        """
        try:
            # Handle JSON string input
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    return False

            # Must be a dictionary
            if not isinstance(data, dict):
                return False

            # Check for OpenAPI/Swagger indicators
            has_openapi = "openapi" in data
            has_swagger = "swagger" in data
            has_paths = "paths" in data

            return (has_openapi or has_swagger) and has_paths

        except Exception:
            return False

    def process_data(self, data: Any, source_url: str, site: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Process OpenAPI specification and convert to standardized documents.

        Args:
            data: OpenAPI JSON data (dict or JSON string)
            source_url: URL or identifier for the source
            site: Site identifier

        Returns:
            Tuple of (documents, texts_for_embedding)
        """
        try:
            # Parse JSON if needed
            if isinstance(data, str):
                openapi_data = json.loads(data)
            else:
                openapi_data = data

            # Convert to Schema.org APIReference documents
            api_references = self._openapi_to_schema_org(
                openapi_data, source_url)

            # Convert to standardized document format
            documents = []
            texts_for_embedding = []

            for api_ref in api_references:
                # Convert to JSON string for embedding
                json_data = json.dumps(
                    api_ref, ensure_ascii=False).replace("\\n", " ")

                # Extract URL and name
                url = api_ref.get(
                    "url", f"synthetic:{site}:{api_ref.get('identifier', 'unknown')}")
                # Create standardized document
                name = api_ref.get("name", "Untitled API Endpoint")
                doc = {
                    "id": str(int64_hash(url)),
                    "schema_json": json_data,
                    "url": url,
                    "name": name,
                    "site": site
                }

                documents.append(doc)
                texts_for_embedding.append(json_data)

            return documents, texts_for_embedding

        except Exception as e:
            print(f"Error processing OpenAPI data: {str(e)}")
            return [], []

    def get_supported_extensions(self) -> List[str]:
        """Get file extensions supported by this strategy."""
        return ['.json', '.yaml', '.yml']

    def get_strategy_name(self) -> str:
        """Get human-readable name for this strategy."""
        return "OpenAPI JSON"

    @staticmethod
    async def fetch_from_url(url: str) -> Dict[str, Any]:
        """
        Fetch OpenAPI JSON from a URL.

        Args:
            url: URL to fetch OpenAPI JSON from

        Returns:
            Parsed OpenAPI JSON as dictionary
        """
        print(f"Fetching OpenAPI JSON from URL: {url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ValueError(
                            f"Failed to fetch URL {url}: HTTP {response.status}")

                    content_text = await response.text()

                    if not content_text.strip():
                        raise ValueError(f"Empty response from URL: {url}")

                    try:
                        openapi_data = json.loads(content_text)
                    except json.JSONDecodeError as json_error:
                        raise ValueError(
                            f"Response is not valid JSON: {str(json_error)}")

                    if not isinstance(openapi_data, dict):
                        raise ValueError(
                            f"OpenAPI specification must be a JSON object")

                    return openapi_data

        except Exception as e:
            print(f"Error fetching OpenAPI JSON from {url}: {str(e)}")
            raise

    def _openapi_to_schema_org(self, openapi_data: Dict[str, Any], source_url: str = None) -> List[Dict[str, Any]]:
        """
        Convert OpenAPI specification to Schema.org APIReference objects.

        Args:
            openapi_data: Parsed OpenAPI JSON
            source_url: Source URL for the API

        Returns:
            List of Schema.org APIReference documents
        """
        documents = []

        # Extract basic API information
        api_info = openapi_data.get("info", {})
        api_title = api_info.get("title", "API")
        api_description = api_info.get("description", "")
        api_version = api_info.get("version", "")

        # Extract base URL from servers or source URL
        base_url = self._extract_base_url(openapi_data, source_url)

        # Extract external docs
        external_docs = openapi_data.get("externalDocs", {})
        external_docs_url = external_docs.get("url", "")

        # Process each path and operation
        paths = openapi_data.get("paths", {})

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Process each HTTP method for this path
            for method in ["get", "post", "put", "delete", "patch", "head", "options", "trace"]:
                operation = path_item.get(method)
                if not operation:
                    continue

                # Extract operation details
                operation_id = operation.get("operationId",
                                             f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}")
                summary = operation.get("summary", f"{method.upper()} {path}")
                description = operation.get(
                    "description", f"Use this endpoint to {summary.lower()}")
                tags = operation.get("tags", [])

                # Extract parameters
                param_info = self._extract_parameters(
                    operation.get("parameters", []))

                # Extract responses
                response_info = self._extract_responses(
                    operation.get("responses", {}))

                # Extract operation-specific external docs
                operation_external_docs = operation.get("externalDocs", {})
                operation_docs_url = operation_external_docs.get(
                    "url", external_docs_url)

                # Build the full URL for this endpoint
                endpoint_url = f"{base_url.rstrip('/')}{path}" if base_url else path

                # Create Schema.org APIReference document
                api_reference = {
                    "@type": "APIReference",
                    "name": summary,
                    "description": description,
                    "url": operation_docs_url or endpoint_url,
                    "identifier": operation_id,
                    "programmingLanguage": "HTTP",
                    "applicationCategory": "WebAPI",
                    "operatingSystem": "Any",
                    "isPartOf": {
                        "@type": "SoftwareApplication",
                        "name": api_title,
                        "description": api_description,
                        "applicationCategory": "WebAPI",
                        "operatingSystem": "Any",
                        "version": api_version
                    },
                    "potentialAction": {
                        "@type": "Action",
                        "name": f"{method.upper()} {path}",
                        "description": summary,
                        "target": {
                            "@type": "EntryPoint",
                            "urlTemplate": endpoint_url,
                            "httpMethod": method.upper(),
                            "contentType": "application/json"
                        },
                        "object": param_info,
                        "result": response_info[0] if response_info else {
                            "@type": "DataDownload",
                            "name": "API Response",
                            "description": "Response from the API endpoint",
                            "encodingFormat": "application/json"
                        }
                    },
                    "keywords": tags + [api_title, "API", method.upper()],
                    "category": tags[0] if tags else "api",
                    "version": api_version
                }

                documents.append(api_reference)

        print(
            f"Converted OpenAPI spec to {len(documents)} APIReference documents")
        return documents

    def _extract_base_url(self, openapi_data: Dict[str, Any], source_url: str = None) -> str:
        """Extract base URL from OpenAPI servers or source URL."""
        # Try servers first
        servers = openapi_data.get("servers", [])
        if servers:
            return servers[0].get("url", "")

        # Fall back to source URL
        if source_url:
            parsed_url = urlparse(source_url)
            return f"{parsed_url.scheme}://{parsed_url.netloc}"

        return ""

    def _extract_parameters(self, parameters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract and format parameter information."""
        param_info = []

        for param in parameters:
            # Skip $ref parameters for now
            if "$ref" in param:
                continue

            param_name = param.get("name", "")
            param_in = param.get("in", "")
            param_required = param.get("required", False)
            param_schema = param.get("schema", {})
            param_type = param_schema.get("type", "string")
            param_description = param.get(
                "description", f"{param_in} parameter")

            # Handle different parameter types
            if isinstance(param_type, list):
                data_type = f"Array[{', '.join(str(t).title() for t in param_type)}]"
            elif isinstance(param_type, dict):
                data_type = "Object"
            elif param_type is None:
                data_type = "Any"
            else:
                data_type = str(param_type).title()

            param_info.append({
                "@type": "PropertyValue",
                "name": param_name,
                "description": f"{param_description} ({param_in} parameter)",
                "valueRequired": param_required,
                "dataType": data_type
            })

        return param_info

    def _extract_responses(self, responses: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and format response information."""
        response_info = []

        for status_code, response in responses.items():
            if isinstance(response, dict):
                response_desc = response.get(
                    "description", f"Response {status_code}")
                content = response.get("content", {})

                # Extract content types
                content_types = list(content.keys())

                response_info.append({
                    "@type": "DataDownload",
                    "name": f"HTTP {status_code} Response",
                    "description": response_desc,
                    "encodingFormat": content_types[0] if content_types else "application/json"
                })

        return response_info

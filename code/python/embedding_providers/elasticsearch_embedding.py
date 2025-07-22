# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Elasticsearch embedding implementation.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

from typing import List, Optional, Union, Dict

from elasticsearch import AsyncElasticsearch, NotFoundError
from core.config import CONFIG

from misc.logger.logging_config_helper import get_configured_logger, LogLevel
logger = get_configured_logger("elasticsearch_embedding")

class ElasticsearchEmbedding:
    def __init__(self,  endpoint_name: Optional[str] = None):
        self.endpoint_name = endpoint_name or CONFIG.preferred_embedding_provider
        embedding_config = CONFIG.embedding_providers[self.endpoint_name]
        self._model = embedding_config.model
        if self._model is None:
            raise ValueError("The Elasticsearch embedding model is empty (inference endpoint)")
        
        # Initialize model task type cache
        self._model_task_type = None
        
        # If config (settings) not provided
        self._config = embedding_config.config
        if self._config is None:
            raise ValueError("The Elasticsearch embedding config is empty")
        
        # Check for required settings for Elasticsearch inference endpoint
        if self._config["service"] is None:
            raise ValueError("The Elasticsearch embedding config.service is empty")
        if self._config["service_settings"] is None:
            raise ValueError("The Elasticsearch embedding config.service_settings is empty")
        if self._config["service_settings"]["model_id"] is None:
            raise ValueError("The Elasticsearch embedding config.service_settings.model_id is empty")
        
        # Check for Elasticsearch authentication
        if embedding_config.api_key is None:
            raise ValueError("The ELASTICSEARCH_API_KEY environment variable is empty")
        if embedding_config.endpoint is None:
            raise ValueError("The ELASTICSEARCH_URL environment variable is empty")
        
        self._client = self._initialize_client(embedding_config.endpoint, embedding_config.api_key)
        
    def _initialize_client(self, endpoint:str, api_key:str)-> AsyncElasticsearch:
        """Initialize the Elasticsearch client"""
        try:
            logger.info(f"Initializing Elasticsearch embedding client for endpoint: {self.endpoint_name}")
            return AsyncElasticsearch(hosts=endpoint, api_key=api_key)
        except Exception as e:
            logger.exception(f"Failed to initialize Elasticsearch embedding client: {str(e)}")
            raise
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def close(self):
        """Close the Elasticsearch client connection"""
        if self._client:
            try:
                await self._client.close()
                logger.debug("Elasticsearch client connection closed")
            except Exception as e:
                logger.warning(f"Error closing Elasticsearch client: {str(e)}")
            finally:
                self._client = None
    
    async def get_model_task_type(self)-> str:
        """
        Get the model task type for the configured inference endpoint (self._model).
        """
        if self._model_task_type is not None:
            return self._model_task_type
        
        try:
            logger.debug(f"Check if the inference endpoint {self._model} exists in Elasticsearch")
            response = await self._client.inference.get(inference_id=self._model)
        except NotFoundError:
            logger.debug(f"The inference endpoint {self._model} does not exist. We create a new one.")
            try:
                # We need to create the inference endpoint
                response = await self._client.options(
                    request_timeout=180 # Elasticseatch needs some time if the model is not deployed
                ).inference.put(
                    inference_id=self._model,
                    body={
                        "service": self._config["service"],
                        "service_settings": self._config["service_settings"]
                    }
                )
            except Exception as e:
                logger.exception(f"Failed to create the inference endpoint {self._model}: {str(e)}")
                raise 
        try:
            self._model_task_type = response['endpoints'][0]['task_type']
            return self._model_task_type
        except KeyError:
            logger.exception(f"Failed to retrieve task type from response: {response}")
            raise ValueError("Invalid response format from Elasticsearch inference endpoint")
        
    async def get_embeddings(
        self,
        text: str,
        model: Optional[str] = None,
        timeout: float = 30.0
    ) -> Union[List[float], Dict[str,float]]:
        """
        Generate an embedding for a single text using Elasticsearch Inference API.
        
        Args:
            text: The text to embed
            model: Optional model ID to use, defaults to provider's configured model
            timeout: Maximum time to wait for the embedding response in seconds
            
        Returns:
            List of floats representing the embedding vector
            
        Raises:
            ValueError: If text is empty or None
            Exception: For Elasticsearch API errors
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty or None")
            
        try:
            task_type = await self.get_model_task_type()
            response = await self._client.options(
                request_timeout=timeout
            ).inference.inference(
                inference_id=model or self._model,
                task_type=task_type,
                body={ "input": text }
            )
            return response[task_type][0]['embedding']
        except Exception as e:
            logger.exception(f"Failed to get embeddings for text: {str(e)}")
            raise
    
    async def get_batch_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        timeout: float = 60.0
    ) -> List[Union[List[float], Dict[str,float]]]:
        """
        Generate embeddings for multiple texts using Elasticsearch Inference API.
        
        Args:
            texts: List of texts to embed
            model: Optional model ID to use, defaults to provider's configured model
            timeout: Maximum time to wait for the batch embedding response in seconds
            
        Returns:
            List of embedding vectors, each a list of floats
            
        Raises:
            ValueError: If texts is empty or contains empty strings
            Exception: For Elasticsearch API errors
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")
        
            
        try:
            task_type = await self.get_model_task_type()
            response = await self._client.options(
                request_timeout=timeout
            ).inference.inference(
                inference_id=model or self._model,
                task_type=task_type,
                body={
                    "input": texts
                }
            )
            embeddings = []
            for each_embedding in response[task_type]:
                embeddings.append(each_embedding['embedding'])
            return embeddings
        except Exception as e:
            logger.exception(f"Failed to get batch embeddings: {str(e)}")
            raise

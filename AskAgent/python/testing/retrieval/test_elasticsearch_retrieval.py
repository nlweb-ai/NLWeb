import pytest
import os
import json
from pathlib import Path
from typing import List, Dict, Any

from embedding_providers.elasticsearch_embedding import ElasticsearchEmbedding
from core.config import CONFIG
from retrieval_providers.elasticsearch_client import ElasticsearchClient

# Skip all tests in this module if ELASTICSEARCH_URL is not set
if not os.getenv("ELASTICSEARCH_URL"):
    pytest.skip("ELASTICSEARCH_URL environment variable is required", allow_module_level=True)

# Skip all tests in this module if ELASTICSEARCH_API_KEY is not set
if not os.getenv("ELASTICSEARCH_API_KEY"):
    pytest.skip("ELASTICSEARCH_API_KEY environment variable is required", allow_module_level=True)

current_dir = os.path.dirname(os.path.abspath(__file__))
# Load the Elasticsearch retrieval configuration for testing
CONFIG.load_retrieval_config(current_dir + '/test_elasticsearch_retrieval.yaml')
# Load the Elasticsearch embedding configuration for testing (used for search)
CONFIG.load_embedding_config(current_dir + '/test_elasticsearch_embedding.yaml')

@pytest.fixture
async def elasticsearch_retrieval():
    es_client = ElasticsearchClient()
    yield es_client
    # Ensure proper cleanup after each test
    await es_client.close()

def get_scifi_movies()->List[Dict[str, Any]]:
    documents=[]
    file= Path(current_dir + "/100_scifi_movies_e5_embeddings.ndjson")
    
    if not file.exists():
        return documents

    for line in file.read_text().splitlines():
        doc= json.loads(line)
        documents.append(doc)

    return documents

@pytest.mark.order(1)
def test_elasticsearch_retrieval_initialization(elasticsearch_retrieval: ElasticsearchClient):
    assert elasticsearch_retrieval is not None
    assert elasticsearch_retrieval.endpoint_name is not None
    assert elasticsearch_retrieval.endpoint_config is not None

@pytest.mark.order(2)
async def test_create_index_if_not_exists(elasticsearch_retrieval: ElasticsearchClient):
    result = await elasticsearch_retrieval.create_index_if_not_exists()
    assert result is True

@pytest.mark.order(3)
async def test_upload_documents(elasticsearch_retrieval: ElasticsearchClient):
    documents = get_scifi_movies()
    result = await elasticsearch_retrieval.upload_documents(documents)
    assert result == 100

@pytest.mark.order(4)
async def test_search_documents(elasticsearch_retrieval: ElasticsearchClient):
    query = "Movies about space travel and aliens"
    results = await elasticsearch_retrieval.search(query=query, site="Wikipedia")
    assert results is not None
    assert len(results) == 50
    assert "Alien: Romulus" in results[0]

@pytest.mark.order(5)
async def test_search_by_url(elasticsearch_retrieval: ElasticsearchClient):
    url = "https://en.wikipedia.org/wiki/Alien:_Romulus"
    results = await elasticsearch_retrieval.search_by_url(url=url)
    assert results is not None
    assert url in results
    assert "Alien: Romulus" in results

@pytest.mark.order(6)
async def test_search_all_sites(elasticsearch_retrieval: ElasticsearchClient):
    query = "Movies about Gorilla"
    results = await elasticsearch_retrieval.search_all_sites(query=query)
    assert results is not None
    assert len(results) == 50

@pytest.mark.order(7)
async def test_get_sites(elasticsearch_retrieval: ElasticsearchClient):
    results = await elasticsearch_retrieval.get_sites()
    assert results is not None
    assert len(results) == 2
    assert results == ["Wikipedia", "Wikipedia2"]

@pytest.mark.order(8)
async def test_delete_documents_by_site(elasticsearch_retrieval: ElasticsearchClient):
    """Delete documents by site Wikipedia (90 documents)"""
    result = await elasticsearch_retrieval.delete_documents_by_site(site="Wikipedia")
    assert result == 90

@pytest.mark.order(9)
async def test_delete_index(elasticsearch_retrieval: ElasticsearchClient):
    result = await elasticsearch_retrieval.delete_index()
    assert result is True
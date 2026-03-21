import pytest
import os

from core.config import CONFIG
from embedding_providers.elasticsearch_embedding import ElasticsearchEmbedding

# Skip all tests in this module if ELASTICSEARCH_URL is not set
if not os.getenv("ELASTICSEARCH_URL"):
    pytest.skip("ELASTICSEARCH_URL environment variable is required", allow_module_level=True)

# Skip all tests in this module if ELASTICSEARCH_API_KEY is not set
if not os.getenv("ELASTICSEARCH_API_KEY"):
    pytest.skip("ELASTICSEARCH_API_KEY environment variable is required", allow_module_level=True)

current_dir = os.path.dirname(os.path.abspath(__file__))
# Load the Elasticsearch retrieval configuration for testing
CONFIG.load_embedding_config(current_dir + '/test_elasticsearch_embedding.yaml')

@pytest.fixture
async def elasticsearch_embedding():
    embedding = ElasticsearchEmbedding()
    yield embedding
    # Ensure proper cleanup after each test
    await embedding.close()

async def test_elasticsearch_embedding_initialization(elasticsearch_embedding: ElasticsearchEmbedding):
    assert elasticsearch_embedding is not None
    assert elasticsearch_embedding._client is not None
    assert elasticsearch_embedding._model is not None
    assert elasticsearch_embedding._config is not None

async def test_elasticsearch_embedding_model_task_type(elasticsearch_embedding: ElasticsearchEmbedding):
    task_type = await elasticsearch_embedding.get_model_task_type()
    assert task_type is not None
    assert isinstance(task_type, str)
    assert task_type in ["text_embedding", "sparse_embedding", "rerank"]

async def test_elasticsearch_get_embeddings(elasticsearch_embedding: ElasticsearchEmbedding):
    result = await elasticsearch_embedding.get_embeddings("test text")
    assert result is not None
    assert isinstance(result, list)

async def test_elasticsearch_get_batch_embeddings(elasticsearch_embedding: ElasticsearchEmbedding):
    texts = ["test text 1", "test text 2"]
    result = await elasticsearch_embedding.get_batch_embeddings(texts)
    assert result is not None
    assert isinstance(result, list)
    assert len(result) == len(texts)
    for each_embedding in result:
        assert isinstance(each_embedding, list)
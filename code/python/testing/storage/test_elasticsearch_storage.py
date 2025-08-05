import pytest
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any

from core.config import CONFIG
from elasticsearch import AsyncElasticsearch
from storage_providers.elasticsearch_storage import ElasticsearchStorageProvider

# Skip all tests in this module if ELASTICSEARCH_URL is not set
if not os.getenv("ELASTICSEARCH_URL"):
    pytest.skip("ELASTICSEARCH_URL environment variable is required", allow_module_level=True)

# Skip all tests in this module if ELASTICSEARCH_API_KEY is not set
if not os.getenv("ELASTICSEARCH_API_KEY"):
    pytest.skip("ELASTICSEARCH_API_KEY environment variable is required", allow_module_level=True)

current_dir = os.path.dirname(os.path.abspath(__file__))
# Load the Elasticsearch storage configuration for testing
CONFIG.load_conversation_storage_config(current_dir + '/test_elasticsearch_storage.yaml')
# Load the Elasticsearch embedding configuration for testing (used for search)
CONFIG.load_embedding_config(current_dir + '/test_elasticsearch_embedding.yaml')

@pytest.fixture
async def elasticsearch_storage():
    es_client = ElasticsearchStorageProvider(CONFIG.conversation_storage)
    yield es_client
    # Ensure proper cleanup after each test
    await es_client.close()

@pytest.fixture(scope="module", autouse=True)
async def run_after_tests():
    # Setup code (optional)
    yield
    # Remove the Elasticsearch index after all tests
    es_client = ElasticsearchStorageProvider(CONFIG.conversation_storage)
    await delete_index(await es_client._get_es_client())
    await es_client.close()
    

def get_conversations()->List[Dict[str, Any]]:
    documents=[]
    file= Path(current_dir + "/conversations.ndjson")
    
    if not file.exists():
        return documents

    for line in file.read_text().splitlines():
        if not line.strip():
            continue
        doc= json.loads(line)
        documents.append(doc)

    return documents

async def refresh_es_indices(es: AsyncElasticsearch):
    """Refresh the Elasticsearch indices to ensure all changes are visible."""
    await es.indices.refresh(index=CONFIG.conversation_storage.collection_name)
  
async def delete_index(es: AsyncElasticsearch):
    """Delete the Elasticsearch index if it exists."""
    try:
        await es.indices.delete(index=CONFIG.conversation_storage.collection_name, ignore_unavailable=True)
    except Exception as e:
        print(f"Error deleting index: {e}")

@pytest.mark.order(1)
def test_elasticsearch_storage_initialization(elasticsearch_storage: ElasticsearchStorageProvider):
    assert elasticsearch_storage is not None
    assert elasticsearch_storage.index_name == CONFIG.conversation_storage.collection_name

@pytest.mark.order(2)
async def test_add_conversations(elasticsearch_storage: ElasticsearchStorageProvider):
    conversations = get_conversations()
    conversations_stored = 0
    for conversation in conversations:
        user_id = conversation.get("user_id", "test_user")
        site = conversation.get("site", "test_site")
        thread_id = conversation.get("thread_id", None)
        user_prompt = conversation.get("user_prompt", "")
        response = conversation.get("response", "")
        
        result = await elasticsearch_storage.add_conversation(
            user_id=user_id,
            site=site,
            thread_id=thread_id,
            user_prompt=user_prompt,
            response=response
        )
        conversations_stored += 1

        assert result is not None
        assert result.user_id == user_id
        assert result.site == site
        assert result.thread_id == thread_id
        assert result.user_prompt == user_prompt
        assert result.response == response
        assert result.conversation_id is not None

    await refresh_es_indices(elasticsearch_storage.es_client)
    assert conversations_stored == len(conversations)

@pytest.mark.order(3)
async def test_get_conversation_thread(elasticsearch_storage: ElasticsearchStorageProvider):
    thread_id= "f712c573-cc63-45eb-94f2-42b64cfd1486"
    threads = await elasticsearch_storage.get_conversation_thread(
        thread_id=thread_id
    )

    assert len(threads) == 2
    for thread in threads:
        assert thread.thread_id == thread_id

@pytest.mark.order(4)
async def test_get_conversation_thread_with_user_id(elasticsearch_storage: ElasticsearchStorageProvider):
    thread_id= "781985f6-2ca9-4502-a2d4-66ac5fe66c20"
    user_id= "bf7a861d-a9e3-4144-8ba6-22aa56e93350"
    threads = await elasticsearch_storage.get_conversation_thread(
        thread_id=thread_id,
        user_id=user_id
    )

    assert len(threads) == 2
    for thread in threads:
        assert thread.thread_id == thread_id
        assert thread.user_id == user_id

@pytest.mark.order(5)
async def test_get_recent_conversations(elasticsearch_storage: ElasticsearchStorageProvider):
    user_id= "7854ff06-82d6-40a1-8a21-e447160a98a6"
    site= "example.com"
    threads = await elasticsearch_storage.get_recent_conversations(
        user_id=user_id,
        site=site,
        limit=3
    )

    assert len(threads) == 2
    assert threads[0]["id"] == "a8df02c1-f94e-4022-86ba-3e9fb13b4ac9"
    assert len(threads[0]["conversations"]) == 1
    assert threads[1]["id"] == "f712c573-cc63-45eb-94f2-42b64cfd1486"
    assert len(threads[1]["conversations"]) == 2
    assert threads[1]["conversations"][0]["user_prompt"] == "How do I boil an egg perfectly?"
    assert threads[1]["conversations"][1]["user_prompt"] == "What spices go well with chicken?"

    for thread in threads:
        assert thread["site"] == site

@pytest.mark.order(6)
async def test_search_conversations(elasticsearch_storage: ElasticsearchStorageProvider):
    results = await elasticsearch_storage.search_conversations(
        query="How to cook gnocchi?",
        limit=3
    )

    assert len(results) == 3
    assert results[0].user_prompt == "How is gnocchi traditionally made?"

@pytest.mark.order(7)
async def test_search_conversations_with_user_id(elasticsearch_storage: ElasticsearchStorageProvider):
    user_id = "f9056bbe-110f-4c02-b6fd-049300952397"
    results = await elasticsearch_storage.search_conversations(
        query="How to cook gnocchi?",
        user_id=user_id,
        limit=3
    )

    assert len(results) == 3
    assert results[0].user_prompt == "How is gnocchi traditionally made?"
    for result in results:
        assert result.user_id == user_id

@pytest.mark.order(8)
async def test_search_conversations_with_user_id_and_site(elasticsearch_storage: ElasticsearchStorageProvider):
    user_id= "f9056bbe-110f-4c02-b6fd-049300952397"
    site= "example.it"
    results = await elasticsearch_storage.search_conversations(
        query="How to cook gnocchi?",
        user_id=user_id,
        site=site,
        limit=3
    )

    assert len(results) == 3
    assert results[0].user_prompt == "How is gnocchi traditionally made?"
    for result in results:
        assert result.site == site
        assert result.user_id == user_id


@pytest.mark.order(9)
async def test_delete_conversations_with_id(elasticsearch_storage: ElasticsearchStorageProvider):
    # Search for conversations to get the conversation_id (generated at runtime)
    client =  await elasticsearch_storage._get_es_client()
    result = await client.search(
        index=elasticsearch_storage.index_name,
        query={
            "bool": {
                "must": [
                    {"match": {"thread_id": "a8df02c1-f94e-4022-86ba-3e9fb13b4ac9"}}
                ]
            }
        }
    )
    conversation_id = result['hits']['hits'][0]['_source']['conversation_id']
    success = await elasticsearch_storage.delete_conversation(
        conversation_id=conversation_id
    )
    assert success is True

    failure = await elasticsearch_storage.delete_conversation(
        conversation_id="xxxx-xxxx-xxxx-xxxx"
    )
    assert failure is False

@pytest.mark.order(10)
async def test_delete_conversations_with_id_and_user_id(elasticsearch_storage: ElasticsearchStorageProvider):
    # Search for conversations to get the conversation_id (generated at runtime)
    client =  await elasticsearch_storage._get_es_client()
    user_id="9f5e1a5c-88c9-4dde-abc6-c7aff77119cc"
    result = await client.search(
        index=elasticsearch_storage.index_name,
        query={
            "bool": {
                "must": [
                    {"match": {"thread_id": "0433bc75-1bb5-4bbc-a25f-7f06207676b6"}},
                    {"match": {"user_id": user_id}}
                ]
            }
        }
    )
    conversation_id = result['hits']['hits'][0]['_source']['conversation_id']

    success = await elasticsearch_storage.delete_conversation(
        conversation_id=conversation_id,
        user_id=user_id
    )
    assert success is True

    failure = await elasticsearch_storage.delete_conversation(
        conversation_id="xxxx-xxxx-xxxx-xxxx",
        user_id=user_id
    )
    assert failure is False
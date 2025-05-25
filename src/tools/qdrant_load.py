import os
import sys
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from db_create_utils import documentsFromCSVLine

# To use a local persistent instance for prototyping,
# set database_path to a local directory
QDRANT_PATH = "/path/to/some/directory"

# To connect to a Qdrant server, set the `QDRANT_URL` and optionally `QDRANT_API_KEY`.
# > docker run -p 6333:6333 qdrant/qdrant
QDRANT_URL = None
QDRANT_API_KEY = None

COLLECTION_NAME = "nlweb_collection"
EMBEDDING_SIZE = 1536

EMBEDDINGS_PATH_SMALL = "/Users/anush/Desktop/NLWeb/data/sites/embeddings/small"

# Initialize Qdrant client
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, path=QDRANT_PATH)


def recreate_collection(collection_name, vector_size):
    """Recreate a collection in Qdrant"""
    if client.collection_exists(collection_name):
        print(f"Dropping existing collection '{collection_name}'")
        client.delete_collection(collection_name)

    print(f"Creating collection '{collection_name}' with vector size {vector_size}")
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def get_documents_from_csv(csv_file_path, site):
    """Reads and parses documents from a CSV-style text file"""
    documents = []
    with open(csv_file_path, "r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                try:
                    docs = documentsFromCSVLine(line, site)
                    documents.extend(docs)
                except ValueError as e:
                    print(f"Skipping row due to error: {str(e)}")
    return documents


def get_uuid_from_id(text_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, text_id))


def upload_documents_to_qdrant(documents, collection_name):
    """Upload documents to Qdrant"""
    points = []
    for doc in documents:
        if "embedding" not in doc or not doc["embedding"]:
            continue
        point_id = get_uuid_from_id(doc["id"])
        vector = doc["embedding"]
        payload = {
            "url": doc.get("url"),
            "name": doc.get("name"),
            "site": doc.get("site"),
            "schema_json": doc.get("schema_json"),
        }
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))

    if points:
        client.upsert(collection_name=collection_name, points=points)
        print(f"Uploaded {len(points)} points to Qdrant collection '{collection_name}'")


def upload_data_from_csv(csv_file_path, site, collection_name):
    documents = get_documents_from_csv(csv_file_path, site)
    print(f"Found {len(documents)} documents in {site}")
    upload_documents_to_qdrant(documents, collection_name)
    return len(documents)


def main():
    complete_reload = len(sys.argv) <= 1 or sys.argv[1].lower() == "reload=true"

    if complete_reload:
        recreate_collection(COLLECTION_NAME, EMBEDDING_SIZE)

    embedding_paths = [EMBEDDINGS_PATH_SMALL]
    total_documents = 0

    for path in embedding_paths:
        csv_files = [
            f.replace(".txt", "") for f in os.listdir(path) if f.endswith(".txt")
        ]
        for csv_file in csv_files:
            print(f"\nProcessing file: {csv_file}")
            csv_file_path = os.path.join(path, f"{csv_file}.txt")
            try:
                documents_added = upload_data_from_csv(
                    csv_file_path, csv_file, COLLECTION_NAME
                )
                total_documents += documents_added
            except Exception as e:
                print(f"Error processing file {csv_file}: {e}")

    print(f"\nData processing completed. Total documents added: {total_documents}")


if __name__ == "__main__":
    main()

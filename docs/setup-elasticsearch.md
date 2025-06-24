# Elasticsearch Setup

To configure [Elasticsearch](https://www.elastic.co/elasticsearch) for use with NLWeb, you'll need to set a few environment variables or update your configuration.

## Connecting to an Elasticsearch Server

To connect to a running Elasticsearch server, set the following environment variables:

* `ELASTICSEARCH_URL`: The URL of your Elasticsearch instance (e.g., `http://localhost:9200`).
* `ELASTICSEARCH_API_KEY`: The Elasticsearch API key

If you don't have already an instance of Elasticsearch, you can [start a free trial](https://cloud.elastic.co/registration?elektra=nlweb) using Elastic Cloud or Serverless.
Moreover, you can install Elasticsearch locally using the [start-local](https://github.com/elastic/start-local) installer.

Open a terminal and run the following command:

```bash
curl -fsSL https://elastic.co/start-local | sh
```

This will install Elasticsearch and [Kibana](https://www.elastic.co/kibana) locally.
ELasticsearch will be executed on `localhost:9200` with the credentials stored in the `elastic-start-local/.env`
file, including the API key.


## Configuring Elasticsearch as vector database

The Elasticsearch configuration is available in the [config/config_retrieval.yaml](../code/config/config_retrieval.yaml) file.

```yaml
  elasticsearch:
    # Elasticsearch endpoint (localhost or remote URL with Elastic Cloud/Serverless)
    api_endpoint_env: ELASTICSEARCH_URL
    # Authentication credentials
    api_key_env: ELASTICSEARCH_API_KEY
    # Index name to search in
    index_name: nlweb_embeddings
    # Database type
    db_type: elasticsearch
    # Vector properties
    vector_type:
      type: dense_vector
```

You can change the configuration, e.g. changing the `index_name`. You can customize the `vector_type`
property using [dense_vector](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/dense-vector) or [sparse_vector](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/sparse-vector) type.

You can optimize the Elasticsearch vector storage with many options. For instance, you can quantize vectors using a single byte. You can specify `int8_hnsw` as `index_options` type, to use the 1 byte quantization in Elasticsearch, as follows:

```yaml
  elasticsearch:
    # ...
    vector_type:
      type: dense_vector
      index: true
      index_options:
        type: "int8_hnsw"
```

This reduces the memory footprint by 75% (or 4x) at the cost of some accuracy.

You can optionally specify the vector dimension (`dims`) in the configuration, although it's not required—Elasticsearch will automatically use the dimension of the first embedding it receives.

To learn more about configuring Elasticsearch as a vector database, we recommend checking out the following articles:

- [Scalar quantization 101](https://www.elastic.co/search-labs/blog/scalar-quantization-101)
- [RaBitQ binary quantization 101](https://www.elastic.co/search-labs/blog/rabitq-explainer-101)
- [How to implement Better Binary Quantization (BBQ) into your use case and why you should](https://www.elastic.co/search-labs/blog/bbq-implementation-into-use-case)
- [Mapping embeddings to Elasticsearch field types: semantic_text, dense_vector, sparse_vector](https://www.elastic.co/search-labs/blog/mapping-embeddings-to-elasticsearch-field-types)
- [Semantic Text: Simpler, better, leaner, stronger](https://www.elastic.co/search-labs/blog/semantic-text-ga)
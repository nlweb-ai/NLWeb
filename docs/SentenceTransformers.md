# Sentence Transformers Embedding Framework

The `sentence_transformers` framework provides a unified interface for working with embedding and reranker models. It is used by the `db_load` tool to compute vector embeddings when inserting documents into the database.

We use the `all-MiniLM-L6-v2` model as the default embedding model, which offers a strong balance between speed and embedding quality for general-purpose use. The resulting vectors are 384-dimensional.

A wide range of models is supported through the framework. See the full list at [sentence-transformers on Hugging Face](https://huggingface.co/sentence-transformers).

**Note**: Embedding vector size is defined by the model. If you change models or providers and encounter a vector size mismatch error, you may need to delete your existing embeddings database and regenerate it using the `db_load` tool.


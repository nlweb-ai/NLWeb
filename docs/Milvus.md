# Milvus Configuration Guide

## Environment Setup

Set the environment variables `MILVUS_ENDPOINT` and `MILVUS_TOKEN`(Optional) to configure your Milvus connection.

## Connection Options

- **Milvus Lite (Local Development)**: Setting the `MILVUS_ENDPOINT` as a local file, e.g.`./milvus.db`, is the most convenient method, as it automatically utilizes [Milvus Lite](https://milvus.io/docs/milvus_lite.md) to store all data in this file. This is ideal for development, testing, or smaller datasets.

- **Milvus Server (Self-Hosted)**: If you have a large scale of data, you can set up a more performant [Milvus server](https://milvus.io/docs/install_standalone-docker-compose.md) on Docker or Kubernetes. In this setup, please use the server URI, e.g., `http://localhost:19530`, as your `MILVUS_ENDPOINT`, and the `MILVUS_TOKEN` is optional.

- **Zilliz Cloud (Managed Service)**: If you want to use Zilliz Cloud, the fully managed cloud service for Milvus, adjust the `MILVUS_ENDPOINT` and `MILVUS_TOKEN`, which correspond to the [Public Endpoint and API key](https://docs.zilliz.com/docs/byoc/quick-start#free-cluster-details) in Zilliz Cloud.

## Additional Resources

- [Milvus Documentation](https://milvus.io/docs)
- [Zilliz Cloud Documentation](https://docs.zilliz.com/)
# Qdrant 设置

qdrant：
  # 要连接到 Qdrant 服务器，请设置 `QDRANT_URL` 和 （可选 `QDRANT_API_KEY`）。
  # > docker run -p 6333：6333 qdrant/qdrant
  # QDRANT_URL=“http://localhost:6333”
  api_endpoint_env：QDRANT_URL
  api_key_env：QDRANT_API_KEY

  # 要使用本地持久性实例进行原型设计，
  # 将 database_path 设置为本地目录
  database_path：“”

  # 设置要用作的集合的名称 `index_name`
  index_name：nlweb_collection
  db_type： qdrant
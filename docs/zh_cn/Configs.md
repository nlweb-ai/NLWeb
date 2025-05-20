# 配置文件

此存储库中的 NLWeb 实现支持许多
不同的向量存储、LLM 和嵌入提供程序。
名为 config 的目录包含所有配置。

我们有以下配置文件（都是 yaml）：

- llm ：指定可用的 LLMS 和环境变量
        其中可以找到他们的端点、API 密钥等。这些
        可能需要适当修改。顶线 
        <code>preferred_provider</code> 指定了哪个 LLM 应该
        作为默认值。一些 llm 调用需要稍微
        更好的模型和一些像排名调用更喜欢的模型
        更轻的型号。这是使用 high 和 low 参数指定的

- embedding：与 LLMS 类似，指定提供程序、端点等。注意
         嵌入是检索不可或缺的一部分，并且相同
         需要使用 embedding 来创建 vector store
         并从中检索。

- retrieval：指定可用的向量存储。如上变量
         指定终端节点、API 密钥等。此时，只有一个
         stores 的将来，我们将查询所有可用的商店。
         我们不假设后端是 vector store。我们位于
         添加 Restful 向量存储的过程，其中
         将使一个 NLWeb 实例能够将另一个实例视为其后端。

         We do assume that the vector store will return a list of the database
         items encoded as json objects, preferably in a schema.org schema.

- nlweb：指定可用于数据的 JSON 文件的位置
         上传。在以下情况下，还将提示与聊天机器人一起使用
         通过 MCP 与他们通信
         
- Web 服务器：大多数变量都是不言自明的。服务器可以
         在开发或生产模式下运行。在开发模式下，
         查询参数可以覆盖配置中的内容以进行检索
         和 LLM
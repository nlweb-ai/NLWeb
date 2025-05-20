# 检索

 此时，只有一个
stores 的将来，我们将查询所有可用的商店。
我们不假设后端是 vector store。 

我们确实假设 vector store 将返回数据库的列表
编码为 JSON 对象的项，最好采用 schema.org 架构。

我们正在添加 Restful 向量存储，它
将使一个 NLWeb 实例能够将另一个实例视为其后端。

检索的重大改进如下。考虑
像 “homes cost less than 500k which would be suitable
适合一个有 2 个小孩和一只大狗的家庭”。数据库
的项目（房地产列表）将具有结构化字段，例如
价格。最好将其转换为 
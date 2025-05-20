# NLWeb Rest API

此时，NLWeb 在端点 /ask 上支持 2 个 API
和 /mcp 的两者的参数相同，大多数功能也是如此。
/mcp 端点以 MCP 客户端可以使用的格式返回答案。
/mcp 端点还支持核心 MCP 方法 （list_tools、 list_prompts、
call_tool、get_prompt）。


在包含的实现中，没有服务器端状态。
因此，到目前为止，对话的上下文必须作为
请求。如下所述，有多种方法可以执行此作。

ask / mcp 所需的参数是：
- query：自然语言的当前查询

以下是可选参数
- site：与后端的某个数据子集相对应的 token。例如，后端可能会
          支持多个站点，每个站点都有一个仅限于其内容的对话界面。这
          参数可用于指定站点 
- prev：以前查询的逗号分隔列表。在大多数情况下，脱离上下文的查询可以是
           由此构建。 
- decontextualized_query：整个脱离上下文的查询。如果这可用，则无需去语境化
        在服务器端完成
- streaming：默认为 true。要关闭流式处理，请指定值 0 或 false
- query_id：如果未指定，则自动生成 1 个
- 模式：值为 List （default）、summarize 和 generate
    - list ：返回后端与查询最相关的热门匹配项列表
    - summarize：汇总列表并显示摘要，并返回列表
    - generate：更像传统的 RAG，其中生成列表并进行一次或多次调用
        被要求 LLM 尝试回答用户的问题。 

返回值是一个 json 对象，其中包含以下字段：
- query_id
- 零个或多个 result 属性
- 一个结果数组（很快将移动到更丰富的结构，从 schema.org 的 ItemList 开始），每个结果都有
     - 网址
     - 名字
     - 网站
     - 得分
     - 描述（由 LLM 生成）
     - schema_object （来自数据存储的项，以 JSON 编码）


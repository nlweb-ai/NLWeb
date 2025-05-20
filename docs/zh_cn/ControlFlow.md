
# 控制流，编程模型

对话流的标志之一（与传统搜索相比）是
控制流是用户所说的内容或用户所知道的内容的函数。为
例如，如果在旅游网站上，用户请求景点或酒店，而
位置不清楚，首先向用户询问位置是有意义的。
但是，如果用户请求电影，则请求位置没有意义。

更通用的聊天机器人 （ChatGPT/Copilot/Claude/Gemini） 可能会回来问这样的问题
澄清性问题，具体取决于系统提示符等，但行为
通常不如网站想要的可靠。

传统编程为程序员提供了极其细粒度的控制，但需要
程序员对如何执行任务的每一步进行编码。LLM 包含巨大的
与任务相关的背景知识/情报的数量，但程序员可以
只能通过“提示”来控制 LLM，这很笨拙且不可预测。

让网站设计人员在程序控制与模型控制之间选择平衡非常重要
流、UI 等。这也允许网站在涉及交易行为的下层漏斗交互中使用更受约束的（传统）设计模式，这是无法承受的
自然语言固有的歧义。

NLWeb 使用两者的灵活混合，Python 代码进行大量小的、非常精确的调用
分配给 LLM，但保留对显示内容的最终控制权。每个请求都涉及
以数十次 LLM 调用的顺序（例如，“此查询是否引用前面提到的
items“、”查询是否引用某个地点“等）。我们称之为 'Mixed Mode Programming'。

更具体地说，我们在这里说明了这种方法的一个示例。 

<!-- The document on post ranking explains more. -->

## 所需信息

对于某些类型（例如 RealEstate），了解位置、
价格范围等。这是通过以下提示完成的。

  <RealEstate>
    <Prompt ref="RequiredInfoPrompt">
      <promptString>
        回答用户的查询需要位置和价格范围。
        您是否从中获得了此信息
        query 或之前的 queries 或上下文或内存？
        用户的查询是：{request.query}。前面的查询是：{request.previousQueries}。
      </promptString>
      <returnStruc>
        {
          “required_info_found”： “对或错”，
          “user_question”： “向用户询问所需信息的问题”
        }
      </returnStruc>
    </Prompt>
  </RealEstate>


 



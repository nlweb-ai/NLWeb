# 通过更改提示来修改行为

在处理来自用户的单个查询的过程中，NLWeb 会进行大量
LLM 需要许多不同类型的任务。这些包括：

- “前”步骤，例如，
  * 分析查询是否与网站相关
  * 从查询历史记录构造一个去上下文化的查询
  * 确定查询是否提到了应该提交到内存的内容
- 排名
- '发布'。后处理步骤是可选的 
  * 创建结果摘要
  * 尝试使用排名靠前的结果来回答用户的问题（这更接近传统的 RAG）

用于这些调用的提示位于 file site_types.xml 中。系统的行为可以修改
通过更改这些提示。

 下面给出的是一个示例提示：

<Thing>
   <Prompt ref="DetectMemoryRequestPrompt">
      <promptString>
        分析用户的以下陈述。
        用户是否要求您记住，这可能不仅与此查询相关，还与将来的查询相关？
        如果是这样，用户要求我们记住什么？
        用户应该明确要求您记住一些内容以备将来查询，
        而不仅仅是表达对当前查询的要求。
        用户的查询为：{request.rawQuery}。
      </promptString>
      <returnStruc>
        {
          “is_memory_request”： “对或错”，
          “memory_request”： “内存请求，如果有”
        }
      </returnStruc>
    </Prompt>

 ...

</Thing>


每个 <tag>Prompt</tag> 都由一个 'ref' 属性标识，该属性用于
通过调用 LLM 来构造标签的代码。promptString <tag></tag>
遵循模板化结构。每个字符串都包含占位符/变量
（如 {request.query}、{site.itemType} 等）动态填充
在执行期间。提示通常首先建立有关
用户的查询和正在搜索的网站，后跟具体说明
用于分析或转换查询或对候选项目进行排名
在查询的上下文中。LLM 调用始终使用结构化输出
并且所需的输出结构位于 <tag>returnStruc</tag> 中
本文档末尾给出了允许的占位符列表。

上面的提示非常通用，旨在用于所有类型的
项目。但是，大多数网站处理的项目类型非常有限
并且可以设计更具体（因此性能更好）的提示
对于这些。例如，如果我们知道用户正在查找配方，
我们可以使用以下更具体的提示。

  <Recipe>
    <Prompt ref="DetectMemoryRequestPrompt">
      <promptString>
        分析用户的以下陈述。
        用户是否要求您记住可能相关的饮食限制
        不仅针对此查询，还针对未来的查询？例如，用户可能会说
        他们是素食主义者或遵守犹太洁食或清真食品，或指定过敏。
        如果是这样，用户要求我们记住什么？
        用户应该明确要求您记住一些内容以备将来查询，
        而不仅仅是表达对当前查询的要求。
        用户的查询为：{request.rawQuery}。
      </promptString>
      <returnStruc>
        {
          “is_memory_request”： “对或错”，
          “memory_request”： “内存请求，如果有”
        }
      </returnStruc>
    </Prompt>
  </Recipe>

在 schema.org 层次结构中，<tag>Recipe</tag> 位于 <tag></tag> 类中的 Thing 下
层次结构，因此当确定用户正在查找 <tag>Recipe</tag> 时
将使用此提示。

提示还可用于更改与
每个项目。例如，默认排名提示为：


   <Prompt ref="RankingPrompt">
      <promptString>
        Assign a score between 0 and 100 to the following item
        based on how relevant it is to the user's question. Use your knowledge from other sources, about the item, to make a judgement. 
        If the score is above 50, provide a short description of the item highlighting the relevance to the user's question, without mentioning the user's question.
        Provide an explanation of the relevance of the item to the user's question, without mentioning the user's question or the score or explicitly mentioning the term relevance.
        If the score is below 75, in the description, include the reason why it is still relevant.
        The user's question is: \"{request.query}\". The item's description in schema.org format is \"{item.description}\".
      </promptString>
      <returnStruc>
        {
          "score": "integer between 0 and 100",
          "description": "short description of the item"
        }
      </returnStruc>
   </Prompt>

对项目进行星级评分（并且每个项目的 json 都包含星级评分）的网站可能需要
将该评级纳入排名。一种方法是使用 <tag>promptString</tag> ，该
要求 LLM 将此因素考虑在内。例如，

   <Prompt ref="RankingPrompt">
      <promptString>
        Assign a score between 0 and 100 to the following item
        based on how relevant it is to the user's question. Incorporate the aggregateRating for the item into your
	score. Items with higher ratings should be given a higher score.
	...
        The user's question is: \"{request.query}\". The item's description in schema.org format is \"{item.description}\".
      </promptString>
      <returnStruc>
        {
          "score": "integer between 0 and 100",
          "description": "short description of the item"
        }
      </returnStruc>
   </Prompt>

同样，也可以更改描述。例如。

 <Recipe>
   <Prompt ref="RankingPrompt">
      <promptString>
        为以下项目分配一个介于 0 和 100 之间的分数
        基于它与用户问题的相关性。包括项目的简短描述，重点放在
	teim 与用户查询的相关性。此外，还包括营养价值的突出方面
	这个食谱。
        用户的问题是：\“{request.query}\”。schema.org 格式的项的描述为 \“{item.description}\”。
      </promptString>
      <returnStruc>
        {
          “score”： “介于 0 和 100 之间的整数”，
          “description”： “项目的简短描述”
        }
      </returnStruc>
   </Prompt>
 </Recipe>



# 变量

 - request.site：与请求关联的站点
 
 - site.itemType：通常与此站点关联的项目类型（配方、电影等）
 - request.itemType：用户在查询中请求的项的类型（如果显式）

 - request.rawQuery：在任何类型的解情之前，用户键入的查询
 - request.previousQueries：此会话中的先前查询
 - request.query：解情境化的查询
 
 - request.contextUrl：如果存在与查询关联的显式 url 作为上下文
 - request.context描述：

 - request.answers：此请求排名靠前的答案列表。对于发布步骤（如果有）


    

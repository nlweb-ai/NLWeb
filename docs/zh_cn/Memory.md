# 记忆

预检索步骤之一（使用 site_types.xml 中的 DetectMemoryRequestPrompt 实现）
用于确定用户的陈述是否包含应记住的内容
从长远来看。此 repo 中包含的代码将仅针对对话 “记住” 这一点，
只要它在前面的查询列表中传递即可。但是，正如
pre_retrieval/memory.py，有一个钩子，网站可以选择长期保留它
记忆。它可以在将来对 NLWeb 的调用中作为先前查询的一部分传递。

与其他预检索步骤（和排名）一样，内存预检索步骤是通过以下方式实现的
一个提示，可以是专用的。例如，下面是通用的内存提示符：

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

下面是一个特定于食谱的：

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
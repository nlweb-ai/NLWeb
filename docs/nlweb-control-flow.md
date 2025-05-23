
# Control Flow, Programming Model

One of the hallmarks of conversational flows (in contrast with traditional search) is that the control flow is a function of what the user says or what is known by the user. For example, if on a travel site and the user asks for attractions or hotels in a context where the location is not clear, it would make sense to first ask the user for the location. However, asking for location is not meaningful if the user is asking for movies.

A more general Chatbot (ChatGPT/Copilot/Claude/Gemini) might come back and ask such clarifying questions, depending on the system prompt, etc., but the behavior is often not as reliable as a website might want.

Traditional programming gives the programmer extremely fine-grained control, but requires that programmers encode every step of how a task should be performed. LLMs contain huge amounts of background-knowledge/intelligence relevant to the task, but programmers can only control LLMs through ‘prompting,’ which is unwieldy and unpredictable.

It is important to let the site designer pick the balance between program vs model controlling the flow, UI, etc. This also allows the site to use more constrained (traditional) design patterns in down-funnel interactions involving transactional actions, which cannot afford the ambiguity inherent in natural language.

NLWeb uses a flexible mixture of the two, with the Python code making a lot of small, very precise calls to the LLM, but retaining final control over what is shown. Each request involves on the order of dozens of LLM calls (e.g., ‘does this query refer to earlier mentioned items’, ‘Does the query refer to a place’, etc.). We call this 'Mixed Mode Programming".

More concretely, we illustrate an example of this approach here.

<!-- The document on post ranking explains more. -->

## Required Info

For some types (e.g., RealEstate), it is essential to know things like the location, price range, etc. This is done with the following prompt.

  <RealEstate>
    <Prompt ref="RequiredInfoPrompt">
      <promptString>
        Answering the user's query requires the location and price range.
        Do you have this information from this
        query or the previous queries or the context or memory about the user?
        The user's query is: {request.query}. The previous queries are: {request.previousQueries}.
      </promptString>
      <returnStruc>
        {
          "required_info_found": "True or False",
          "user_question": "Question to ask the user for the required information"
        }
      </returnStruc>
    </Prompt>
  </RealEstate>

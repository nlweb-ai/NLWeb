# Memory

One of the pre-retrieval steps (implemented using the DetectMemoryRequestPrompt in site_types.xml) is used to determine whether the statement by the user has something that should be remembered for the longer term. The code included in this repo will 'remember' that only for the conversation, so long as it is passed in the list of previous queries. However, as noted by the comment in pre_retrieval/memory.py, there is a hook for where a website may choose to keep this in longer term memory. It can be passed along in future calls to NLWeb as part of previous queries.

The memory pre retrieval step, like other pre retrieval steps (and ranking) is implemented with a prompt, which can be specialized. For example, here is the generic memory prompt:

<Prompt ref="DetectMemoryRequestPrompt">
      <promptString>
        Analyze the following statement from the user.
        Is the user asking you to remember, that may be relevant to not just this query, but also future queries?
        If so, what is the user asking us to remember?
        The user should be explicitly asking you to remember something for future queries,
        not just expressing a requirement for the current query.
        The user's query is: {request.rawQuery}.
      </promptString>
      <returnStruc>
        {
          "is_memory_request": "True or False",
          "memory_request": "The memory request, if any"
        }
      </returnStruc>
    </Prompt>

And here is one specific for recipes:

<Prompt ref="DetectMemoryRequestPrompt">
      <promptString>
        Analyze the following statement from the user.
        Is the user asking you to remember a dietary constraint, that may be relevant
        to not just this query, but also future queries? For example, the user may say
        that they are vegetarian or observe kosher or halal or specify an allergy.
        If so, what is the user asking us to remember?
        The user should be explicitly asking you to remember something for future queries,
        not just expressing a requirement for the current query.
        The user's query is: {request.rawQuery}.
      </promptString>
      <returnStruc>
        {
          "is_memory_request": "True or False",
          "memory_request": "The memory request, if any"
        }
      </returnStruc>
    </Prompt>

# Modifying behaviour by changing prompts

During the course of processing a single query from a user, NLWeb makes a number of LLM calls for many different kinds of tasks. These include:

- 'Pre' steps, e.g.,
  - Analyzing whether the query is relevant to the site
  - Constructing a decontextualized query from query history
  - Identifying whether the query mentions something that should be committed to memory
- Ranking
- 'Post'. Post steps are optional
  - Create summary of results
  - Try to answer the user's question using the top ranked results (this is closer to traditional RAG)

The prompts used for these calls are in the file site_types.xml. The behaviour of the system can be modified by changing these prompts.

Given below is a sample prompt:

<Thing>
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

 ...

</Thing>

Each <tag>Prompt</tag> is identified by a 'ref' attribute, which is used
by the code calling the LLM to construct the tag. The <tag>promptString</tag>
follows a templated structure. Each string contains placeholders / variables
(like {request.query}, {site.itemType}, etc.) that get dynamically populated
during execution. The prompts typically begin by establishing context about
the user's query and the site being searched, followed by specific instructions
for analyzing or transforming the query or ranking the candidate item
in the context of the query. The LLM calls always used structured output
and the desired structure of the output is in the <tag>returnStruc</tag>
The list of allowed placeholders is given at the end of this document.

The above prompt is very generic and meant to be used for all types of
items. However, most sites deal with a very limited number of types of items
and more specific (and hence better performing) prompts can be designed
for these. For example, if we know that the user is looking for a recipe,
we can use the following more specific prompt.

  <Recipe>
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
  </Recipe>

In the schema.org hierarchy, <tag>Recipe</tag> is under <tag>Thing</tag> in the class
hierarchy and hence when it is determined that the user is looking for a <tag>Recipe</tag>
this prompt will be used.

Prompts can also be used to change the ranking and description associated with
each item. For example, the default ranking prompt is:

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

A site which has star ratings for items (and where the json for each item includes the star rating) might want to
incorporate that rating into the ranking. One way of doing this would be to use a <tag>promptString</tag> that
asks the LLM to factor this in. E.g.,

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

Similarly, descriptions can also be changed. Eg.

 <Recipe>
   <Prompt ref="RankingPrompt">
      <promptString>
        Assign a score between 0 and 100 to the following item
        based on how relevant it is to the user's question. Include a short description of the item, focussing on the 
        relevance of the item to the user's query. Also, include the salient aspects of the nutritional value of this recipe.
        The user's question is: \"{request.query}\". The item's description in schema.org format is \"{item.description}\".
      </promptString>
      <returnStruc>
        {
          "score": "integer between 0 and 100",
          "description": "short description of the item"
        }
      </returnStruc>
   </Prompt>
 </Recipe>

## Variables

- `request.site`: the site associated with the request
- `site.itemType`: the item types (Recipe, Movie, etc.) typically associated with this site
- `request.itemType`: type of item requested by user, if explicit, in the query
- `request.rawQuery`: the query as typed in by the user, before any kind of decontextualization
- `request.previousQueries`: previous queries in this session
- `request.query`: the decontextualized query
- `request.contextUrl`: If there is an explicit url associated with the query as the context
- `request.contextDescription`: If there is an explicit description associated with the query as the context
- `request.answers`: The list of top ranked answers for this request. For post steps, if any

# NLWeb Tools System

## Overview

NLWeb now supports a flexible tool calling system that allows different methods to be invoked based on user queries. This enables specialized handling for different types of requests beyond simple search operations.

## Architecture

Tools are defined in XML format in `code/config/tools.xml`. The system:

1. Analyzes the incoming query and its associated schema.org type
2. Collects applicable tools based on the type hierarchy
3. Evaluates each tool using its specific prompt to determine relevance
4. Invokes the highest-scoring tool with extracted parameters

## Tool Definition Format

Each tool is defined within its applicable schema.org type:

```xml
<Thing>
  <Tool name="search" enabled="true">
    <path>/api/search</path>
    <method>url</method>
    <handler>core.search.SearchHandler</handler>
    <argument name="query">User's search query</argument>
    <example>Find Italian restaurants near me</example>
    <example>Show me action movies from the 1990s</example>
    <prompt>
      The user has the following query: {request.query}.
      
      The search tool finds items that match specific search criteria...
      
      Assign a score from 0 to 100 for whether the search tool is appropriate.
    </prompt>
    <returnStruc>
      {
        "score": "integer between 0 and 100",
        "search_query": "the search query that should be passed to the tool"
      }
    </returnStruc>
  </Tool>
</Thing>
```

### Tool Elements

- **name**: Unique identifier for the tool
- **enabled**: Boolean flag to enable/disable the tool
- **method**: Either "builtin" (for search) or "code" (for handler-based tools). Value "url" for remote tools coming soon.
- **handler**: Python class that implements the tool logic (required for "code" method)
- **example**: Example queries that would trigger this tool
- **prompt**: LLM prompt used to evaluate if this tool should be used
- **returnStruc**: Expected structure of the evaluation response

## Available Tools

### Search Tool

The default tool for finding items based on criteria:

- Searches for recipes, movies, products, etc. matching requirements
- Handles broad exploration queries
- Returns ranked results from the vector database

### Details Tool

Retrieves specific information about a named item:

- Gets ingredients, instructions, or nutritional info for recipes
- Retrieves cast, plot, or ratings for movies
- Shows specifications or pricing for products
- Example: "What are the ingredients in Chicken Alfredo?"

### Compare Tool

Performs side-by-side comparisons of two items:

- Compares nutritional content between recipes
- Contrasts features between products
- Evaluates movies or restaurants against each other
- Example: "Compare pizza margherita vs pepperoni pizza"

### Ensemble Tool

Creates cohesive sets of related items:

- **Meal Planning**: Appetizer + Main Course + Dessert
- **Travel Itineraries**: Museums + Restaurants + Activities
- **Outfit Recommendations**: Clothing + Accessories for specific conditions
- **Event Planning**: Venue + Catering + Entertainment

#### Ensemble Tool Example

When a user asks: "Give me an appetizer, main and dessert for an Asian fusion dinner"

1. The ensemble tool extracts three queries:
   - "Asian fusion appetizer"
   - "Asian fusion main course"
   - "Asian fusion dessert"

2. Each query is sent to the retrieval backend in parallel

3. Results are ranked by relevance using an LLM

4. Top 2-3 results from each category are selected

5. An LLM creates a cohesive recommendation combining all items

The ensemble prompt structure:

```json
{
  "score": 95,
  "queries": [
    "Asian fusion appetizer",
    "Asian fusion main course",
    "Asian fusion dessert"
  ],
  "ensemble_type": "meal_course"
}
```

### Recipe-Specific Tools

#### Substitution Tool

Finds ingredient substitutions for recipes:

- Handles dietary restrictions (vegan, gluten-free, etc.)
- Suggests alternatives for unavailable ingredients
- Example: "I need a vegan substitute for eggs in this cake recipe"

#### Accompaniment Tool

Suggests complementary items:

- Wine pairings for dishes
- Side dishes for main courses
- Sauces that balance flavors
- Example: "What salad would go best with eggplant lasagna?"

## Tool Selection Process

1. **Type Identification**: The system determines the schema.org type of the query
2. **Tool Collection**: All tools applicable to that type (including inherited from parent types) are gathered
3. **Parallel Evaluation**: Each tool's prompt is evaluated using an LLM
4. **Score-Based Selection**: The tool with the highest score above the threshold is selected
5. **Parameter Extraction**: The evaluation also extracts necessary parameters
6. **Handler Invocation**: The selected tool's handler is instantiated and executed

## Adding Custom Tools

To add a new tool:

1. **Define the Tool** in `tools.xml`:

```xml
<YourType>
  <Tool name="your_tool" enabled="true">
    <handler>core.your_module.YourHandler</handler>
    <prompt>Your evaluation prompt...</prompt>
    <returnStruc>
      {
        "score": "integer between 0 and 100",
        "your_param": "extracted parameter"
      }
    </returnStruc>
  </Tool>
</YourType>
```

2. **Implement the Handler**:

```python
class YourHandler:
    def __init__(self, params, handler):
        self.params = params
        self.handler = handler
    
    async def do(self):
        # Implement your tool logic
        result = await process_request(self.params)
        await self.handler.send_message({
            "message_type": "your_result",
            "result": result
        })
```

3. **Test thoroughly** with various queries

## Tool Execution Patterns

Tools can follow different execution patterns:

1. **Simple Query-Response**: Tool processes input and returns results
2. **Multi-Stage Processing**: Tool makes multiple LLM calls or retrieval queries
3. **Parallel Execution**: Tool spawns multiple sub-queries (like ensemble)
4. **Interactive Flow**: Tool can request additional information from user

## Best Practices

1. **Clear Prompts**: Write specific, unambiguous evaluation prompts
2. **Score Thresholds**: Use appropriate score ranges (typically 75+ for selection)
3. **Parameter Validation**: Validate extracted parameters before use
4. **Error Handling**: Gracefully handle missing or invalid parameters
5. **Logging**: Use structured logging for debugging
6. **Type Inheritance**: Leverage schema.org type hierarchy for tool reuse

## Future Enhancements

- **Remote Tools**: Support for external NLWeb endpoints as tools
- **MCP Server Integration**: Connect to Anthropic's Model Context Protocol servers
- **Dynamic Tool Loading**: Load tools from external sources at runtime
- **Tool Chaining**: Allow tools to invoke other tools
- **User-Defined Tools**: Enable users to define custom tools via configuration
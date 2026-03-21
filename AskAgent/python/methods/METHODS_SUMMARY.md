# Methods Directory Summary

## Overview
The methods directory contains specialized handlers for different types of queries and domain-specific processing logic. Each handler extends or works with the base NLWebHandler to provide targeted functionality.

## Main Components

### Generate Answer Handler (`generate_answer.py`)
- **GenerateAnswer class**: RAG-style answer generation
  - Extends NLWebHandler
  - Implements retrieval-augmented generation flow
  - Key methods:
    - `runQuery()`: Main execution pipeline
    - `prepare()`: Parallel preparation tasks
    - `get_ranked_answers()`: Retrieve and rank results
  - Prompts used:
    - RankingPromptForGenerate
    - SynthesizePromptForGenerate
    - DescriptionPromptForGenerate
  - Thread-safe result collection
  - Concurrent task execution for efficiency

### Item Details Handler (`item_details.py`)
- **ItemDetailsHandler class**: Detailed item information retrieval
  - Fetches comprehensive details for specific items
  - Handles structured data extraction
  - Formats detailed responses
  - Supports multiple item types

### Compare Items Handler (`compare_items.py`)
- **CompareItemsHandler class**: Item comparison functionality
  - Side-by-side item comparisons
  - Feature extraction and alignment
  - Difference highlighting
  - Similarity scoring
  - Multi-criteria comparison

### Statistics Handler (`statistics_handler.py`)
- **StatisticsQuery dataclass**: Statistics query representation
- **StatisticsHandler class**: Statistical analysis
  - Data aggregation
  - Statistical computations
  - Trend analysis
  - Summary statistics generation
  - Visualization data preparation

### Who Handler (`whoHandler.py`)
- **WhoHandler class**: User identification and profile
  - Extends NLWebHandler
  - User authentication status
  - Profile information retrieval
  - Session management
  - Permission checking

### Ensemble Tool Handler (`ensemble_tool.py`)
- **EnsembleToolHandler class**: Multi-model ensemble
  - Combines multiple processing approaches
  - Weighted result aggregation
  - Consensus building
  - Fallback strategies
  - Quality score computation

### Recipe Substitution Handler (`recipe_substitution.py`)
- **SubstitutionHandler class**: Recipe ingredient substitution
  - Ingredient replacement suggestions
  - Dietary restriction handling
  - Allergen alternatives
  - Quantity adjustments
  - Cooking method adaptations

### Accompaniment Handler (`accompaniment.py`)
- **AccompanimentHandler class**: Food pairing suggestions
  - Wine and food pairings
  - Side dish recommendations
  - Complementary flavors
  - Course planning
  - Dietary compatibility

## Processing Patterns

### Common Workflow
1. **Handler Initialization**
   - Receives query parameters
   - Sets up handler-specific configuration
   - Initializes result containers

2. **Query Preparation**
   - Query analysis and parsing
   - Context extraction
   - Validation checks
   - Resource allocation

3. **Domain Processing**
   - Handler-specific logic execution
   - Data retrieval and manipulation
   - Algorithm application
   - Result generation

4. **Response Formatting**
   - Structure results appropriately
   - Add metadata and citations
   - Format for presentation
   - Handle streaming if needed

### Handler Categories

#### Content Generation
- GenerateAnswer: Full RAG pipeline
- EnsembleToolHandler: Multi-approach generation

#### Information Retrieval
- ItemDetailsHandler: Detailed item data
- StatisticsHandler: Aggregated statistics

#### Comparison and Analysis
- CompareItemsHandler: Feature comparison
- AccompanimentHandler: Compatibility analysis

#### Domain-Specific
- RecipeSubstitutionHandler: Culinary domain
- WhoHandler: User domain

## Integration Points

### With Core Module
- All handlers import from core.baseHandler
- Use core.llm for language model calls
- Leverage core.prompts for prompt management
- Utilize core.retriever for data access

### With Webserver
- Handlers are invoked by route handlers
- Return structured responses
- Support streaming where applicable
- Handle errors gracefully

### With Query Analysis
- Use analyze_query for intent detection
- Apply relevance_detection filters
- Access memory for context
- Check required_info completeness

## Prompt Management
Each handler typically uses specific prompts:
- Stored in prompts.xml or similar
- Dynamically loaded and filled
- Site and context-specific variations
- Version controlled

## Error Handling
- Try-catch blocks in all handlers
- Graceful degradation strategies
- Fallback responses
- Detailed logging for debugging
- User-friendly error messages

## Performance Optimizations
- Async/await for I/O operations
- Parallel task execution where possible
- Result caching mechanisms
- Lazy loading of resources
- Connection pooling

## Extension Patterns

### Creating New Handlers
1. Extend NLWebHandler or create standalone class
2. Implement domain-specific logic
3. Define prompt templates
4. Add routing configuration
5. Handle edge cases

### Handler Responsibilities
- Input validation
- Business logic execution
- Result formatting
- Error management
- Performance monitoring

## Configuration
- Handler-specific thresholds
- Model selection
- Prompt choices
- Caching policies
- Timeout values

## Testing Considerations
- Unit tests for each handler
- Integration tests with core
- Mock external dependencies
- Performance benchmarks
- Edge case coverage

## Future Extensibility
- Plugin architecture support
- Dynamic handler loading
- Configuration-driven behavior
- A/B testing capabilities
- Metrics collection
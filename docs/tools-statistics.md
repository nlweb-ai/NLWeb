# Statistics Tool Documentation

## Overview

The Statistics Tool enables querying and visualizing statistical data from Data Commons about places (counties, cities, states) and their demographic/economic indicators.

## Architecture

### 1. Tool Definition (tools.xml)

- Located in the `<Statistics>` section
- Handles queries about statistical data, demographics, and economic indicators
- Scores queries based on statistical intent and extracts key components

### 2. Query Templates (statistics_templates.txt)

- Contains 40+ query patterns covering:
  - Single value lookups (e.g., "What is the median income in X county?")
  - Comparisons between places
  - Rankings and extremes
  - Correlations between variables
  - Filtering and thresholds
  - Trend analysis over time
  - Ratios and percentages

### 3. DCID Mappings (dcid_mappings.json)

- Maps human-readable variable names to Data Commons DCIDs
- Current mappings include:
  - population → Count_Person
  - median age → Median_Age_Person
  - median income → Median_Income_Person
  - number of homes → Count_HousingUnit
  - number of veterans → Count_Person_Veteran
  - And more...

### 4. Handler Implementation (statistics_handler.py)

#### Key Methods

1. **Template Matching**
   - `match_templates()`: Scores all templates against user query in parallel
   - Uses LLM to determine semantic similarity
   - Returns templates scoring above threshold (default 0.7)

2. **Variable/Place Extraction**
   - `extract_variables_and_places()`: Uses LLM to extract entities from query
   - Returns lists of variables and places mentioned

3. **DCID Mapping**
   - `map_to_dcids()`: Converts human-readable names to Data Commons DCIDs
   - Falls back to LLM for fuzzy matching if exact match not found

4. **Visualization Selection**
   - `determine_visualization_type()`: Chooses appropriate Data Commons component
   - Options: bar, line, map, scatter, ranking, pie charts

5. **Component Generation**
   - `create_web_component()`: Generates HTML for Data Commons web component
   - Includes all necessary attributes and parameters

## Query Flow

1. User submits query (e.g., "What is the median income in San Francisco county?")
2. Router scores the query and routes to statistics_query tool
3. Handler matches query against templates
4. Extracts variables ("median income") and places ("San Francisco county")
5. Maps to DCIDs (Median_Income_Person, geoId/06075)
6. Determines best visualization (likely datacommons-highlight for single value)
7. Generates and returns web component HTML

## Adding New Variables

To add support for new statistical variables:

1. Add the mapping to `dcid_mappings.json`:

```json
{
  "variables": {
    "new_variable_name": "DCID_For_Variable"
  }
}
```

2. Find DCIDs at: [https://datacommons.org/browser](https://datacommons.org/browser)

## Example Queries

- "What is the population of Los Angeles county?"
- "Which county has the highest median income?"
- "Compare unemployment rates between San Francisco and San Diego"
- "Show me the top 10 counties by number of veterans"
- "What's the correlation between median age and median income across all counties?"
- "Which counties have population greater than 1 million?"

## Testing

Test the tool with various query types:

1. Single value queries
2. Comparisons
3. Rankings
4. Correlations
5. Filtering queries
6. Trend analysis
7. Ratio calculations

## Future Enhancements

1. **Place Resolution**: Implement proper geocoding to resolve place names to DCIDs
2. **Time Series**: Add support for historical data and trend analysis
3. **Custom Aggregations**: Support more complex statistical calculations
4. **Caching**: Cache template matches and DCID mappings for performance
5. **Error Handling**: Better error messages for unknown variables/places
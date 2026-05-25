<?php
/**
 * NLWeb Query Rewriter — implements query fanout for complex queries.
 *
 * Takes a complex natural language query and rewrites it into multiple
 * simpler keyword queries for better retrieval from traditional search engines.
 *
 * Maps to QueryRewrite.do() in the Python code.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class NLWeb_Query_Rewriter {

	/**
	 * Rewrite a complex query into simpler keyword queries.
	 *
	 * @param string $query The decontextualized query.
	 * @param array &$debug Optional debug array to populate.
	 * @return array Array of rewritten queries (strings).
	 */
	public static function rewrite( $query, &$debug = null ) {

		$settings = NLWeb_Settings::get_all();

		// Check if query rewrite is enabled
		if ( empty( $settings['enable_query_fanout'] ) ) {
			if ( is_array( $debug ) ) {
				$debug['fanout_disabled'] = true;
			}
			return array( $query );
		}

		// Build the prompt
		$prompt = self::build_prompt( $query );

		// Schema for the expected response
		$schema = array(
			'rewritten_queries' => 'Array of 1-5 simpler keyword queries',
			'query_count'       => 'Number of queries generated (1-5)',
		);

		// Call the LLM
		$response = NLWeb_LLM::ask( $prompt, $schema, 'high', 20 );

		if ( is_array( $debug ) ) {
			$debug['llm_prompt'] = $prompt;
			$debug['llm_response'] = $response;
			$debug['api_key_set'] = ! empty( $settings['api_key'] );
			$debug['llm_provider'] = $settings['llm_provider'] ?? 'not set';
			$debug['model_high'] = $settings['model_high'] ?? 'not set';
		}

		if ( empty( $response ) || empty( $response['rewritten_queries'] ) ) {
			// Fall back to original query
			if ( is_array( $debug ) ) {
				$debug['fallback_reason'] = empty( $response ) ? 'LLM returned empty response' : 'No rewritten_queries in response';
			}
			return array( $query );
		}

		// Extract and validate queries
		$rewritten = $response['rewritten_queries'];

		if ( ! is_array( $rewritten ) ) {
			return array( $query );
		}

		// Filter out empty queries and ensure they are strings
		$valid_queries = array();
		foreach ( $rewritten as $q ) {
			if ( is_string( $q ) && ! empty( trim( $q ) ) ) {
				$valid_queries[] = trim( $q );
			}
		}

		// Limit to 5 queries
		$valid_queries = array_slice( $valid_queries, 0, 5 );

		if ( empty( $valid_queries ) ) {
			return array( $query );
		}

		return $valid_queries;
	}

	/**
	 * Build the query rewrite prompt.
	 *
	 * @param string $query The original query.
	 * @return string The prompt.
	 */
	private static function build_prompt( $query ) {
		return <<<PROMPT
You are helping to rewrite a complex search query into simpler keyword queries for a traditional keyword-based search engine.
The search engine works best with short, focused queries containing important keywords.

Take the following query and break it down into up to 5 simpler search queries.
Each query should:
- Contain no more than 3 words
- Focus on the most important keywords and concepts
- Be diverse to cover different aspects of the original query
- Use only essential nouns, adjectives, or product terms
- Avoid common words like "for", "the", "some", "are", "that", "would", "be"

For example:
- "what are some options for plates that would be appropriate for serving vegetables" → ["vegetable plates", "serving plates", "dinner plates", "salad plates", "ceramic plates"]
- "looking for a tea pot that can brew green tea" → ["tea pot", "green tea", "teapot ceramic", "japanese teapot", "brewing pot"]
- "movies about alien invasions in the 1950s" → ["alien invasion", "1950s scifi", "alien movies", "invasion films", "scifi 1950s"]

The original query is: {$query}
PROMPT;
	}

	/**
	 * Execute multiple queries and combine results.
	 *
	 * @param array $queries Array of query strings.
	 * @param int   $max_per_query Max results per query.
	 * @return array Combined and deduplicated results.
	 */
	public static function fanout_search( $queries, $max_per_query = 10 ) {

		$all_results = array();
		$seen_ids    = array();

		foreach ( $queries as $query ) {
			$results = NLWeb_Retriever::search( $query, $max_per_query );

			foreach ( $results as $item ) {
				$id = $item['id'] ?? null;

				// Skip if we've already seen this item
				if ( $id && in_array( $id, $seen_ids, true ) ) {
					continue;
				}

				$all_results[] = $item;
				if ( $id ) {
					$seen_ids[] = $id;
				}
			}
		}

		return $all_results;
	}
}

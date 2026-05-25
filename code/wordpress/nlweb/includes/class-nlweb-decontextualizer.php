<?php
/**
 * NLWeb Decontextualizer — rewrites a follow-up query so it stands alone.
 *
 * Maps to PrevQueryDecontextualizer in the Python code.
 *
 * Example:
 *   prev_queries: ["pasta recipes"]
 *   raw_query:    "what about vegetarian ones?"
 *   result:       "vegetarian pasta recipes"
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NLWeb_Decontextualizer {

    /**
     * Decontextualize a query given conversation history.
     *
     * @param string   $raw_query        The user's latest query.
     * @param string[] $previous_queries Previous queries in this conversation.
     * @param string   $site_name        The site name (used in the prompt).
     * @param string   $item_type        Content type hint (e.g. 'Article').
     * @return array   {
     *     'query'                         => string,  // the query to use for retrieval
     *     'requires_decontextualization'   => bool,
     * }
     */
    public static function decontextualize( $raw_query, $previous_queries = array(), $site_name = '', $item_type = 'Article' ) {

        // Nothing to decontextualize.
        if ( empty( $previous_queries ) ) {
            return array(
                'query'                       => $raw_query,
                'requires_decontextualization' => false,
            );
        }

        $prompt_template = NLWeb_Settings::get( 'prompt_decontextualize' );

        $prompt = strtr( $prompt_template, array(
            '{site_name}'        => $site_name ?: get_bloginfo( 'name' ),
            '{item_type}'        => $item_type,
            '{raw_query}'        => $raw_query,
            '{previous_queries}' => wp_json_encode( $previous_queries ),
        ) );

        $schema = array(
            'requires_decontextualization' => 'True or False',
            'decontextualized_query'       => 'The rewritten query, if decontextualization is required',
        );

        $response = NLWeb_LLM::ask( $prompt, $schema, 'low' );

        if ( empty( $response ) || ! isset( $response['requires_decontextualization'] ) ) {
            // LLM failed — fall back to the original query.
            return array(
                'query'                       => $raw_query,
                'requires_decontextualization' => false,
            );
        }

        $needs = ( 'True' === $response['requires_decontextualization'] || true === $response['requires_decontextualization'] );

        return array(
            'query'                       => $needs ? $response['decontextualized_query'] : $raw_query,
            'requires_decontextualization' => $needs,
        );
    }
}

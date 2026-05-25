<?php
/**
 * NLWeb Protocol v0.55 Handler
 *
 * Implements the NLWeb v0.55 specification for request/response handling.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NLWeb_Protocol {

    const VERSION = '0.55';

    /**
     * Parse and validate an NLWeb v0.55 request.
     *
     * @param WP_REST_Request $request The REST request object.
     * @return array Parsed request with query, context, prefer, meta.
     */
    public static function parse_request( $request ) {

        // Support both GET (old format) and POST (new format)
        $method = $request->get_method();

        if ( 'POST' === $method ) {
            $body = $request->get_json_params();

            if ( empty( $body ) ) {
                $body = array();
            }

            return array(
                'query'   => self::parse_query( $body['query'] ?? array() ),
                'context' => self::parse_context( $body['context'] ?? array() ),
                'prefer'  => self::parse_prefer( $body['prefer'] ?? array() ),
                'meta'    => self::parse_meta( $body['meta'] ?? array() ),
            );
        }

        // GET request - legacy format compatibility
        return array(
            'query'   => array(
                'text' => $request->get_param( 'query' ) ?? '',
                'site' => $request->get_param( 'site' ) ?? get_bloginfo( 'name' ),
            ),
            'context' => array(
                'prev' => $request->get_param( 'prev' ) ?? array(),
            ),
            'prefer'  => array(
                'response_format' => 'conversational_search',
                'mode'            => $request->get_param( 'generate_mode' ) === 'summarize' ? 'list, summarize' : 'list',
            ),
            'meta'    => array(
                'version' => self::VERSION,
            ),
        );
    }

    /**
     * Parse query section.
     */
    private static function parse_query( $query ) {
        return array(
            'text'     => $query['text'] ?? '',
            'site'     => $query['site'] ?? get_bloginfo( 'name' ),
            'itemType' => $query['itemType'] ?? null,
            'filters'  => array_diff_key( $query, array_flip( array( 'text', 'site', 'itemType' ) ) ),
        );
    }

    /**
     * Parse context section.
     */
    private static function parse_context( $context ) {
        return array(
            '@type'  => $context['@type'] ?? 'ConversationalContext',
            'prev'   => $context['prev'] ?? array(),
            'text'   => $context['text'] ?? '',
            'memory' => $context['memory'] ?? '',
        );
    }

    /**
     * Parse prefer section.
     */
    private static function parse_prefer( $prefer ) {
        return array(
            'streaming'        => $prefer['streaming'] ?? false,
            'response_format'  => $prefer['response_format'] ?? 'conversational_search',
            'mode'             => $prefer['mode'] ?? 'list',
            'accept-language'  => $prefer['accept-language'] ?? 'en',
            'user-agent'       => $prefer['user-agent'] ?? '',
        );
    }

    /**
     * Parse meta section.
     */
    private static function parse_meta( $meta ) {
        return array(
            'version'         => $meta['version'] ?? self::VERSION,
            'session_context' => $meta['session_context'] ?? array(),
            'user'            => $meta['user'] ?? null,
            'remember'        => $meta['remember'] ?? false,
        );
    }

    /**
     * Build an NLWeb v0.55 compliant response.
     *
     * @param string $response_type One of: answer, elicitation, promise, failure.
     * @param mixed  $content The response content.
     * @param array  $prefer The prefer settings from the request.
     * @param array  $meta Additional metadata.
     * @return array The response structure.
     */
    public static function build_response( $response_type, $content, $prefer = array(), $meta = array() ) {

        $response_format = $prefer['response_format'] ?? 'conversational_search';

        $_meta = array(
            'response_type'   => $response_type,
            'response_format' => $response_format,
            'version'         => self::VERSION,
        );

        // Merge additional meta
        $_meta = array_merge( $_meta, $meta );

        $response = array( '_meta' => $_meta );

        // Build content based on response type
        switch ( $response_type ) {
            case 'answer':
                if ( 'chatgpt_app' === $response_format ) {
                    $response = array_merge( $response, self::build_chatgpt_app_content( $content ) );
                } else {
                    $response['results'] = $content['results'] ?? array();
                }
                break;

            case 'elicitation':
                $response['elicitation'] = $content;
                break;

            case 'promise':
                $response['promise'] = $content;
                break;

            case 'failure':
                $response['error'] = $content;
                break;
        }

        return $response;
    }

    /**
     * Build ChatGPT App format content.
     */
    private static function build_chatgpt_app_content( $content ) {

        $results = $content['results'] ?? array();
        $summary = $content['summary'] ?? '';

        // Build natural language content for the LLM
        $text_content = array();

        if ( ! empty( $summary ) ) {
            $text_content[] = array(
                'type' => 'text',
                'text' => $summary,
            );
        } else {
            $count = count( $results );
            $text_content[] = array(
                'type' => 'text',
                'text' => "Found {$count} results.",
            );
        }

        // Build structured data
        $structured_data = array();
        foreach ( $results as $item ) {
            // Remove internal fields that shouldn't be in structured data
            $clean_item = $item;
            unset( $clean_item['id'] );
            $structured_data[] = $clean_item;
        }

        return array(
            'content'        => $text_content,
            'structuredData' => $structured_data,
        );
    }

    /**
     * Build a failure response.
     */
    public static function build_failure( $code, $message = '', $prefer = array() ) {
        return self::build_response(
            'failure',
            array(
                'code'    => $code,
                'message' => $message,
            ),
            $prefer
        );
    }

    /**
     * Build an answer response.
     */
    public static function build_answer( $results, $summary = null, $prefer = array(), $meta = array() ) {

        $modes = array_map( 'trim', explode( ',', $prefer['mode'] ?? 'list' ) );

        // If summarize mode is requested and we have a summary, add it as the first result
        if ( in_array( 'summarize', $modes, true ) && ! empty( $summary ) ) {
            array_unshift(
                $results,
                array(
                    '@type' => 'SearchSummary',
                    'text'  => $summary,
                )
            );
        }

        $content = array(
            'results' => $results,
            'summary' => $summary,
        );

        return self::build_response( 'answer', $content, $prefer, $meta );
    }
}

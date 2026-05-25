<?php
/**
 * NLWeb LLM — thin wrapper around OpenAI / Anthropic / Gemini HTTP APIs.
 *
 * Every call goes through ask() which returns the parsed JSON response
 * matching the supplied schema, identical to ask_llm() in the Python code.
 *
 * Also exposes ask_multi() to make many calls in parallel via curl_multi.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NLWeb_LLM {

    /**
     * Make a single LLM call.
     *
     * @param string $prompt     The prompt text.
     * @param array  $schema     Expected return structure (keys + description).
     * @param string $level      'high' or 'low' — selects the model.
     * @param int    $timeout    Timeout in seconds.
     * @return array             Parsed JSON response matching $schema, or empty array on failure.
     */
    public static function ask( $prompt, $schema, $level = 'low', $timeout = 15 ) {

        $settings = NLWeb_Settings::get_all();
        $provider = $settings['llm_provider'];
        $api_key  = $settings['api_key'];
        $model    = ( 'high' === $level ) ? $settings['model_high'] : $settings['model_low'];

        if ( empty( $api_key ) || empty( $model ) ) {
            return array();
        }

        $request = self::build_request( $provider, $api_key, $model, $prompt, $schema, $settings['api_endpoint'], $timeout );
        if ( ! $request ) {
            return array();
        }

        $response = wp_remote_post( $request['url'], $request['args'] );

        if ( is_wp_error( $response ) ) {
            return array();
        }

        $body = wp_remote_retrieve_body( $response );
        return self::parse_response( $provider, $body, $schema );
    }

    /**
     * Make many LLM calls in parallel using curl_multi.
     *
     * @param array[] $calls  Each element: array( 'prompt' => string, 'schema' => array, 'level' => string ).
     * @param int     $timeout Timeout in seconds per call.
     * @return array[]         Array of parsed results in the same order as $calls.
     */
    public static function ask_multi( $calls, $timeout = 15 ) {

        if ( ! function_exists( 'curl_multi_init' ) ) {
            // Fallback: sequential.
            $results = array();
            foreach ( $calls as $call ) {
                $results[] = self::ask( $call['prompt'], $call['schema'], $call['level'] ?? 'low', $timeout );
            }
            return $results;
        }

        $settings = NLWeb_Settings::get_all();
        $provider = $settings['llm_provider'];
        $api_key  = $settings['api_key'];

        $mh      = curl_multi_init();
        $handles = array();

        foreach ( $calls as $i => $call ) {
            $model   = ( 'high' === ( $call['level'] ?? 'low' ) ) ? $settings['model_high'] : $settings['model_low'];
            $request = self::build_request( $provider, $api_key, $model, $call['prompt'], $call['schema'], $settings['api_endpoint'], $timeout );

            if ( ! $request ) {
                $handles[ $i ] = null;
                continue;
            }

            $ch = curl_init( $request['url'] );
            curl_setopt( $ch, CURLOPT_RETURNTRANSFER, true );
            curl_setopt( $ch, CURLOPT_POST, true );
            curl_setopt( $ch, CURLOPT_POSTFIELDS, $request['args']['body'] );
            curl_setopt( $ch, CURLOPT_HTTPHEADER, self::flatten_headers( $request['args']['headers'] ) );
            curl_setopt( $ch, CURLOPT_TIMEOUT, $timeout );

            curl_multi_add_handle( $mh, $ch );
            $handles[ $i ] = $ch;
        }

        // Execute all requests.
        $running = null;
        do {
            curl_multi_exec( $mh, $running );
            curl_multi_select( $mh );
        } while ( $running > 0 );

        // Collect results.
        $results = array();
        foreach ( $handles as $i => $ch ) {
            if ( null === $ch ) {
                $results[ $i ] = array();
                continue;
            }

            $body = curl_multi_getcontent( $ch );
            curl_multi_remove_handle( $mh, $ch );
            curl_close( $ch );

            $results[ $i ] = self::parse_response( $provider, $body, $calls[ $i ]['schema'] );
        }

        curl_multi_close( $mh );
        return $results;
    }

    /* ----------------------------------------------------------------
     *  Build provider-specific request
     * -------------------------------------------------------------- */

    private static function build_request( $provider, $api_key, $model, $prompt, $schema, $endpoint, $timeout ) {

        $system_msg = 'You are a helpful assistant. Respond ONLY with valid JSON matching this schema: '
                    . wp_json_encode( $schema );

        switch ( $provider ) {

            case 'openrouter':
                $url = $endpoint ?: 'https://openrouter.ai/api/v1/chat/completions';
                return array(
                    'url'  => $url,
                    'args' => array(
                        'timeout' => $timeout,
                        'headers' => array(
                            'Content-Type'  => 'application/json',
                            'Authorization' => "Bearer $api_key",
                            'HTTP-Referer'  => get_site_url(),
                            'X-Title'       => 'NLWeb WordPress Plugin',
                        ),
                        'body' => wp_json_encode( array(
                            'model'    => $model,
                            'messages' => array(
                                array( 'role' => 'system', 'content' => $system_msg ),
                                array( 'role' => 'user',   'content' => $prompt ),
                            ),
                            'response_format' => array( 'type' => 'json_object' ),
                            'max_tokens'      => 512,
                            'temperature'     => 0,
                        ) ),
                    ),
                );

            case 'anthropic':
                $url = $endpoint ?: 'https://api.anthropic.com/v1/messages';
                return array(
                    'url'  => $url,
                    'args' => array(
                        'timeout' => $timeout,
                        'headers' => array(
                            'Content-Type'      => 'application/json',
                            'x-api-key'         => $api_key,
                            'anthropic-version'  => '2023-06-01',
                        ),
                        'body' => wp_json_encode( array(
                            'model'      => $model,
                            'max_tokens' => 512,
                            'system'     => $system_msg,
                            'messages'   => array(
                                array( 'role' => 'user', 'content' => $prompt ),
                            ),
                        ) ),
                    ),
                );

            case 'gemini':
                $url = $endpoint
                     ?: "https://generativelanguage.googleapis.com/v1beta/models/{$model}:generateContent?key={$api_key}";
                return array(
                    'url'  => $url,
                    'args' => array(
                        'timeout' => $timeout,
                        'headers' => array(
                            'Content-Type' => 'application/json',
                        ),
                        'body' => wp_json_encode( array(
                            'contents' => array(
                                array(
                                    'parts' => array(
                                        array( 'text' => $system_msg . "\n\n" . $prompt ),
                                    ),
                                ),
                            ),
                            'generationConfig' => array(
                                'responseMimeType' => 'application/json',
                                'maxOutputTokens'  => 512,
                                'temperature'      => 0,
                            ),
                        ) ),
                    ),
                );

            default:
                return null;
        }
    }

    /* ----------------------------------------------------------------
     *  Parse provider-specific response into a plain array
     * -------------------------------------------------------------- */

    private static function parse_response( $provider, $body, $schema ) {

        $data = json_decode( $body, true );
        if ( ! is_array( $data ) ) {
            return array();
        }

        $text = '';
        switch ( $provider ) {
            case 'openrouter':
                $text = $data['choices'][0]['message']['content'] ?? '';
                break;
            case 'anthropic':
                $text = $data['content'][0]['text'] ?? '';
                break;
            case 'gemini':
                $text = $data['candidates'][0]['content']['parts'][0]['text'] ?? '';
                break;
        }

        if ( empty( $text ) ) {
            return array();
        }

        // Try to parse as JSON.
        $parsed = json_decode( $text, true );
        if ( is_array( $parsed ) ) {
            return $parsed;
        }

        // Attempt to extract JSON from markdown code fences.
        if ( preg_match( '/```(?:json)?\s*(.+?)\s*```/s', $text, $m ) ) {
            $parsed = json_decode( $m[1], true );
            if ( is_array( $parsed ) ) {
                return $parsed;
            }
        }

        return array();
    }

    /* ----------------------------------------------------------------
     *  Utility
     * -------------------------------------------------------------- */

    private static function flatten_headers( $headers ) {
        $flat = array();
        foreach ( $headers as $k => $v ) {
            $flat[] = "$k: $v";
        }
        return $flat;
    }
}

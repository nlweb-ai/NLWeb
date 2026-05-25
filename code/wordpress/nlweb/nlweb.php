<?php
/**
 * Plugin Name: NLWeb
 * Plugin URI: https://nlweb.ai
 * Description: Adds natural language search to your WordPress site via the NLWeb protocol. Exposes /ask and MCP endpoints powered by LLM-based ranking of your existing content.
 * Version: 0.1.0
 * Author: NLWeb
 * License: MIT
 * Requires PHP: 7.4
 * Requires at least: 5.6
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

define( 'NLWEB_VERSION', '0.1.0' );
define( 'NLWEB_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'NLWEB_PLUGIN_URL', plugin_dir_url( __FILE__ ) );

// Core includes
require_once NLWEB_PLUGIN_DIR . 'includes/class-nlweb-protocol.php';
require_once NLWEB_PLUGIN_DIR . 'includes/class-nlweb-settings.php';
require_once NLWEB_PLUGIN_DIR . 'includes/class-nlweb-llm.php';
require_once NLWEB_PLUGIN_DIR . 'includes/class-nlweb-retriever.php';
require_once NLWEB_PLUGIN_DIR . 'includes/class-nlweb-decontextualizer.php';
require_once NLWEB_PLUGIN_DIR . 'includes/class-nlweb-ranker.php';
require_once NLWEB_PLUGIN_DIR . 'includes/class-nlweb-query-rewriter.php';
require_once NLWEB_PLUGIN_DIR . 'includes/class-nlweb-handler.php';
require_once NLWEB_PLUGIN_DIR . 'includes/class-nlweb-frontend.php';

/**
 * Initialize admin settings.
 */
add_action( 'admin_menu', array( 'NLWeb_Settings', 'add_menu_page' ) );
add_action( 'admin_init', array( 'NLWeb_Settings', 'register_settings' ) );

/**
 * Initialize frontend functionality.
 */
NLWeb_Frontend::init();

/**
 * Register REST API routes.
 */
add_action( 'rest_api_init', function () {

    // ---- /ask endpoint (GET and POST) ----
    register_rest_route( 'nlweb/v1', '/ask', array(
        array(
            'methods'             => 'GET',
            'callback'            => 'nlweb_handle_ask',
            'permission_callback' => '__return_true',
        ),
        array(
            'methods'             => 'POST',
            'callback'            => 'nlweb_handle_ask',
            'permission_callback' => '__return_true',
        ),
    ) );

    // ---- MCP endpoint (JSON-RPC 2.0) ----
    register_rest_route( 'nlweb/v1', '/mcp', array(
        'methods'             => 'POST',
        'callback'            => 'nlweb_handle_mcp',
        'permission_callback' => '__return_true',
    ) );
} );

/* ------------------------------------------------------------------ */
/*  /ask handler                                                       */
/* ------------------------------------------------------------------ */

function nlweb_handle_ask( WP_REST_Request $request ) {

    // Parse request using NLWeb v0.55 protocol
    $parsed = NLWeb_Protocol::parse_request( $request );

    // Validate query
    if ( empty( $parsed['query']['text'] ) ) {
        $response = NLWeb_Protocol::build_failure(
            'INVALID_QUERY',
            'query.text parameter is required',
            $parsed['prefer']
        );
        return new WP_REST_Response( $response, 400 );
    }

    // Build query params for handler (maintaining backward compatibility)
    $query_params = array(
        'query'                  => $parsed['query']['text'],
        'site'                   => $parsed['query']['site'],
        'prev'                   => $parsed['context']['prev'],
        'generate_mode'          => strpos( $parsed['prefer']['mode'], 'summarize' ) !== false ? 'summarize' : 'none',
        'decontextualized_query' => '',
    );

    try {
        $handler = new NLWeb_Handler( $query_params );
        $result  = $handler->run();

        // Convert old format to new protocol format
        $response = NLWeb_Protocol::build_answer(
            $result['results'] ?? array(),
            $result['summary'] ?? null,
            $parsed['prefer'],
            array(
                'session_context' => $parsed['meta']['session_context'],
            )
        );

        // Add debug info if present
        if ( ! empty( $result['debug'] ) ) {
            $response['debug'] = $result['debug'];
        }

        return new WP_REST_Response( $response, 200 );

    } catch ( Exception $e ) {
        $response = NLWeb_Protocol::build_failure(
            'INTERNAL_ERROR',
            $e->getMessage(),
            $parsed['prefer']
        );
        return new WP_REST_Response( $response, 500 );
    }
}

/* ------------------------------------------------------------------ */
/*  MCP JSON-RPC 2.0 handler                                          */
/* ------------------------------------------------------------------ */

function nlweb_handle_mcp( WP_REST_Request $request ) {

    $body = $request->get_json_params();

    $jsonrpc    = $body['jsonrpc'] ?? '2.0';
    $method     = $body['method']  ?? '';
    $params     = $body['params']  ?? array();
    $request_id = $body['id']      ?? null;

    try {
        switch ( $method ) {

            case 'initialize':
                $result = array(
                    'protocolVersion' => '2024-11-05',
                    'capabilities'    => array( 'tools' => new stdClass() ),
                    'serverInfo'      => array(
                        'name'    => 'nlweb-wordpress',
                        'version' => NLWEB_VERSION,
                    ),
                    'instructions'    => 'NLWeb WordPress endpoint - search and query ' . get_bloginfo( 'name' ),
                );
                break;

            case 'notifications/initialized':
            case 'initialized':
                // Notification — no response required.
                if ( null === $request_id ) {
                    return new WP_REST_Response( null, 204 );
                }
                $result = array( 'status' => 'ok' );
                break;

            case 'tools/list':
                $result = nlweb_mcp_tools_list();
                break;

            case 'tools/call':
                $result = nlweb_mcp_tools_call( $params );
                break;

            default:
                return nlweb_jsonrpc_error( $request_id, -32601, "Method not found: $method" );
        }

        return new WP_REST_Response( array(
            'jsonrpc' => $jsonrpc,
            'id'      => $request_id,
            'result'  => $result,
        ), 200 );

    } catch ( Exception $e ) {
        return nlweb_jsonrpc_error( $request_id, -32603, $e->getMessage() );
    }
}

/* ---- MCP helpers ------------------------------------------------- */

function nlweb_mcp_tools_list() {
    $site_name = get_bloginfo( 'name' );
    return array(
        'tools' => array(
            array(
                'name'        => 'ask',
                'description' => "Search and query content on $site_name",
                'inputSchema' => array(
                    'type'       => 'object',
                    'properties' => array(
                        'query' => array(
                            'type'        => 'string',
                            'description' => 'The search query or question',
                        ),
                        'generate_mode' => array(
                            'type'        => 'string',
                            'enum'        => array( 'list', 'summarize' ),
                            'description' => 'Response mode',
                            'default'     => 'list',
                        ),
                    ),
                    'required' => array( 'query' ),
                ),
            ),
        ),
    );
}

function nlweb_mcp_tools_call( $params ) {
    $tool_name = $params['name'] ?? '';
    $arguments = $params['arguments'] ?? array();

    if ( 'ask' !== $tool_name ) {
        throw new Exception( "Unknown tool: $tool_name" );
    }

    $query_params = array(
        'query'         => $arguments['query'] ?? '',
        'site'          => get_bloginfo( 'name' ),
        'generate_mode' => $arguments['generate_mode'] ?? 'list',
        'prev'          => $arguments['prev'] ?? array(),
        'last_ans'      => $arguments['last_ans'] ?? array(),
    );

    $handler = new NLWeb_Handler( $query_params );
    $result  = $handler->run();

    return array(
        'content' => array(
            array(
                'type' => 'text',
                'text' => wp_json_encode( $result ),
            ),
        ),
        'isError' => false,
    );
}

function nlweb_jsonrpc_error( $id, $code, $message ) {
    return new WP_REST_Response( array(
        'jsonrpc' => '2.0',
        'id'      => $id,
        'error'   => array(
            'code'    => $code,
            'message' => $message,
        ),
    ), 200 );
}

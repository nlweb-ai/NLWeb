<?php
/**
 * NLWeb Handler — the main query orchestrator.
 *
 * Maps to NLWebHandler.runQuery() in the Python code.
 * Runs the full pipeline: decontextualize → retrieve → rank → (summarize).
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NLWeb_Handler {

    /** @var array Query parameters. */
    private $params;

    /** @var string The (possibly decontextualized) query used for retrieval. */
    private $query;

    /** @var string The raw query as entered by the user. */
    private $raw_query;

    /** @var string Site name. */
    private $site;

    /** @var array Previous queries (for multi-turn). */
    private $prev_queries;

    /** @var array Previous answers (title+url pairs). */
    private $last_answers;

    /** @var string generate mode: none | summarize */
    private $generate_mode;

    /** @var bool Whether decontextualization happened. */
    private $was_decontextualized = false;

    /** @var array Debug information for display. */
    private $debug = array();

    public function __construct( $params ) {
        $this->params        = $params;
        $this->raw_query     = $params['query'] ?? '';
        $this->site          = $params['site'] ?? get_bloginfo( 'name' );
        $this->prev_queries  = $params['prev'] ?? array();
        $this->last_answers  = $params['last_ans'] ?? array();
        $this->generate_mode = $params['generate_mode'] ?? 'none';

        // If the caller already provides a decontextualized query, use it.
        $this->query = ! empty( $params['decontextualized_query'] )
            ? $params['decontextualized_query']
            : '';
    }

    /**
     * Execute the full pipeline and return the response.
     *
     * @return array The response payload (matches /ask JSON).
     */
    public function run() {

        $settings = NLWeb_Settings::get_all();

        /* ---- 1. Decontextualize ----------------------------------- */

        if ( empty( $this->query ) ) {
            $decon = NLWeb_Decontextualizer::decontextualize(
                $this->raw_query,
                $this->prev_queries,
                $this->site
            );
            $this->query                = $decon['query'];
            $this->was_decontextualized = $decon['requires_decontextualization'];
            $this->debug[] = array(
                'step' => 'Decontextualization',
                'raw_query' => $this->raw_query,
                'decontextualized_query' => $this->query,
                'was_changed' => $this->was_decontextualized,
            );
        } else {
            $this->debug[] = array(
                'step' => 'Decontextualization',
                'message' => 'Skipped (query already provided)',
            );
        }

        /* ---- 2. Query Fanout (optional) --------------------------- */

        $rewritten_queries = array( $this->query );
        $fanout_debug = array();
        if ( ! empty( $settings['enable_query_fanout'] ) ) {
            $rewritten_queries = NLWeb_Query_Rewriter::rewrite( $this->query, $fanout_debug );
            $this->debug[] = array(
                'step' => 'Query Fanout',
                'enabled' => true,
                'original_query' => $this->query,
                'rewritten_queries' => $rewritten_queries,
                'count' => count( $rewritten_queries ),
                'llm_details' => $fanout_debug,
            );
        } else {
            $this->debug[] = array(
                'step' => 'Query Fanout',
                'enabled' => false,
                'message' => 'Query fanout disabled in settings',
            );
        }

        /* ---- 3. Retrieve ------------------------------------------ */

        $max_retrieve = (int) $settings['max_results'];

        if ( count( $rewritten_queries ) > 1 ) {
            // Fanout search across multiple queries
            $max_per_query = (int) ( $max_retrieve / count( $rewritten_queries ) );
            $max_per_query = max( $max_per_query, 5 ); // At least 5 per query
            $items         = NLWeb_Query_Rewriter::fanout_search( $rewritten_queries, $max_per_query );
            $this->debug[] = array(
                'step' => 'Retrieval',
                'mode' => 'fanout',
                'queries' => $rewritten_queries,
                'max_per_query' => $max_per_query,
                'items_found' => count( $items ),
            );
        } else {
            // Single query search
            $items = NLWeb_Retriever::search( $this->query, $max_retrieve );
            $this->debug[] = array(
                'step' => 'Retrieval',
                'mode' => 'single',
                'query' => $this->query,
                'max_results' => $max_retrieve,
                'items_found' => count( $items ),
            );
        }

        if ( empty( $items ) ) {
            $response = $this->build_response( array(), $settings );
            // Include rewritten queries in response if fanout was used
            if ( count( $rewritten_queries ) > 1 ) {
                $response['rewritten_queries'] = $rewritten_queries;
            }
            return $response;
        }

        /* ---- 4. Rank ---------------------------------------------- */

        $ranked = NLWeb_Ranker::rank( $this->query, $items );
        $this->debug[] = array(
            'step' => 'Ranking',
            'items_before' => count( $items ),
            'items_after' => count( $ranked ),
            'top_score' => ! empty( $ranked ) ? $ranked[0]['score'] : null,
        );

        /* ---- 4. Optionally summarize ------------------------------ */

        $summary = null;
        if ( 'summarize' === $this->generate_mode && ! empty( $ranked ) ) {
            $summary = $this->summarize( $ranked, $settings );
        }

        return $this->build_response( $ranked, $settings, $summary );
    }

    /* ----------------------------------------------------------------
     *  Summarize
     * -------------------------------------------------------------- */

    private function summarize( $ranked, $settings ) {

        $top = array_slice( $ranked, 0, 3 );

        $prompt_template = $settings['prompt_summarize'];
        $prompt = strtr( $prompt_template, array(
            '{query}'   => $this->query,
            '{answers}' => wp_json_encode( $top ),
        ) );

        $schema = array( 'summary' => 'string' );

        $resp = NLWeb_LLM::ask( $prompt, $schema, 'high', 20 );

        return $resp['summary'] ?? null;
    }

    /* ----------------------------------------------------------------
     *  Build final response
     * -------------------------------------------------------------- */

    private function build_response( $ranked, $settings, $summary = null ) {

        $response = array(
            'message_type' => 'result',
        );

        // Include decontextualization info when it happened.
        if ( $this->was_decontextualized ) {
            $response['decontextualized_query'] = $this->query;
            $response['original_query']         = $this->raw_query;
        }

        $response['results'] = $ranked;

        if ( null !== $summary ) {
            $response['summary'] = $summary;
        }

        // Include debug information
        $response['debug'] = $this->debug;

        return $response;
    }
}

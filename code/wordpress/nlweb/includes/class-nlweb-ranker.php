<?php
/**
 * NLWeb Ranker — scores retrieved items via LLM, using parallel curl_multi.
 *
 * Maps to ranking.py Ranking class in the Python code.
 *
 * Each item is scored 0-100 and given an LLM-generated description.
 * Items below the score threshold are dropped; the rest are returned
 * sorted by score descending, capped at num_results_to_return.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NLWeb_Ranker {

    /**
     * Rank a set of retrieved items.
     *
     * @param string  $query  The (decontextualized) query.
     * @param array[] $items  Each element: [ url, schema_json, name, site ].
     * @return array[]        Ranked results: [ { @type, url, name, site, siteUrl, score, description, schema_object } ]
     */
    public static function rank( $query, $items ) {

        if ( empty( $items ) ) {
            return array();
        }

        $settings        = NLWeb_Settings::get_all();
        $prompt_template = $settings['prompt_ranking'];
        $threshold       = (int) $settings['score_threshold'];
        $max_return      = (int) $settings['num_results_to_return'];

        // Build one LLM call per item.
        $calls = array();
        foreach ( $items as $item ) {
            list( $url, $schema_json, $name, $site ) = $item;

            $description = self::trim_schema( $schema_json );

            $prompt = strtr( $prompt_template, array(
                '{query}'            => $query,
                '{item_description}' => $description,
                '{site_name}'        => $site,
                '{item_type}'        => self::detect_type( $schema_json ),
            ) );

            $calls[] = array(
                'prompt' => $prompt,
                'schema' => array(
                    'score'       => 'integer between 0 and 100',
                    'description' => 'short description of the item',
                ),
                'level'  => 'high',
                // Carry original data through for assembly.
                '_meta'  => $item,
            );
        }

        // Fire all ranking calls in parallel.
        $responses = NLWeb_LLM::ask_multi( $calls );

        // Assemble results.
        $ranked = array();
        foreach ( $responses as $i => $resp ) {
            $score = (int) ( $resp['score'] ?? 0 );
            if ( $score < $threshold ) {
                continue;
            }

            list( $url, $schema_json, $name, $site ) = $calls[ $i ]['_meta'];

            $schema_object = json_decode( $schema_json, true );
            if ( is_array( $schema_object ) && isset( $schema_object[0] ) ) {
                $schema_object = $schema_object[0]; // unwrap array if needed
            }

            // Extract @type from schema_object, fallback to 'Item'
            $type = 'Item';
            if ( is_array( $schema_object ) && isset( $schema_object['@type'] ) ) {
                $type = $schema_object['@type'];
            }

            $ranked[] = array(
                '@type'       => $type,
                'url'         => $url,
                'name'        => $name,
                'site'        => $site,
                'siteUrl'     => $site,
                'score'       => $score,
                'description' => $resp['description'] ?? '',
                'grounding'   => array(
                    'schema_object' => $schema_object ?: new stdClass(),
                ),
            );
        }

        // Sort descending by score.
        usort( $ranked, function ( $a, $b ) {
            return $b['score'] - $a['score'];
        } );

        error_log( '[NLWeb] Ranker: Ranked ' . count( $ranked ) . ' items, returning top ' . $max_return );
        if ( ! empty( $ranked ) ) {
            error_log( '[NLWeb] Ranker: Top result: "' . $ranked[0]['name'] . '" (score: ' . $ranked[0]['score'] . ')' );
        }

        return array_slice( $ranked, 0, $max_return );
    }

    /* ----------------------------------------------------------------
     *  Helpers
     * -------------------------------------------------------------- */

    /**
     * Trim a Schema.org JSON string to the essentials for the prompt.
     * Mirrors trim_json() in the Python code — strips images, publishers,
     * and other large fields that waste tokens.
     */
    private static function trim_schema( $json_str ) {

        $obj = json_decode( $json_str, true );
        if ( ! is_array( $obj ) ) {
            return $json_str;  // not valid JSON — send as-is
        }

        // If it's a list, take first element.
        if ( isset( $obj[0] ) ) {
            $obj = $obj[0];
        }

        $skip = array( 'image', 'publisher', 'mainEntityOfPage', 'datePublished', 'dateModified', '@context' );
        foreach ( $skip as $key ) {
            unset( $obj[ $key ] );
        }

        $trimmed = wp_json_encode( $obj );

        // Hard limit to avoid blowing the context window.
        if ( strlen( $trimmed ) > 4000 ) {
            $trimmed = mb_substr( $trimmed, 0, 4000 ) . '...}';
        }

        return $trimmed;
    }

    /**
     * Detect the @type from schema JSON for prompt filling.
     */
    private static function detect_type( $json_str ) {
        $obj = json_decode( $json_str, true );
        if ( is_array( $obj ) ) {
            if ( isset( $obj[0] ) ) {
                $obj = $obj[0];
            }
            return $obj['@type'] ?? 'Article';
        }
        return 'Article';
    }
}

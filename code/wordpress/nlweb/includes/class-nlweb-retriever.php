<?php
/**
 * NLWeb Retriever — uses WP_Query for search and extracts Schema.org JSON
 * from Yoast SEO, RankMath, or builds it from post data.
 *
 * Returns results in the same tuple format as the Python retriever:
 *   [ url, schema_json_string, name, site ]
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NLWeb_Retriever {

    /**
     * Search WordPress content.
     *
     * @param string $query       The search query.
     * @param int    $num_results Max items to return.
     * @return array[]            Each element: [ url, schema_json, name, site ].
     */
    public static function search( $query, $num_results = 20 ) {

        $settings   = NLWeb_Settings::get_all();
        $post_types = $settings['post_types'];

        $wp_query = new WP_Query( array(
            's'              => $query,
            'posts_per_page' => $num_results,
            'post_type'      => $post_types,
            'post_status'    => 'publish',
            'orderby'        => 'relevance',
        ) );

        $results  = array();
        $site     = wp_parse_url( home_url(), PHP_URL_HOST );

        error_log( '[NLWeb] Retriever: WordPress found ' . count( $wp_query->posts ) . ' posts for query: "' . $query . '"' );

        foreach ( $wp_query->posts as $post ) {
            $url    = get_permalink( $post );
            $name   = $post->post_title;
            $schema = self::get_schema_for_post( $post );

            $results[] = array( $url, wp_json_encode( $schema ), $name, $site );
        }

        return $results;
    }

    /* ----------------------------------------------------------------
     *  Schema.org extraction — try Yoast, then RankMath, then build.
     * -------------------------------------------------------------- */

    /**
     * Get Schema.org JSON-LD for a post.
     *
     * @param WP_Post $post
     * @return array   Schema.org object as associative array.
     */
    public static function get_schema_for_post( $post ) {

        // 1. Try Yoast SEO.
        $schema = self::schema_from_yoast( $post );
        if ( $schema ) {
            return $schema;
        }

        // 2. Try RankMath.
        $schema = self::schema_from_rankmath( $post );
        if ( $schema ) {
            return $schema;
        }

        // 3. Build from post data.
        return self::schema_from_post( $post );
    }

    /* ---- Yoast SEO ------------------------------------------------ */

    private static function schema_from_yoast( $post ) {
        // Yoast stores the full graph via its API; check if the class exists.
        if ( ! class_exists( 'WPSEO_Schema_Context' ) && ! class_exists( 'Yoast\\WP\\SEO\\Generators\\Schema_Generator' ) ) {
            return null;
        }

        // Yoast >= 14 exposes wpseo_schema_graph filter, but the simplest
        // approach is to read the cached meta that Yoast stores.
        $meta = get_post_meta( $post->ID, '_yoast_wpseo_schema_page_type', true );
        // If Yoast is active we can build from its helper functions.
        // For reliability, call Yoast's structured data presenter if available.
        if ( function_exists( 'YoastSEO' ) ) {
            try {
                $surface = YoastSEO()->meta->for_post( $post->ID );
                if ( $surface && isset( $surface->schema ) ) {
                    $graph = $surface->schema;
                    // schema is a full @graph — find the main entity.
                    if ( isset( $graph['@graph'] ) && is_array( $graph['@graph'] ) ) {
                        foreach ( $graph['@graph'] as $node ) {
                            $type = $node['@type'] ?? '';
                            if ( in_array( $type, array( 'Article', 'BlogPosting', 'NewsArticle', 'Product', 'Recipe', 'WebPage' ), true ) ) {
                                return $node;
                            }
                        }
                        // Fallback: return the first entity.
                        return $graph['@graph'][0] ?? null;
                    }
                    return $graph;
                }
            } catch ( \Exception $e ) {
                // Yoast internals changed — fall through.
            }
        }

        return null;
    }

    /* ---- RankMath -------------------------------------------------- */

    private static function schema_from_rankmath( $post ) {
        // RankMath stores schema in post meta 'rank_math_schema_{type}'.
        if ( ! class_exists( 'RankMath' ) ) {
            return null;
        }

        $schemas = get_post_meta( $post->ID, 'rank_math_schema_Article', true );
        if ( $schemas && is_array( $schemas ) ) {
            return $schemas;
        }

        // RankMath also stores raw JSON-LD in rank_math_rich_snippet.
        $rich = get_post_meta( $post->ID, 'rank_math_rich_snippet', true );
        if ( $rich ) {
            $decoded = is_string( $rich ) ? json_decode( $rich, true ) : $rich;
            if ( is_array( $decoded ) ) {
                return $decoded;
            }
        }

        return null;
    }

    /* ---- Build from post data -------------------------------------- */

    private static function schema_from_post( $post ) {

        $type = self::detect_schema_type( $post );

        $schema = array(
            '@context'    => 'https://schema.org',
            '@type'       => $type,
            'name'        => $post->post_title,
            'url'         => get_permalink( $post ),
            'description' => self::get_description( $post ),
        );

        // Author.
        $author_name = get_the_author_meta( 'display_name', $post->post_author );
        if ( $author_name ) {
            $schema['author'] = array(
                '@type' => 'Person',
                'name'  => $author_name,
            );
        }

        // Date.
        $schema['datePublished'] = get_the_date( 'c', $post );
        $schema['dateModified']  = get_the_modified_date( 'c', $post );

        // Featured image.
        $thumb = get_the_post_thumbnail_url( $post, 'large' );
        if ( $thumb ) {
            $schema['image'] = $thumb;
        }

        // Categories / tags.
        $cats = wp_get_post_categories( $post->ID, array( 'fields' => 'names' ) );
        if ( $cats ) {
            $schema['articleSection'] = implode( ', ', $cats );
        }

        $tags = wp_get_post_tags( $post->ID, array( 'fields' => 'names' ) );
        if ( $tags ) {
            $schema['keywords'] = implode( ', ', $tags );
        }

        // WooCommerce product enrichment.
        if ( 'product' === $post->post_type && function_exists( 'wc_get_product' ) ) {
            $product = wc_get_product( $post->ID );
            if ( $product ) {
                $schema['@type'] = 'Product';
                $schema['offers'] = array(
                    '@type'         => 'Offer',
                    'price'         => $product->get_price(),
                    'priceCurrency' => get_woocommerce_currency(),
                    'availability'  => $product->is_in_stock()
                        ? 'https://schema.org/InStock'
                        : 'https://schema.org/OutOfStock',
                );
                $schema['sku']   = $product->get_sku();
                $brand = $product->get_attribute( 'brand' );
                if ( $brand ) {
                    $schema['brand'] = array( '@type' => 'Brand', 'name' => $brand );
                }
            }
        }

        return $schema;
    }

    /* ----------------------------------------------------------------
     *  Helpers
     * -------------------------------------------------------------- */

    private static function detect_schema_type( $post ) {
        if ( 'product' === $post->post_type ) {
            return 'Product';
        }
        if ( 'page' === $post->post_type ) {
            return 'WebPage';
        }
        return 'Article';
    }

    private static function get_description( $post ) {
        // Use the excerpt if available, otherwise trim the content.
        if ( ! empty( $post->post_excerpt ) ) {
            return wp_strip_all_tags( $post->post_excerpt );
        }
        return wp_trim_words( wp_strip_all_tags( $post->post_content ), 200, '...' );
    }
}

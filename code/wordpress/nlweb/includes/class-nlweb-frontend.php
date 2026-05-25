<?php
/**
 * NLWeb Frontend — adds conversational search interface to WordPress.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NLWeb_Frontend {

    /**
     * Initialize frontend functionality.
     */
    public static function init() {
        // Add shortcode for search box
        add_shortcode( 'nlweb_search', array( __CLASS__, 'render_search_box' ) );

        // Enqueue scripts and styles
        add_action( 'wp_enqueue_scripts', array( __CLASS__, 'enqueue_assets' ) );
    }

    /**
     * Enqueue frontend assets.
     */
    public static function enqueue_assets() {
        wp_enqueue_style(
            'nlweb-frontend',
            NLWEB_PLUGIN_URL . 'assets/nlweb-frontend.css',
            array(),
            NLWEB_VERSION
        );

        // MCP renderer (loaded first)
        wp_enqueue_script(
            'nlweb-mcp-renderer',
            NLWEB_PLUGIN_URL . 'assets/nlweb-mcp-renderer.js',
            array(),
            NLWEB_VERSION,
            true
        );

        // Main frontend script (depends on MCP renderer)
        wp_enqueue_script(
            'nlweb-frontend',
            NLWEB_PLUGIN_URL . 'assets/nlweb-frontend.js',
            array( 'nlweb-mcp-renderer' ),
            NLWEB_VERSION,
            true
        );

        // Pass REST API URL to JavaScript
        wp_localize_script( 'nlweb-frontend', 'nlwebConfig', array(
            'apiUrl' => rest_url( 'nlweb/v1/ask' ),
            'siteUrl' => get_bloginfo( 'url' ),
        ) );
    }

    /**
     * Render the search box shortcode.
     *
     * Usage: [nlweb_search]
     */
    public static function render_search_box( $atts ) {
        $atts = shortcode_atts( array(
            'placeholder' => 'Message NLWeb...',
            'title'       => 'NLWeb AI Search',
        ), $atts );

        ob_start();
        ?>
        <div class="nlweb-search-container">
            <h2 class="nlweb-search-title"><?php echo esc_html( $atts['title'] ); ?></h2>

            <div id="nlweb-conversation" class="nlweb-conversation">
                <!-- Empty state shown on page load -->
                <div class="nlweb-empty-state">
                    <h3>🎬 Discover Sci-Fi Movies</h3>
                    <p>Ask me anything about science fiction films, actors, directors, or themes.</p>
                    <div class="nlweb-suggestions">
                        <div class="nlweb-suggestion-chip" data-query="time travel movies from the 1980s">🕐 Time Travel 80s</div>
                        <div class="nlweb-suggestion-chip" data-query="alien invasion films from the 1950s">👽 Alien Invasions</div>
                        <div class="nlweb-suggestion-chip" data-query="movies directed by Spielberg">🎥 Spielberg Films</div>
                        <div class="nlweb-suggestion-chip" data-query="dystopian future movies">🌆 Dystopian Futures</div>
                    </div>
                </div>
            </div>

            <div id="nlweb-status" class="nlweb-status"></div>

            <div class="nlweb-input-area">
                <div class="nlweb-search-box">
                    <input
                        type="text"
                        id="nlweb-query-input"
                        class="nlweb-input"
                        placeholder="<?php echo esc_attr( $atts['placeholder'] ); ?>"
                        autocomplete="off"
                    />
                    <button id="nlweb-search-btn" class="nlweb-button">Send</button>
                </div>
            </div>

            <!-- Hidden results area for backward compatibility -->
            <div id="nlweb-results" class="nlweb-results"></div>
        </div>
        <?php
        return ob_get_clean();
    }
}

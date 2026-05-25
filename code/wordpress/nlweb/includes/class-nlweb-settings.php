<?php
/**
 * NLWeb Settings — admin page for configuring the plugin.
 *
 * Stores everything in a single wp_option: 'nlweb_settings'.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class NLWeb_Settings {

    const OPTION_KEY = 'nlweb_settings';
    const PAGE_SLUG  = 'nlweb-settings';

    /* ----------------------------------------------------------------
     *  Defaults
     * -------------------------------------------------------------- */

    public static function defaults() {
        return array(

            /* -- LLM provider ---------------------------------------- */
            'llm_provider'  => 'openai',          // openai | anthropic | gemini
            'api_key'       => '',
            'api_endpoint'  => '',                 // optional — for Azure, custom endpoints
            'model_high'    => 'gpt-4.1-mini',    // used for ranking
            'model_low'     => 'gpt-4.1-mini',    // used for decontextualization

            /* -- Retrieval ------------------------------------------- */
            'post_types'         => array( 'post', 'page' ),
            'max_results'        => 20,                 // items retrieved from WP_Query before ranking
            'enable_query_fanout' => true,              // enable query fanout for complex queries

            /* -- Ranking --------------------------------------------- */
            'num_results_to_return' => 10,
            'score_threshold'       => 51,

            /* -- Prompts (editable) ---------------------------------- */
            'prompt_ranking' =>
                'Assign a score between 0 and 100 to the following item '
                . 'based on how relevant it is to the user\'s question. '
                . 'Use your knowledge from other sources, about the item, to make a judgement. '
                . 'If the score is above 50, provide a short description of the item '
                . 'highlighting the relevance to the user\'s question, without mentioning the user\'s question. '
                . 'If the score is below 75, in the description, include the reason why it is still relevant. '
                . 'The description you generate should be in the same language as the item\'s description.'
                . "\n\n"
                . 'The user\'s question is: "{query}". '
                . 'The item\'s description in schema.org format is "{item_description}".',

            'prompt_decontextualize' =>
                'The user is querying the site {site_name} which has content of type {item_type}. '
                . 'Rewrite the query, incorporating the context of the previous queries and answers. '
                . 'Keep the decontextualized query short and do not reference the site. '
                . "\n\n"
                . 'If the query very clearly does not reference earlier queries, '
                . 'don\'t change the query. Err on the side of incorporating the context of the '
                . 'previous queries. If you are not sure whether this is a brand new query, '
                . 'or follow up, it is likely a follow up. Try your best to incorporate the '
                . 'context from the previous queries.'
                . "\n\n"
                . 'The user\'s query is: {raw_query}. '
                . 'Previous queries were: {previous_queries}.',

            'prompt_summarize' =>
                'Given the following items, summarize the results as an answer to the user\'s question. '
                . 'The user\'s question is: {query}. '
                . 'The items are: {answers}.',
        );
    }

    /* ----------------------------------------------------------------
     *  Getters
     * -------------------------------------------------------------- */

    /**
     * Return the full settings array, with defaults filled in.
     */
    public static function get_all() {
        $saved = get_option( self::OPTION_KEY, array() );
        return wp_parse_args( $saved, self::defaults() );
    }

    /**
     * Return a single setting value.
     */
    public static function get( $key ) {
        $all = self::get_all();
        return $all[ $key ] ?? null;
    }

    /* ----------------------------------------------------------------
     *  Admin menu
     * -------------------------------------------------------------- */

    public static function add_menu_page() {
        add_options_page(
            'NLWeb Settings',
            'NLWeb',
            'manage_options',
            self::PAGE_SLUG,
            array( __CLASS__, 'render_page' )
        );
    }

    /* ----------------------------------------------------------------
     *  Register settings
     * -------------------------------------------------------------- */

    public static function register_settings() {

        register_setting( self::PAGE_SLUG, self::OPTION_KEY, array(
            'type'              => 'array',
            'sanitize_callback' => array( __CLASS__, 'sanitize' ),
        ) );

        /* -- Section: LLM ------------------------------------------- */
        add_settings_section( 'nlweb_llm', 'LLM Provider', null, self::PAGE_SLUG );

        add_settings_field( 'llm_provider', 'Provider', array( __CLASS__, 'field_llm_provider' ),
            self::PAGE_SLUG, 'nlweb_llm' );

        add_settings_field( 'api_key', 'API Key', array( __CLASS__, 'field_api_key' ),
            self::PAGE_SLUG, 'nlweb_llm' );

        add_settings_field( 'api_endpoint', 'API Endpoint (optional)', array( __CLASS__, 'field_api_endpoint' ),
            self::PAGE_SLUG, 'nlweb_llm' );

        add_settings_field( 'model_high', 'Model (ranking)', array( __CLASS__, 'field_model_high' ),
            self::PAGE_SLUG, 'nlweb_llm' );

        add_settings_field( 'model_low', 'Model (decontextualization)', array( __CLASS__, 'field_model_low' ),
            self::PAGE_SLUG, 'nlweb_llm' );

        /* -- Section: Retrieval ------------------------------------- */
        add_settings_section( 'nlweb_retrieval', 'Retrieval', null, self::PAGE_SLUG );

        add_settings_field( 'post_types', 'Post types to search', array( __CLASS__, 'field_post_types' ),
            self::PAGE_SLUG, 'nlweb_retrieval' );

        add_settings_field( 'max_results', 'Max items retrieved before ranking', array( __CLASS__, 'field_max_results' ),
            self::PAGE_SLUG, 'nlweb_retrieval' );

        add_settings_field( 'enable_query_fanout', 'Enable query fanout', array( __CLASS__, 'field_enable_query_fanout' ),
            self::PAGE_SLUG, 'nlweb_retrieval' );

        /* -- Section: Ranking --------------------------------------- */
        add_settings_section( 'nlweb_ranking', 'Ranking', null, self::PAGE_SLUG );

        add_settings_field( 'num_results_to_return', 'Max results returned', array( __CLASS__, 'field_num_results' ),
            self::PAGE_SLUG, 'nlweb_ranking' );

        add_settings_field( 'score_threshold', 'Minimum score (0-100)', array( __CLASS__, 'field_score_threshold' ),
            self::PAGE_SLUG, 'nlweb_ranking' );

        /* -- Section: Prompts --------------------------------------- */
        add_settings_section( 'nlweb_prompts', 'Prompts', array( __CLASS__, 'section_prompts_description' ), self::PAGE_SLUG );

        add_settings_field( 'prompt_ranking', 'Ranking prompt', array( __CLASS__, 'field_prompt_ranking' ),
            self::PAGE_SLUG, 'nlweb_prompts' );

        add_settings_field( 'prompt_decontextualize', 'Decontextualization prompt', array( __CLASS__, 'field_prompt_decontextualize' ),
            self::PAGE_SLUG, 'nlweb_prompts' );

        add_settings_field( 'prompt_summarize', 'Summarization prompt', array( __CLASS__, 'field_prompt_summarize' ),
            self::PAGE_SLUG, 'nlweb_prompts' );
    }

    /* ----------------------------------------------------------------
     *  Sanitize
     * -------------------------------------------------------------- */

    public static function sanitize( $input ) {
        $clean = array();

        $clean['llm_provider']  = sanitize_text_field( $input['llm_provider'] ?? 'openai' );
        $clean['api_key']       = sanitize_text_field( $input['api_key'] ?? '' );
        $clean['api_endpoint']  = esc_url_raw( $input['api_endpoint'] ?? '' );
        $clean['model_high']    = sanitize_text_field( $input['model_high'] ?? '' );
        $clean['model_low']     = sanitize_text_field( $input['model_low'] ?? '' );

        $clean['post_types']         = array_map( 'sanitize_text_field', $input['post_types'] ?? array( 'post', 'page' ) );
        $clean['max_results']        = absint( $input['max_results'] ?? 20 );
        $clean['enable_query_fanout'] = ! empty( $input['enable_query_fanout'] );

        $clean['num_results_to_return'] = absint( $input['num_results_to_return'] ?? 10 );
        $clean['score_threshold']       = absint( $input['score_threshold'] ?? 51 );

        // Prompts — allow most characters but strip tags.
        $clean['prompt_ranking']          = wp_kses_post( $input['prompt_ranking'] ?? '' );
        $clean['prompt_decontextualize']  = wp_kses_post( $input['prompt_decontextualize'] ?? '' );
        $clean['prompt_summarize']        = wp_kses_post( $input['prompt_summarize'] ?? '' );

        return $clean;
    }

    /* ----------------------------------------------------------------
     *  Field renderers
     * -------------------------------------------------------------- */

    public static function field_llm_provider() {
        $val = self::get( 'llm_provider' );
        $providers = array(
            'openai'    => 'OpenAI',
            'anthropic' => 'Anthropic',
            'gemini'    => 'Google Gemini',
        );
        echo '<select name="' . self::OPTION_KEY . '[llm_provider]">';
        foreach ( $providers as $key => $label ) {
            printf( '<option value="%s" %s>%s</option>', esc_attr( $key ), selected( $val, $key, false ), esc_html( $label ) );
        }
        echo '</select>';
    }

    public static function field_api_key() {
        $val = self::get( 'api_key' );
        printf(
            '<input type="password" name="%s[api_key]" value="%s" class="regular-text" autocomplete="off" />',
            self::OPTION_KEY, esc_attr( $val )
        );
    }

    public static function field_api_endpoint() {
        $val = self::get( 'api_endpoint' );
        printf(
            '<input type="url" name="%s[api_endpoint]" value="%s" class="regular-text" placeholder="Leave blank for default" />',
            self::OPTION_KEY, esc_attr( $val )
        );
        echo '<p class="description">Only needed for Azure OpenAI or custom endpoints.</p>';
    }

    public static function field_model_high() {
        $val = self::get( 'model_high' );
        printf(
            '<input type="text" name="%s[model_high]" value="%s" class="regular-text" />',
            self::OPTION_KEY, esc_attr( $val )
        );
        echo '<p class="description">Used for ranking each item. Example: gpt-4.1-mini, claude-3-5-haiku-latest, gemini-2.0-flash</p>';
    }

    public static function field_model_low() {
        $val = self::get( 'model_low' );
        printf(
            '<input type="text" name="%s[model_low]" value="%s" class="regular-text" />',
            self::OPTION_KEY, esc_attr( $val )
        );
        echo '<p class="description">Used for decontextualization. Can be a cheaper/faster model.</p>';
    }

    public static function field_post_types() {
        $selected    = self::get( 'post_types' );
        $post_types  = get_post_types( array( 'public' => true ), 'objects' );
        foreach ( $post_types as $pt ) {
            $checked = in_array( $pt->name, $selected, true ) ? 'checked' : '';
            printf(
                '<label style="margin-right:1em;"><input type="checkbox" name="%s[post_types][]" value="%s" %s /> %s</label>',
                self::OPTION_KEY, esc_attr( $pt->name ), $checked, esc_html( $pt->label )
            );
        }
        echo '<p class="description">Which content types to include in search results.</p>';
    }

    public static function field_max_results() {
        $val = self::get( 'max_results' );
        printf(
            '<input type="number" name="%s[max_results]" value="%d" min="5" max="100" step="1" />',
            self::OPTION_KEY, $val
        );
        echo '<p class="description">How many items to retrieve from WordPress before LLM ranking. More = better results but more LLM calls.</p>';
    }

    public static function field_enable_query_fanout() {
        $val = self::get( 'enable_query_fanout' );
        $checked = $val ? 'checked' : '';
        printf(
            '<label><input type="checkbox" name="%s[enable_query_fanout]" value="1" %s /> Enable</label>',
            self::OPTION_KEY, $checked
        );
        echo '<p class="description">Rewrite complex queries into multiple simpler keyword queries for better retrieval. Uses LLM to generate 1-5 focused queries.</p>';
    }

    public static function field_num_results() {
        $val = self::get( 'num_results_to_return' );
        printf(
            '<input type="number" name="%s[num_results_to_return]" value="%d" min="1" max="50" step="1" />',
            self::OPTION_KEY, $val
        );
    }

    public static function field_score_threshold() {
        $val = self::get( 'score_threshold' );
        printf(
            '<input type="number" name="%s[score_threshold]" value="%d" min="0" max="100" step="1" />',
            self::OPTION_KEY, $val
        );
        echo '<p class="description">Items scoring below this are filtered out.</p>';
    }

    public static function section_prompts_description() {
        echo '<p>Customize the prompts sent to the LLM. '
           . 'Use <code>{query}</code>, <code>{item_description}</code>, <code>{site_name}</code>, '
           . '<code>{item_type}</code>, <code>{raw_query}</code>, <code>{previous_queries}</code>, '
           . '<code>{answers}</code> as placeholders.</p>';
    }

    public static function field_prompt_ranking() {
        $val = self::get( 'prompt_ranking' );
        printf(
            '<textarea name="%s[prompt_ranking]" rows="8" class="large-text code">%s</textarea>',
            self::OPTION_KEY, esc_textarea( $val )
        );
    }

    public static function field_prompt_decontextualize() {
        $val = self::get( 'prompt_decontextualize' );
        printf(
            '<textarea name="%s[prompt_decontextualize]" rows="8" class="large-text code">%s</textarea>',
            self::OPTION_KEY, esc_textarea( $val )
        );
    }

    public static function field_prompt_summarize() {
        $val = self::get( 'prompt_summarize' );
        printf(
            '<textarea name="%s[prompt_summarize]" rows="6" class="large-text code">%s</textarea>',
            self::OPTION_KEY, esc_textarea( $val )
        );
    }

    /* ----------------------------------------------------------------
     *  Page renderer
     * -------------------------------------------------------------- */

    public static function render_page() {
        if ( ! current_user_can( 'manage_options' ) ) {
            return;
        }
        ?>
        <div class="wrap">
            <h1>NLWeb Settings</h1>
            <form method="post" action="options.php">
                <?php
                settings_fields( self::PAGE_SLUG );
                do_settings_sections( self::PAGE_SLUG );
                submit_button();
                ?>
            </form>
            <hr />
            <h2>Endpoints</h2>
            <table class="widefat" style="max-width:700px;">
                <tbody>
                    <tr>
                        <td><strong>Ask (REST)</strong></td>
                        <td><code><?php echo esc_url( rest_url( 'nlweb/v1/ask' ) ); ?>?query=your+question</code></td>
                    </tr>
                    <tr>
                        <td><strong>MCP (JSON-RPC)</strong></td>
                        <td><code><?php echo esc_url( rest_url( 'nlweb/v1/mcp' ) ); ?></code></td>
                    </tr>
                </tbody>
            </table>
        </div>
        <?php
    }
}

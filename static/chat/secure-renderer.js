/**
 * Secure Renderer Wrapper
 * Ensures all content is sanitized before rendering to prevent XSS attacks
 */

class SecureRenderer {
    constructor() {
        // Default DOMPurify configuration for general content
        this.defaultConfig = {
            ALLOWED_TAGS: [
                'b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li',
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'code',
                'blockquote', 'img', 'div', 'span', 'table', 'thead', 'tbody',
                'tr', 'th', 'td', 'caption'
            ],
            ALLOWED_ATTR: ['href', 'src', 'alt', 'class', 'id', 'style', 'title'],
            ALLOW_DATA_ATTR: false,
            FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form'],
            FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover']
        };

        // Extended configuration for chart/visualization content
        this.chartConfig = {
            ...this.defaultConfig,
            ALLOWED_TAGS: [
                ...this.defaultConfig.ALLOWED_TAGS,
                'svg', 'g', 'path', 'rect', 'circle', 'line', 'text', 'polygon',
                'polyline', 'ellipse', 'tspan', 'defs', 'pattern', 'marker',
                'clipPath', 'mask', 'linearGradient', 'radialGradient', 'stop'
            ],
            ALLOWED_ATTR: [
                ...this.defaultConfig.ALLOWED_ATTR,
                'viewBox', 'width', 'height', 'x', 'y', 'dx', 'dy',
                'd', 'points', 'transform', 'fill', 'stroke', 'stroke-width',
                'cx', 'cy', 'r', 'rx', 'ry', 'x1', 'y1', 'x2', 'y2',
                'gradientUnits', 'gradientTransform', 'offset', 'stop-color',
                'stop-opacity', 'marker-start', 'marker-mid', 'marker-end'
            ]
        };

        // Configuration for code blocks (more restrictive)
        this.codeConfig = {
            ALLOWED_TAGS: ['pre', 'code', 'span'],
            ALLOWED_ATTR: ['class'],
            ALLOW_DATA_ATTR: false
        };

        // Cache for existing renderers
        this.renderers = new Map();
    }

    /**
     * Check if DOMPurify is available
     */
    isDOMPurifyAvailable() {
        return typeof window !== 'undefined' && window.DOMPurify;
    }

    /**
     * Sanitize content based on type
     */
    sanitize(content, type = 'default') {
        if (!this.isDOMPurifyAvailable()) {
            return this.escapeHtml(content);
        }

        // Select appropriate configuration
        let config = this.defaultConfig;
        if (type === 'chart' || type === 'chart_result' || type === 'results_map') {
            config = this.chartConfig;
        } else if (type === 'code') {
            config = this.codeConfig;
        }

        // Sanitize with appropriate config
        return window.DOMPurify.sanitize(content, config);
    }

    /**
     * Basic HTML escaping fallback
     */
    escapeHtml(text) {
        if (typeof text !== 'string') {
            text = String(text);
        }
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Wrap an existing renderer with security
     */
    wrapRenderer(renderer, contentType = 'default') {
        return {
            render: (data) => {
                try {
                    // Get raw rendered content
                    let rendered = '';
                    if (typeof renderer === 'function') {
                        rendered = renderer(data);
                    } else if (renderer && typeof renderer.render === 'function') {
                        rendered = renderer.render(data);
                    } else {
                        rendered = String(data);
                    }

                    // Sanitize based on content type
                    return this.sanitize(rendered, contentType);
                } catch (error) {
                    return this.escapeHtml(`Error rendering content: ${error.message}`);
                }
            }
        };
    }

    /**
     * Render text content (always escaped)
     */
    renderText(content) {
        if (typeof content !== 'string') {
            content = JSON.stringify(content, null, 2);
        }
        return this.escapeHtml(content);
    }

    /**
     * Render HTML content (sanitized)
     */
    renderHtml(content, type = 'default') {
        return this.sanitize(content, type);
    }

    /**
     * Render AI response based on message type
     */
    renderAIResponse(message) {
        const messageType = message.message_type || message.type || 'text';
        const content = message.content || '';
        const data = message.content;

        switch (messageType) {
            case 'text':
            case 'summary':
                return this.renderText(content);

            case 'result':
                return this.renderResultBatch(data);

            case 'chart_result':
                return this.renderChart(data);

            case 'results_map':
                return this.renderResultsMap(data);

            case 'code':
                return this.renderCode(content, data);

            case 'error':
                return this.renderError(content || data);

            default:
                // Try to use existing renderer if available
                const renderer = this.getRenderer(messageType);
                if (renderer) {
                    return renderer.render(data || content);
                }
                // Fallback to text
                return this.renderText(content || JSON.stringify(data));
        }
    }

    /**
     * Render result batch (list of results)
     */
    renderResultBatch(results) {
        if (!Array.isArray(results)) {
            return this.renderText('No results');
        }

        const html = `
            <div class="result-batch">
                <div class="result-count">${results.length} results found</div>
                <ul class="result-list">
                    ${results.map(result => `
                        <li class="result-item">
                            ${result.name ? `<strong>${this.escapeHtml(result.name)}</strong>` : ''}
                            ${result.url ? `<a href="${this.escapeHtml(result.url)}" target="_blank" rel="noopener">${this.escapeHtml(result.url)}</a>` : ''}
                            ${result.description ? `<p>${this.escapeHtml(result.description)}</p>` : ''}
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;

        return this.sanitize(html);
    }

    /**
     * Render chart data
     */
    renderChart(chartData) {
        // If we have a JSON renderer available, use it
        const jsonRenderer = this.getRenderer('json');
        if (jsonRenderer && window.JsonRenderer) {
            return jsonRenderer.render(chartData);
        }

        // Otherwise, create a simple representation
        const chartType = chartData.type || 'unknown';
        const title = chartData.title || 'Chart';
        
        const html = `
            <div class="chart-result">
                <h4>${this.escapeHtml(title)}</h4>
                <div class="chart-type">Type: ${this.escapeHtml(chartType)}</div>
                <div class="chart-data">
                    <pre>${this.escapeHtml(JSON.stringify(chartData, null, 2))}</pre>
                </div>
            </div>
        `;

        return this.sanitize(html, 'chart');
    }

    /**
     * Render results map
     */
    renderResultsMap(mapData) {
        const html = `
            <div class="results-map">
                ${Object.entries(mapData).map(([key, value]) => `
                    <div class="map-entry">
                        <strong>${this.escapeHtml(key)}:</strong>
                        <div class="map-value">
                            ${this.renderValue(value)}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        return this.sanitize(html);
    }

    /**
     * Render a value (recursive for nested structures)
     */
    renderValue(value) {
        if (value === null || value === undefined) {
            return '<span class="null">null</span>';
        }

        if (typeof value === 'object') {
            if (Array.isArray(value)) {
                return `<ul>${value.map(v => `<li>${this.renderValue(v)}</li>`).join('')}</ul>`;
            }
            return this.renderResultsMap(value);
        }

        return this.escapeHtml(String(value));
    }

    /**
     * Render code block
     */
    renderCode(code, language = 'plaintext') {
        const html = `
            <pre class="code-block"><code class="language-${this.escapeHtml(language)}">${this.escapeHtml(code)}</code></pre>
        `;
        return this.sanitize(html, 'code');
    }

    /**
     * Render error message
     */
    renderError(error) {
        const errorMessage = typeof error === 'string' ? error : (error.message || 'Unknown error');
        const html = `
            <div class="error-message">
                <span class="error-icon">⚠️</span>
                <span class="error-text">${this.escapeHtml(errorMessage)}</span>
            </div>
        `;
        return this.sanitize(html);
    }

    /**
     * Get or create a wrapped renderer
     */
    getRenderer(type) {
        if (this.renderers.has(type)) {
            return this.renderers.get(type);
        }

        // Try to find existing renderer
        let renderer = null;
        
        // Check for JsonRenderer
        if (type === 'json' && window.JsonRenderer) {
            renderer = this.wrapRenderer(new window.JsonRenderer(), 'default');
        }
        // Check for other type-specific renderers
        else if (window[`${type}Renderer`]) {
            renderer = this.wrapRenderer(new window[`${type}Renderer`](), type);
        }
        // Check for render function in window
        else if (window[`render${type.charAt(0).toUpperCase() + type.slice(1)}`]) {
            renderer = this.wrapRenderer(
                window[`render${type.charAt(0).toUpperCase() + type.slice(1)}`],
                type
            );
        }

        if (renderer) {
            this.renderers.set(type, renderer);
        }

        return renderer;
    }

    /**
     * Register a custom renderer
     */
    registerRenderer(type, renderer, contentType = 'default') {
        this.renderers.set(type, this.wrapRenderer(renderer, contentType));
    }

    /**
     * Main entry point for rendering any content
     */
    render(content, type = 'text') {
        try {
            if (type === 'text' || typeof content === 'string') {
                return this.renderText(content);
            } else if (type === 'html') {
                return this.renderHtml(content);
            } else if (type === 'ai_response' || type === 'ai') {
                return this.renderAIResponse(content);
            } else {
                // Try specific renderer
                const renderer = this.getRenderer(type);
                if (renderer) {
                    return renderer.render(content);
                }
                // Fallback to text
                return this.renderText(content);
            }
        } catch (error) {
            return this.renderError(error);
        }
    }
}

// Export singleton instance
export default new SecureRenderer();

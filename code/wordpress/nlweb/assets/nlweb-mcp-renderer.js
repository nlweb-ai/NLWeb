/**
 * NLWeb MCP Apps Renderer - Vanilla JavaScript Implementation
 *
 * Handles rendering and communication with MCP Apps (SEP-1865)
 * Based on the MCP Apps specification for interactive UI resources.
 */

class MCPAppRenderer {
    constructor(container, options = {}) {
        this.container = container;
        this.iframe = null;
        this.onAction = options.onAction || (() => {});
        this.messageHandlers = new Map();
        // Configure allowed origins for postMessage communication.
        // If not provided, default to the current origin.
        if (Array.isArray(options.allowedOrigins) && options.allowedOrigins.length > 0) {
            this.allowedOrigins = options.allowedOrigins.slice();
        } else if (typeof window !== 'undefined' && window.location && window.location.origin) {
            this.allowedOrigins = [window.location.origin];
        } else {
            this.allowedOrigins = [];
        }
        this.setupMessageListener();
    }

    /**
     * Detect if content is an MCP App
     */
    static isMCPApp(content) {
        if (!content) return false;

        // Check for ui:// URI
        if (content.uri && content.uri.startsWith('ui://')) {
            return true;
        }

        // Check for MCP App MIME type
        if (content.mimeType === 'text/html;profile=mcp-app') {
            return true;
        }

        // Check for @type UIResource
        if (content['@type'] === 'UIResource') {
            return true;
        }

        return false;
    }

    /**
     * Render an MCP App resource
     */
    render(resource) {
        // Clear existing content
        this.container.innerHTML = '';

        // Create sandboxed iframe
        this.iframe = document.createElement('iframe');
        this.iframe.className = 'nlweb-mcp-app-frame';
        this.iframe.setAttribute('sandbox', 'allow-scripts allow-forms allow-same-origin');
        this.iframe.style.width = '100%';
        this.iframe.style.height = '100%';
        this.iframe.style.border = 'none';

        // Get the HTML content
        let htmlContent = resource.html || resource.content || '';

        // If it's a URI, we'd need to fetch it
        if (resource.uri && resource.uri.startsWith('ui://')) {
            this.fetchAndRender(resource.uri);
            return;
        }

        // Inject the bridge script
        const bridgeScript = this.getBridgeScript();
        htmlContent = this.injectBridge(htmlContent, bridgeScript);

        // Load content into iframe
        this.container.appendChild(this.iframe);
        this.iframe.contentDocument.open();
        this.iframe.contentDocument.write(htmlContent);
        this.iframe.contentDocument.close();
    }

    /**
     * Fetch UI resource from uri://
     */
    async fetchAndRender(uri) {
        // In a real implementation, this would fetch from NLWeb
        // For now, show a placeholder
        this.container.innerHTML = `
            <div class="nlweb-mcp-loading">
                <p>Loading interactive app from ${uri}...</p>
            </div>
        `;
    }

    /**
     * Get the bridge script to inject into the iframe
     */
    getBridgeScript() {
        return `
<script>
(function() {
    // MCP Apps Bridge - Communication with parent window
    window.MCPBridge = {
        // Call a tool on the host
        callTool: function(toolName, params) {
            return new Promise((resolve, reject) => {
                const messageId = 'mcp_' + Date.now() + '_' + Math.random();

                window.addEventListener('message', function handler(event) {
                    if (event.data.id === messageId) {
                        window.removeEventListener('message', handler);
                        if (event.data.error) {
                            reject(event.data.error);
                        } else {
                            resolve(event.data.result);
                        }
                    }
                });

                window.parent.postMessage({
                    type: 'mcp-tool-call',
                    id: messageId,
                    toolName: toolName,
                    params: params
                }, '*');
            });
        },

        // Send an intent/message to the host
        sendIntent: function(intent) {
            window.parent.postMessage({
                type: 'mcp-intent',
                intent: intent
            }, '*');
        },

        // Update the app state
        setState: function(state) {
            window.parent.postMessage({
                type: 'mcp-state-update',
                state: state
            }, '*');
        }
    };

    // Notify parent that bridge is ready
    window.parent.postMessage({ type: 'mcp-bridge-ready' }, '*');
})();
</script>
        `;
    }

    /**
     * Inject bridge script into HTML
     */
    injectBridge(html, bridgeScript) {
        // Try to inject before </body>
        if (html.includes('</body>')) {
            return html.replace('</body>', bridgeScript + '</body>');
        }
        // Try to inject before </html>
        if (html.includes('</html>')) {
            return html.replace('</html>', bridgeScript + '</html>');
        }
        // Just append
        return html + bridgeScript;
    }

    /**
     * Setup message listener for iframe communication
     */
    setupMessageListener() {
        window.addEventListener('message', (event) => {
            // Security: Check event.origin and event.source to ensure the message
            // comes from a trusted origin and the expected iframe (if available).
            if (!event || !event.origin) {
                return;
            }

            // If allowedOrigins is configured, require the event.origin to match.
            if (Array.isArray(this.allowedOrigins) && this.allowedOrigins.length > 0) {
                if (!this.allowedOrigins.includes(event.origin)) {
                    return;
                }
            }

            // If we have an iframe reference, ensure the message comes from it.
            if (this.iframe && this.iframe.contentWindow && event.source !== this.iframe.contentWindow) {
                return;
            }

            const { type, id, toolName, params, intent, state } = event.data || {};

            switch (type) {
                case 'mcp-bridge-ready':
                    console.log('[MCP] Bridge ready');
                    break;

                case 'mcp-tool-call':
                    this.handleToolCall(id, toolName, params);
                    break;

                case 'mcp-intent':
                    this.handleIntent(intent);
                    break;

                case 'mcp-state-update':
                    this.handleStateUpdate(state);
                    break;
            }
        });
    }

    /**
     * Handle tool call from iframe
     */
    async handleToolCall(messageId, toolName, params) {
        try {
            const result = await this.onAction({
                type: 'tool',
                payload: { toolName, params }
            });

            // Send result back to iframe
            this.iframe.contentWindow.postMessage({
                id: messageId,
                result: result
            }, '*');
        } catch (error) {
            // Send error back to iframe
            this.iframe.contentWindow.postMessage({
                id: messageId,
                error: error.message
            }, '*');
        }
    }

    /**
     * Handle intent from iframe (e.g., "Explain this chart")
     */
    handleIntent(intent) {
        this.onAction({
            type: 'intent',
            payload: { intent }
        });
    }

    /**
     * Handle state update from iframe
     */
    handleStateUpdate(state) {
        this.onAction({
            type: 'state',
            payload: { state }
        });
    }

    /**
     * Destroy the renderer
     */
    destroy() {
        if (this.iframe) {
            this.iframe.remove();
            this.iframe = null;
        }
    }
}

// Export for use in other scripts
window.MCPAppRenderer = MCPAppRenderer;

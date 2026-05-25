/**
 * NLWeb Frontend JavaScript - ChatGPT Style with MCP Apps Support
 */

(function() {
    'use strict';

    let conversationHistory = [];
    let mcpRenderers = new Map();

    function init() {
        const searchBtn = document.getElementById('nlweb-search-btn');
        const queryInput = document.getElementById('nlweb-query-input');

        if (!searchBtn || !queryInput) {
            return;
        }

        searchBtn.addEventListener('click', handleSearch);
        queryInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSearch();
            }
        });

        // Handle suggestion chips
        document.querySelectorAll('.nlweb-suggestion-chip').forEach(chip => {
            chip.addEventListener('click', function() {
                const query = this.getAttribute('data-query');
                queryInput.value = query;
                handleSearch();
            });
        });
    }

    function handleSearch() {
        const queryInput = document.getElementById('nlweb-query-input');
        const query = queryInput.value.trim();

        if (!query) {
            return;
        }

        // Clear empty state on first query
        const emptyState = document.querySelector('.nlweb-empty-state');
        if (emptyState) {
            emptyState.remove();
        }

        // Add user message to conversation
        addMessage('user', query);

        // Clear input
        queryInput.value = '';

        // Show typing indicator
        showTypingIndicator();

        // Build NLWeb v0.55 request body
        const requestBody = {
            query: {
                text: query
            },
            context: {
                prev: conversationHistory
            },
            prefer: {
                response_format: 'conversational_search',
                mode: 'list'
            },
            meta: {
                version: '0.55'
            }
        };

        // Make API request
        fetch(nlwebConfig.apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        })
            .then(response => response.json())
            .then(data => {
                removeTypingIndicator();
                handleResults(data, query);
                conversationHistory.push(query);
            })
            .catch(error => {
                removeTypingIndicator();
                addMessage('assistant', 'Sorry, there was an error processing your request.');
                console.error('Search error:', error);
            });
    }

    function handleResults(data, query) {
        // Display debug info if present
        if (data.debug && data.debug.length > 0) {
            displayDebugInfo(data.debug);
        }

        // Check if response contains MCP App
        if (MCPAppRenderer && MCPAppRenderer.isMCPApp(data)) {
            renderMCPApp(data);
            return;
        }

        // Handle regular results
        if (!data.results || data.results.length === 0) {
            addMessage('assistant', "I couldn't find any relevant results for your query.");
            return;
        }

        // Extract summary if present
        let summary = null;
        let results = data.results;

        // Check if first result is a SearchSummary
        if (results[0] && results[0]['@type'] === 'SearchSummary') {
            summary = results[0].text;
            results = results.slice(1); // Remove summary from results
        }

        // Build response message
        const message = summary || `Found ${results.length} result${results.length !== 1 ? 's' : ''}:`;

        addMessage('assistant', message, results);
    }

    function addMessage(role, content, results = null) {
        const conversationContainer = document.getElementById('nlweb-conversation');
        const messageEl = document.createElement('div');
        messageEl.className = `nlweb-message nlweb-message-${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'nlweb-message-avatar';
        avatar.textContent = role === 'user' ? 'You' : 'AI';

        const wrapper = document.createElement('div');
        wrapper.className = 'nlweb-message-content-wrapper';

        const messageContent = document.createElement('div');
        messageContent.className = 'nlweb-message-content';
        messageContent.textContent = content;

        wrapper.appendChild(messageContent);

        // Add results if present
        if (results && results.length > 0) {
            const resultsEl = createResultsCards(results);
            wrapper.appendChild(resultsEl);
        }

        messageEl.appendChild(avatar);
        messageEl.appendChild(wrapper);
        conversationContainer.appendChild(messageEl);

        // Scroll to bottom
        conversationContainer.scrollTop = conversationContainer.scrollHeight;
    }

    function createResultsCards(results) {
        const container = document.createElement('div');
        container.className = 'nlweb-message-results';

        results.forEach(result => {
            const card = document.createElement('div');
            card.className = 'nlweb-result-card';

            const title = document.createElement('h4');
            title.className = 'nlweb-result-card-title';
            const link = document.createElement('a');
            link.href = result.url;
            link.target = '_blank';
            link.textContent = result.name || 'Untitled';
            title.appendChild(link);
            card.appendChild(title);

            if (result.description) {
                const desc = document.createElement('p');
                desc.className = 'nlweb-result-card-description';
                desc.textContent = result.description;
                card.appendChild(desc);
            }

            // Add metadata badges
            const meta = document.createElement('div');
            meta.className = 'nlweb-result-card-meta';

            if (result['@type'] && result['@type'] !== 'Item') {
                const typeBadge = document.createElement('span');
                typeBadge.className = 'nlweb-result-badge';
                typeBadge.textContent = result['@type'];
                meta.appendChild(typeBadge);
            }

            if (result.score !== undefined && result.score > 0) {
                const scoreBadge = document.createElement('span');
                scoreBadge.className = 'nlweb-result-badge' + (result.score >= 75 ? ' score-high' : '');
                scoreBadge.textContent = `Score: ${result.score}`;
                meta.appendChild(scoreBadge);
            }

            if (meta.children.length > 0) {
                card.appendChild(meta);
            }

            container.appendChild(card);
        });

        return container;
    }

    function renderMCPApp(appResource) {
        const conversationContainer = document.getElementById('nlweb-conversation');

        const messageEl = document.createElement('div');
        messageEl.className = 'nlweb-message nlweb-message-assistant';

        const avatar = document.createElement('div');
        avatar.className = 'nlweb-message-avatar';
        avatar.textContent = 'AI';

        const wrapper = document.createElement('div');
        wrapper.className = 'nlweb-message-content-wrapper';

        const messageContent = document.createElement('div');
        messageContent.className = 'nlweb-message-content';
        messageContent.textContent = 'Here\'s an interactive view:';

        const appContainer = document.createElement('div');
        appContainer.className = 'nlweb-mcp-app-container';

        wrapper.appendChild(messageContent);
        wrapper.appendChild(appContainer);

        messageEl.appendChild(avatar);
        messageEl.appendChild(wrapper);
        conversationContainer.appendChild(messageEl);

        // Render the MCP App
        if (window.MCPAppRenderer) {
            const renderer = new MCPAppRenderer(appContainer, {
                onAction: handleMCPAction
            });
            renderer.render(appResource);
            mcpRenderers.set(messageEl, renderer);
        }

        conversationContainer.scrollTop = conversationContainer.scrollHeight;
    }

    async function handleMCPAction(action) {
        if (action.type === 'tool') {
            // Forward tool call to NLWeb
            const { toolName, params } = action.payload;

            const response = await fetch(nlwebConfig.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    tool: toolName,
                    params: params
                })
            });

            return await response.json();
        }

        if (action.type === 'intent') {
            // User sent a message from within the MCP App
            const queryInput = document.getElementById('nlweb-query-input');
            queryInput.value = action.payload.intent;
            handleSearch();
        }
    }

    function showTypingIndicator() {
        const conversationContainer = document.getElementById('nlweb-conversation');

        const messageEl = document.createElement('div');
        messageEl.className = 'nlweb-message nlweb-message-assistant';
        messageEl.id = 'nlweb-typing-indicator';

        const avatar = document.createElement('div');
        avatar.className = 'nlweb-message-avatar';
        avatar.textContent = 'AI';

        const wrapper = document.createElement('div');
        wrapper.className = 'nlweb-message-content-wrapper';

        const messageContent = document.createElement('div');
        messageContent.className = 'nlweb-message-content';

        const typing = document.createElement('div');
        typing.className = 'nlweb-typing';
        typing.innerHTML = '<span class="nlweb-typing-dot"></span><span class="nlweb-typing-dot"></span><span class="nlweb-typing-dot"></span>';

        messageContent.appendChild(typing);
        wrapper.appendChild(messageContent);
        messageEl.appendChild(avatar);
        messageEl.appendChild(wrapper);

        conversationContainer.appendChild(messageEl);
        conversationContainer.scrollTop = conversationContainer.scrollHeight;
    }

    function removeTypingIndicator() {
        const indicator = document.getElementById('nlweb-typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    function displayDebugInfo(debugSteps) {
        const conversationContainer = document.getElementById('nlweb-conversation');

        const debugEl = document.createElement('div');
        debugEl.className = 'nlweb-debug-panel';

        const header = document.createElement('div');
        header.className = 'nlweb-debug-header';
        header.innerHTML = '<strong>🔍 Debug Information</strong> <span class="nlweb-debug-toggle">[show/hide]</span>';

        const content = document.createElement('div');
        content.className = 'nlweb-debug-content';
        content.style.display = 'none';

        debugSteps.forEach(step => {
            const stepEl = document.createElement('div');
            stepEl.className = 'nlweb-debug-step';

            const stepTitle = document.createElement('div');
            stepTitle.className = 'nlweb-debug-step-title';
            stepTitle.textContent = step.step;
            stepEl.appendChild(stepTitle);

            const stepData = document.createElement('pre');
            stepData.className = 'nlweb-debug-step-data';
            stepData.textContent = JSON.stringify(step, null, 2);
            stepEl.appendChild(stepData);

            content.appendChild(stepEl);
        });

        header.addEventListener('click', () => {
            if (content.style.display === 'none') {
                content.style.display = 'block';
            } else {
                content.style.display = 'none';
            }
        });

        debugEl.appendChild(header);
        debugEl.appendChild(content);
        conversationContainer.appendChild(debugEl);

        conversationContainer.scrollTop = conversationContainer.scrollHeight;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();

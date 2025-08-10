import eventBus from './event-bus.js';
import stateManager from './state-manager.js';

export class ShareUI {
    constructor() {
        this.participantPanel = null;
        this.currentConversationId = null;
        
        // Bind methods
        this.handleShareClick = this.handleShareClick.bind(this);
        this.handleIncomingShareLink = this.handleIncomingShareLink.bind(this);
    }

    initialize() {
        this.setupEventListeners();
        this.checkForIncomingShareLink();
    }

    setupEventListeners() {
        eventBus.on('ui:shareConversation', (data) => {
            this.handleShareClick(data.conversationId);
        });

        eventBus.on('state:participants', (participants) => {
            this.updateParticipantPanel(participants);
        });

        eventBus.on('state:currentConversation', (conversation) => {
            // Get conversation data from stateManager for sharing
            const currentConv = stateManager.getCurrentConversation();
            this.currentConversationId = currentConv?.id;
            if (currentConv?.participants) {
                this.showParticipantPanel(currentConv.participants);
            }
        });
    }

    generateShareLink(conversationId) {
        const baseUrl = window.location.origin;
        return `${baseUrl}/chat/join/${conversationId}`;
    }

    async handleShareClick(conversationId) {
        // Get conversation from stateManager to ensure we have the latest data
        const conversation = stateManager.conversations.get(conversationId);
        if (!conversation) {
            this.showErrorFeedback('Conversation not found');
            return;
        }
        
        const shareLink = this.generateShareLink(conversationId);
        
        try {
            await this.copyToClipboard(shareLink);
            this.showSuccessFeedback('Share link copied to clipboard!');
        } catch (error) {
            this.showErrorFeedback('Failed to copy link. Please try again.');
        }
    }

    async copyToClipboard(text) {
        // Try modern clipboard API first
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
            // Fallback for older browsers or non-secure contexts
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            try {
                const successful = document.execCommand('copy');
                if (!successful) {
                    throw new Error('Copy command failed');
                }
            } finally {
                document.body.removeChild(textArea);
            }
        }
    }

    showSuccessFeedback(message) {
        this.showFeedback(message, 'success');
    }

    showErrorFeedback(message) {
        this.showFeedback(message, 'error');
    }

    showFeedback(message, type) {
        // Remove any existing feedback
        const existingFeedback = document.querySelector('.share-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }

        // Create feedback element
        const feedback = document.createElement('div');
        feedback.className = `share-feedback share-feedback-${type}`;
        feedback.textContent = message;
        feedback.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${type === 'success' ? '#27ae60' : '#e74c3c'};
            color: white;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 1001;
            animation: slideIn 0.3s ease;
        `;

        // Add animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        `;
        document.head.appendChild(style);

        document.body.appendChild(feedback);

        // Auto-remove after 3 seconds
        setTimeout(() => {
            feedback.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                feedback.remove();
                style.remove();
            }, 300);
        }, 3000);
    }

    checkForIncomingShareLink() {
        // Check if current URL is a join link
        const path = window.location.pathname;
        const joinMatch = path.match(/\/chat\/join\/([a-zA-Z0-9_-]+)/);
        
        if (joinMatch) {
            const conversationId = joinMatch[1];
            // Wait for app initialization
            setTimeout(() => {
                this.handleIncomingShareLink(conversationId);
            }, 100);
        }
    }

    async handleIncomingShareLink(conversationId) {
        if (!conversationId) {
            const path = window.location.pathname;
            const joinMatch = path.match(/\/chat\/join\/([a-zA-Z0-9_-]+)/);
            if (joinMatch) {
                conversationId = joinMatch[1];
            } else {
                return;
            }
        }

        try {
            const shouldJoin = await this.showJoinDialog(conversationId);
            if (shouldJoin) {
                eventBus.emit('ui:joinConversation', { conversationId });
                // Update URL to remove the join path
                window.history.replaceState({}, '', '/chat');
            } else {
                // Redirect to chat home if user cancels
                window.location.href = '/chat';
            }
        } catch (error) {
            this.showErrorFeedback('Failed to join conversation');
        }
    }

    async showJoinDialog(conversationId) {
        return new Promise((resolve) => {
            // Create modal overlay
            const overlay = document.createElement('div');
            overlay.className = 'join-dialog-overlay';
            overlay.innerHTML = `
                <div class="join-dialog">
                    <div class="join-dialog-header">
                        <h2>Join Conversation</h2>
                    </div>
                    <div class="join-dialog-body">
                        <p>You've been invited to join a conversation.</p>
                        <div class="conversation-info">
                            <div class="info-label">Conversation ID:</div>
                            <div class="info-value">${this.escapeHtml(conversationId)}</div>
                        </div>
                        <div class="identity-info" id="join-identity-info">
                            <div class="info-label">Your identity:</div>
                            <div class="info-value">Loading...</div>
                        </div>
                    </div>
                    <div class="join-dialog-actions">
                        <button type="button" class="btn btn-secondary cancel-btn">Cancel</button>
                        <button type="button" class="btn btn-primary join-btn">Join Conversation</button>
                    </div>
                </div>
            `;

            // Add styles
            const style = document.createElement('style');
            style.textContent = `
                .join-dialog-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background-color: rgba(0, 0, 0, 0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                }
                .join-dialog {
                    background: white;
                    border-radius: 0.5rem;
                    padding: 0;
                    width: 90%;
                    max-width: 450px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
                }
                .join-dialog-header {
                    padding: 1.5rem;
                    border-bottom: 1px solid #e1e4e8;
                }
                .join-dialog-header h2 {
                    margin: 0;
                    font-size: 1.5rem;
                }
                .join-dialog-body {
                    padding: 1.5rem;
                }
                .conversation-info, .identity-info {
                    margin-top: 1rem;
                    padding: 1rem;
                    background: #f6f8fa;
                    border-radius: 0.25rem;
                }
                .info-label {
                    font-weight: 600;
                    margin-bottom: 0.25rem;
                }
                .info-value {
                    color: #586069;
                }
                .join-dialog-actions {
                    display: flex;
                    gap: 0.5rem;
                    justify-content: flex-end;
                    padding: 1.5rem;
                    border-top: 1px solid #e1e4e8;
                }
            `;

            document.head.appendChild(style);
            document.body.appendChild(overlay);

            // Load identity info
            eventBus.once('identity:current', (identity) => {
                const identityInfo = overlay.querySelector('#join-identity-info .info-value');
                if (identity) {
                    identityInfo.textContent = `${identity.displayName} (${identity.email})`;
                } else {
                    identityInfo.textContent = 'Not logged in';
                }
            });
            eventBus.emit('ui:requestIdentity');

            // Handle buttons
            const handleJoin = () => {
                cleanup();
                resolve(true);
            };

            const handleCancel = () => {
                cleanup();
                resolve(false);
            };

            const cleanup = () => {
                document.body.removeChild(overlay);
                document.head.removeChild(style);
            };

            // Event listeners
            overlay.querySelector('.join-btn').addEventListener('click', handleJoin);
            overlay.querySelector('.cancel-btn').addEventListener('click', handleCancel);
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) handleCancel();
            });
        });
    }

    showParticipantPanel(participants) {
        if (!participants || participants.length === 0) {
            this.hideParticipantPanel();
            return;
        }

        // Create or update participant panel
        if (!this.participantPanel) {
            this.createParticipantPanel();
        }

        this.updateParticipantList(participants);
        this.participantPanel.style.display = 'block';
    }

    createParticipantPanel() {
        this.participantPanel = document.createElement('div');
        this.participantPanel.className = 'participant-panel';
        this.participantPanel.innerHTML = `
            <div class="participant-header">
                <h3>Participants</h3>
                <button class="btn btn-icon close-participants" title="Close">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
            <div class="participant-list"></div>
        `;

        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .participant-panel {
                position: fixed;
                right: 0;
                top: 0;
                bottom: 0;
                width: 280px;
                background: white;
                border-left: 1px solid #e1e4e8;
                box-shadow: -2px 0 8px rgba(0,0,0,0.1);
                z-index: 100;
                display: none;
                transition: transform 0.3s ease;
            }
            .participant-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 1rem;
                border-bottom: 1px solid #e1e4e8;
            }
            .participant-header h3 {
                margin: 0;
                font-size: 1.125rem;
            }
            .participant-list {
                padding: 1rem;
                overflow-y: auto;
                height: calc(100% - 60px);
            }
            .participant-item {
                display: flex;
                align-items: center;
                padding: 0.75rem;
                margin-bottom: 0.5rem;
                background: #f6f8fa;
                border-radius: 0.25rem;
            }
            .participant-avatar {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: #3498db;
                color: white;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 1rem;
                font-weight: 600;
            }
            .participant-info {
                flex: 1;
            }
            .participant-name {
                font-weight: 600;
                margin-bottom: 0.25rem;
            }
            .participant-email {
                font-size: 0.875rem;
                color: #586069;
            }
            .participant-status {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #28a745;
            }
            @media (max-width: 768px) {
                .participant-panel {
                    width: 100%;
                }
            }
        `;

        document.head.appendChild(style);
        document.body.appendChild(this.participantPanel);

        // Close button handler
        this.participantPanel.querySelector('.close-participants').addEventListener('click', () => {
            this.hideParticipantPanel();
        });
    }

    updateParticipantList(participants) {
        const listContainer = this.participantPanel.querySelector('.participant-list');
        
        listContainer.innerHTML = participants.map(participant => {
            const displayName = this.escapeHtml(participant.displayName || participant.display_name || 'Unknown');
            const email = this.escapeHtml(participant.email || '');
            const initials = this.getInitials(displayName);
            
            return `
                <div class="participant-item">
                    <div class="participant-avatar">${initials}</div>
                    <div class="participant-info">
                        <div class="participant-name">${displayName}</div>
                        ${email ? `<div class="participant-email">${email}</div>` : ''}
                    </div>
                    <div class="participant-status"></div>
                </div>
            `;
        }).join('');
    }

    updateParticipantPanel(participants) {
        if (this.participantPanel) {
            this.updateParticipantList(participants);
        }
    }

    hideParticipantPanel() {
        if (this.participantPanel) {
            this.participantPanel.style.display = 'none';
        }
    }

    getInitials(name) {
        const parts = name.split(' ').filter(p => p.length > 0);
        if (parts.length >= 2) {
            return parts[0][0].toUpperCase() + parts[1][0].toUpperCase();
        }
        return name.substring(0, 2).toUpperCase();
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

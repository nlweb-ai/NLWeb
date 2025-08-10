import eventBus from './event-bus.js';

class IdentityService {
    constructor() {
        this.currentIdentity = null;
    }

    async ensureIdentity() {
        if (this.currentIdentity) {
            return this.currentIdentity;
        }

        // Check for OAuth identity first
        const oauthIdentity = this.getOAuthIdentity();
        if (oauthIdentity) {
            this.currentIdentity = oauthIdentity;
            return this.currentIdentity;
        }

        // Fall back to email identity
        const emailIdentity = this.getEmailIdentity();
        if (emailIdentity) {
            this.currentIdentity = emailIdentity;
            return this.currentIdentity;
        }

        // Prompt for email if no identity exists
        const promptedIdentity = await this.promptForEmail();
        if (promptedIdentity) {
            this.currentIdentity = promptedIdentity;
            this.save();
            return this.currentIdentity;
        }

        return null;
    }

    getOAuthIdentity() {
        try {
            const authToken = sessionStorage.getItem('authToken');
            const userInfo = localStorage.getItem('userInfo');
            
            if (authToken && userInfo) {
                const user = JSON.parse(userInfo);
                return {
                    type: 'oauth',
                    participantId: this.hashEmail(user.email),
                    email: user.email,
                    displayName: user.name || user.email,
                    provider: user.provider,
                    hasAuth: true
                };
            }
        } catch (error) {
        }
        return null;
    }

    getEmailIdentity() {
        try {
            const identity = localStorage.getItem('nlweb_chat_identity');
            if (identity) {
                const parsed = JSON.parse(identity);
                return {
                    type: 'email',
                    participantId: this.hashEmail(parsed.email),
                    email: parsed.email,
                    displayName: parsed.displayName || parsed.email,
                    hasAuth: false
                };
            }
        } catch (error) {
        }
        return null;
    }

    async promptForEmail() {
        return new Promise((resolve) => {
            // Create modal elements
            const overlay = document.createElement('div');
            overlay.className = 'identity-modal-overlay';
            overlay.innerHTML = `
                <div class="identity-modal">
                    <div class="identity-modal-header">
                        <h2>Enter Your Identity</h2>
                        <button type="button" class="btn-close">&times;</button>
                    </div>
                    <form class="identity-form">
                        <div class="form-group">
                            <label for="email-input">Email (required)</label>
                            <input type="email" id="email-input" required>
                            <div class="error-message" id="email-error"></div>
                        </div>
                        <div class="form-group">
                            <label for="name-input">Display Name (optional)</label>
                            <input type="text" id="name-input" placeholder="How others will see you">
                        </div>
                        <div class="form-actions">
                            <button type="button" class="btn btn-secondary cancel-btn">Cancel</button>
                            <button type="submit" class="btn btn-primary">Join Chat</button>
                        </div>
                    </form>
                </div>
            `;

            // Add styles
            const style = document.createElement('style');
            style.textContent = `
                .identity-modal-overlay {
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
                .identity-modal {
                    background: white;
                    border-radius: 0.5rem;
                    padding: 0;
                    width: 90%;
                    max-width: 400px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
                }
                .identity-modal-header {
                    padding: 1rem;
                    border-bottom: 1px solid #e1e4e8;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .identity-modal-header h2 {
                    margin: 0;
                    font-size: 1.25rem;
                }
                .identity-form {
                    padding: 1rem;
                }
                .form-group {
                    margin-bottom: 1rem;
                }
                .form-group label {
                    display: block;
                    margin-bottom: 0.5rem;
                    font-weight: 500;
                }
                .form-group input {
                    width: 100%;
                    padding: 0.75rem;
                    border: 1px solid #dfe4ea;
                    border-radius: 0.25rem;
                    font-size: 1rem;
                    box-sizing: border-box;
                }
                .form-group input:focus {
                    outline: none;
                    border-color: #3498db;
                }
                .error-message {
                    color: #e74c3c;
                    font-size: 0.875rem;
                    margin-top: 0.25rem;
                    min-height: 1rem;
                }
                .form-actions {
                    display: flex;
                    gap: 0.5rem;
                    justify-content: flex-end;
                    margin-top: 1.5rem;
                }
            `;

            document.head.appendChild(style);
            document.body.appendChild(overlay);

            const emailInput = overlay.querySelector('#email-input');
            const nameInput = overlay.querySelector('#name-input');
            const form = overlay.querySelector('.identity-form');
            const errorDiv = overlay.querySelector('#email-error');

            // Focus email input
            emailInput.focus();

            // Handle form submission
            const handleSubmit = (e) => {
                e.preventDefault();
                
                const email = emailInput.value.trim();
                const displayName = nameInput.value.trim();

                if (!email) {
                    errorDiv.textContent = 'Email is required';
                    return;
                }

                if (!this.isValidEmail(email)) {
                    errorDiv.textContent = 'Please enter a valid email';
                    return;
                }

                const identity = {
                    type: 'email',
                    participantId: this.hashEmail(email),
                    email: email,
                    displayName: displayName || email,
                    hasAuth: false
                };

                cleanup();
                resolve(identity);
            };

            // Handle cancel
            const handleCancel = () => {
                cleanup();
                resolve(null);
            };

            // Cleanup function
            const cleanup = () => {
                document.body.removeChild(overlay);
                document.head.removeChild(style);
            };

            // Event listeners
            form.addEventListener('submit', handleSubmit);
            overlay.querySelector('.cancel-btn').addEventListener('click', handleCancel);
            overlay.querySelector('.btn-close').addEventListener('click', handleCancel);
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) handleCancel();
            });

            // Clear error on input
            emailInput.addEventListener('input', () => {
                errorDiv.textContent = '';
            });
        });
    }

    getParticipantInfo() {
        if (!this.currentIdentity) {
            return null;
        }

        return {
            participantId: this.currentIdentity.participantId,
            displayName: this.currentIdentity.displayName,
            email: this.currentIdentity.email,
            type: this.currentIdentity.type,
            hasAuth: this.currentIdentity.hasAuth
        };
    }

    hashEmail(email) {
        // Simple hash for participant ID (not cryptographic)
        let hash = 0;
        for (let i = 0; i < email.length; i++) {
            const char = email.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        return `user_${Math.abs(hash).toString(36)}`;
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    save() {
        if (this.currentIdentity && this.currentIdentity.type === 'email') {
            localStorage.setItem('nlweb_chat_identity', JSON.stringify({
                email: this.currentIdentity.email,
                displayName: this.currentIdentity.displayName
            }));
        }
    }

    clear() {
        this.currentIdentity = null;
        localStorage.removeItem('nlweb_chat_identity');
        // Note: OAuth tokens in sessionStorage will be cleared by logout process
        eventBus.emit('identity:cleared');
    }

    getCurrentIdentity() {
        return this.currentIdentity;
    }
}

// Export singleton instance
export default new IdentityService();

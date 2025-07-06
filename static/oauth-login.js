// OAuth Login Management Module

class OAuthManager {
  constructor() {
    this.authToken = localStorage.getItem('authToken');
    this.userInfo = JSON.parse(localStorage.getItem('userInfo') || 'null');
    this.loginButton = document.getElementById('login-button');
    this.logoutButton = document.getElementById('logout-button');
    this.userInfoDiv = document.getElementById('user-info');
    this.userNameSpan = document.getElementById('user-name');
    this.popupOverlay = document.getElementById('oauth-popup-overlay');
    this.popupCloseButton = document.getElementById('oauth-popup-close');
    
    // OAuth provider buttons
    this.googleButton = document.getElementById('google-login');
    this.facebookButton = document.getElementById('facebook-login');
    this.microsoftButton = document.getElementById('microsoft-login');
    this.githubButton = document.getElementById('github-login');
    
    // OAuth configuration will be loaded from server
    this.oauthConfig = null;
    
    this.initializeEventListeners();
    this.loadOAuthConfig();
    this.updateUIState();
  }
  
  initializeEventListeners() {
    // Login button click
    this.loginButton?.addEventListener('click', () => this.showLoginPopup());
    
    // Logout button click
    this.logoutButton?.addEventListener('click', () => this.logout());
    
    // Close popup
    this.popupCloseButton?.addEventListener('click', () => this.hideLoginPopup());
    this.popupOverlay?.addEventListener('click', (e) => {
      if (e.target === this.popupOverlay) {
        this.hideLoginPopup();
      }
    });
    
    // OAuth provider buttons
    this.googleButton?.addEventListener('click', () => this.loginWithProvider('google'));
    this.facebookButton?.addEventListener('click', () => this.loginWithProvider('facebook'));
    this.microsoftButton?.addEventListener('click', () => this.loginWithProvider('microsoft'));
    this.githubButton?.addEventListener('click', () => this.loginWithProvider('github'));
  }
  
  showLoginPopup() {
    if (this.popupOverlay) {
      this.popupOverlay.style.display = 'flex';
      // Update provider visibility when popup is shown
      this.updateProviderVisibility();
    }
  }
  
  hideLoginPopup() {
    if (this.popupOverlay) {
      this.popupOverlay.style.display = 'none';
    }
  }
  
  async loadOAuthConfig() {
    try {
      const response = await fetch('/api/oauth/config');
      if (response.ok) {
        this.oauthConfig = await response.json();
        console.log('OAuth config loaded:', this.oauthConfig);
        
        // Update UI to show only enabled providers
        this.updateProviderVisibility();
      } else {
        console.error('Failed to load OAuth config');
      }
    } catch (error) {
      console.error('Error loading OAuth config:', error);
    }
  }
  
  updateProviderVisibility() {
    if (!this.oauthConfig) return;
    
    // Hide/show Google login button
    if (this.googleButton) {
      this.googleButton.style.display = this.oauthConfig.google?.enabled ? 'flex' : 'none';
    }
    
    // Hide/show Facebook login button
    if (this.facebookButton) {
      this.facebookButton.style.display = this.oauthConfig.facebook?.enabled ? 'flex' : 'none';
    }
    
    // Hide/show Microsoft login button
    if (this.microsoftButton) {
      this.microsoftButton.style.display = this.oauthConfig.microsoft?.enabled ? 'flex' : 'none';
    }
    
    // Hide/show GitHub login button
    if (this.githubButton) {
      this.githubButton.style.display = this.oauthConfig.github?.enabled ? 'flex' : 'none';
    }
    
    // Check if any provider is enabled
    const anyEnabled = (this.oauthConfig.google?.enabled || 
                       this.oauthConfig.facebook?.enabled || 
                       this.oauthConfig.microsoft?.enabled ||
                       this.oauthConfig.github?.enabled);
    
    // If no providers are enabled, show a message
    const providersContainer = document.querySelector('.oauth-providers');
    if (providersContainer && !anyEnabled) {
      providersContainer.innerHTML = '<p style="text-align: center; color: #666;">No authentication providers are configured. Please contact the administrator.</p>';
    }
  }
  
  async loginWithProvider(provider) {
    try {
      // Wait for OAuth config to load if not already loaded
      if (!this.oauthConfig) {
        await this.loadOAuthConfig();
      }
      
      // Build only the URL for the selected provider
      let authUrl;
      switch(provider) {
        case 'google':
          authUrl = this.buildGoogleAuthUrl();
          break;
        case 'facebook':
          authUrl = this.buildFacebookAuthUrl();
          break;
        case 'microsoft':
          authUrl = this.buildMicrosoftAuthUrl();
          break;
        case 'github':
          authUrl = this.buildGitHubAuthUrl();
          break;
        default:
          console.error(`Unknown provider: ${provider}`);
          return;
      }
      
      if (authUrl && authUrl !== null) {
        // Store provider and state in session storage
        const state = this.generateRandomString(32);
        sessionStorage.setItem('oauth_provider', provider);
        sessionStorage.setItem('oauth_state', state);
        
        // For PKCE flow (more secure), also generate and store code verifier
        if (provider === 'google' || provider === 'microsoft') {
          const codeVerifier = this.generateRandomString(128);
          const codeChallenge = await this.generateCodeChallenge(codeVerifier);
          sessionStorage.setItem('oauth_code_verifier', codeVerifier);
          // Add code_challenge to auth URL for PKCE
        }
        
        // Open OAuth popup window
        const width = 500;
        const height = 600;
        const left = (screen.width - width) / 2;
        const top = (screen.height - height) / 2;
        
        const authWindow = window.open(
          authUrl,
          'oauth_popup',
          `width=${width},height=${height},left=${left},top=${top}`
        );
        
        // Listen for messages from the popup
        const messageHandler = (event) => {
          // Verify origin for security
          if (event.origin !== window.location.origin) return;
          
          if (event.data.type === 'oauth-callback') {
            window.removeEventListener('message', messageHandler);
            this.handleOAuthCallback(event.data);
          }
        };
        
        window.addEventListener('message', messageHandler);
        
        // Also check for window close
        const checkInterval = setInterval(() => {
          try {
            if (authWindow.closed) {
              clearInterval(checkInterval);
              window.removeEventListener('message', messageHandler);
            }
          } catch (e) {
            // Cross-origin error is expected
          }
        }, 1000);
      }
    } catch (error) {
      console.error('OAuth login error:', error);
      alert('Login failed. Please try again.');
    }
  }
  
  generateRandomString(length) {
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let text = '';
    for (let i = 0; i < length; i++) {
      text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
  }
  
  async generateCodeChallenge(verifier) {
    // For PKCE flow - generate SHA256 hash of verifier
    const encoder = new TextEncoder();
    const data = encoder.encode(verifier);
    const digest = await window.crypto.subtle.digest('SHA-256', data);
    return btoa(String.fromCharCode(...new Uint8Array(digest)))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');
  }
  
  async handleOAuthCallback(data) {
    const { token, error, provider, userInfo } = data;
    
    if (error) {
      console.error('OAuth error:', error);
      alert('Login failed: ' + error);
      return;
    }
    
    if (token && userInfo) {
      // Store auth data
      this.authToken = token;
      this.userInfo = userInfo;
      
      localStorage.setItem('authToken', this.authToken);
      localStorage.setItem('userInfo', JSON.stringify(this.userInfo));
      
      // Clear session storage
      sessionStorage.removeItem('oauth_provider');
      sessionStorage.removeItem('oauth_state');
      sessionStorage.removeItem('oauth_code_verifier');
      
      // Update UI
      this.updateUIState();
      this.hideLoginPopup();
      
      // Notify the chat interface
      window.dispatchEvent(new CustomEvent('authStateChanged', {
        detail: {
          isAuthenticated: true,
          authToken: this.authToken,
          userInfo: this.userInfo
        }
      }));
    }
  }
  
  buildGoogleAuthUrl() {
    if (!this.oauthConfig || !this.oauthConfig.google || !this.oauthConfig.google.client_id) {
      console.error('Google OAuth is not configured');
      alert('Google login is not configured. Please contact the administrator.');
      return null;
    }
    
    const clientId = this.oauthConfig.google.client_id;
    const redirectUri = encodeURIComponent(window.location.origin + '/oauth/callback');
    const scope = encodeURIComponent('openid profile email');
    const state = sessionStorage.getItem('oauth_state');
    
    // Using authorization code flow for better security
    return `https://accounts.google.com/o/oauth2/v2/auth?` +
      `client_id=${clientId}&` +
      `redirect_uri=${redirectUri}&` +
      `response_type=code&` +  // Authorization code flow
      `scope=${scope}&` +
      `state=${state}&` +
      `access_type=offline&` +
      `prompt=consent`;
  }
  
  buildFacebookAuthUrl() {
    if (!this.oauthConfig || !this.oauthConfig.facebook || !this.oauthConfig.facebook.app_id) {
      console.error('Facebook OAuth is not configured');
      alert('Facebook login is not configured. Please contact the administrator.');
      return null;
    }
    
    const appId = this.oauthConfig.facebook.app_id;
    const redirectUri = encodeURIComponent(window.location.origin + '/oauth/callback');
    const scope = encodeURIComponent('public_profile,email');
    const state = sessionStorage.getItem('oauth_state');
    
    return `https://www.facebook.com/v18.0/dialog/oauth?` +
      `client_id=${appId}&` +
      `redirect_uri=${redirectUri}&` +
      `scope=${scope}&` +
      `state=${state}&` +
      `response_type=code`; // Authorization code flow
  }
  
  buildMicrosoftAuthUrl() {
    if (!this.oauthConfig || !this.oauthConfig.microsoft || !this.oauthConfig.microsoft.client_id) {
      console.error('Microsoft OAuth is not configured');
      alert('Microsoft login is not configured. Please contact the administrator.');
      return null;
    }
    
    const clientId = this.oauthConfig.microsoft.client_id;
    const redirectUri = encodeURIComponent(window.location.origin + '/oauth/callback');
    const scope = encodeURIComponent('openid profile email');
    const state = sessionStorage.getItem('oauth_state');
    
    return `https://login.microsoftonline.com/common/oauth2/v2.0/authorize?` +
      `client_id=${clientId}&` +
      `redirect_uri=${redirectUri}&` +
      `response_type=code&` + // Authorization code flow
      `scope=${scope}&` +
      `state=${state}&` +
      `response_mode=query`; // Use query for code flow
  }
  
  buildGitHubAuthUrl() {
    if (!this.oauthConfig || !this.oauthConfig.github || !this.oauthConfig.github.client_id) {
      console.error('GitHub OAuth is not configured');
      alert('GitHub login is not configured. Please contact the administrator.');
      return null;
    }
    
    const clientId = this.oauthConfig.github.client_id;
    const redirectUri = encodeURIComponent(window.location.origin + '/oauth/callback');
    const scope = encodeURIComponent('read:user user:email');
    const state = sessionStorage.getItem('oauth_state');
    
    return `https://github.com/login/oauth/authorize?` +
      `client_id=${clientId}&` +
      `redirect_uri=${redirectUri}&` +
      `scope=${scope}&` +
      `state=${state}`;
  }
  
  async checkAuthCompletion() {
    // Check if we received auth token from the callback
    const tempToken = sessionStorage.getItem('temp_auth_token');
    const tempUserInfo = sessionStorage.getItem('temp_user_info');
    
    if (tempToken && tempUserInfo) {
      // Store in localStorage for persistence
      this.authToken = tempToken;
      this.userInfo = JSON.parse(tempUserInfo);
      
      localStorage.setItem('authToken', this.authToken);
      localStorage.setItem('userInfo', JSON.stringify(this.userInfo));
      
      // Clear temporary storage
      sessionStorage.removeItem('temp_auth_token');
      sessionStorage.removeItem('temp_user_info');
      sessionStorage.removeItem('oauth_provider');
      
      // Update UI
      this.updateUIState();
      this.hideLoginPopup();
      
      // Notify the chat interface about the auth update
      window.dispatchEvent(new CustomEvent('authStateChanged', {
        detail: {
          isAuthenticated: true,
          authToken: this.authToken,
          userInfo: this.userInfo
        }
      }));
    }
  }
  
  logout() {
    // Clear auth data
    this.authToken = null;
    this.userInfo = null;
    
    localStorage.removeItem('authToken');
    localStorage.removeItem('userInfo');
    
    // Update UI
    this.updateUIState();
    
    // Notify the chat interface
    window.dispatchEvent(new CustomEvent('authStateChanged', {
      detail: {
        isAuthenticated: false,
        authToken: null,
        userInfo: null
      }
    }));
  }
  
  updateUIState() {
    if (this.authToken && this.userInfo) {
      // User is logged in
      this.loginButton.style.display = 'none';
      this.userInfoDiv.style.display = 'flex';
      
      // Update user name
      const displayName = this.userInfo.name || this.userInfo.email || 'User';
      this.userNameSpan.textContent = displayName;
      
      // Add provider icon as a data attribute for CSS styling
      if (this.userInfo.provider) {
        this.userInfoDiv.setAttribute('data-provider', this.userInfo.provider);
      }
      
      // Add title tooltip
      this.userNameSpan.title = `Logged in via ${this.userInfo.provider || 'OAuth'}`;
    } else {
      // User is not logged in
      this.loginButton.style.display = 'block';
      this.userInfoDiv.style.display = 'none';
      this.userInfoDiv.removeAttribute('data-provider');
    }
  }
  
  getAuthToken() {
    return this.authToken;
  }
  
  isAuthenticated() {
    return !!this.authToken;
  }
}

// Initialize OAuth manager when DOM is ready
let oauthManager;

document.addEventListener('DOMContentLoaded', () => {
  oauthManager = new OAuthManager();
});

// Export for use in other modules
export { oauthManager };
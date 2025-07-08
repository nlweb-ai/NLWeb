# OAuth Authentication Setup Guide for NLWeb

This guide explains how to set up and use OAuth authentication in NLWeb, allowing users to log in with Google, Facebook, Microsoft, or GitHub accounts.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Provider Setup](#provider-setup)
  - [Google OAuth Setup](#google-oauth-setup)
  - [Facebook OAuth Setup](#facebook-oauth-setup)
  - [Microsoft OAuth Setup](#microsoft-oauth-setup)
  - [GitHub OAuth Setup](#github-oauth-setup)
- [NLWeb Configuration](#nlweb-configuration)
- [Testing the Integration](#testing-the-integration)
- [How It Works](#how-it-works)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

## Overview

NLWeb implements OAuth 2.0 authentication using the secure Authorization Code flow. This allows users to authenticate using their existing accounts from major providers without sharing their passwords with NLWeb.

### Key Features
- Secure server-side token exchange
- Support for Google, Facebook, Microsoft, and GitHub
- Session-based authentication
- Automatic token inclusion in API calls
- Clean, modern login UI

## Prerequisites

Before setting up OAuth, ensure you have:
- NLWeb installed and running
- A public URL for your NLWeb instance (or use ngrok for local testing)
- Admin access to create OAuth applications with your chosen providers
- The `httpx` Python package installed (included in requirements.txt)

## Provider Setup

### Google OAuth Setup

1. **Go to Google Cloud Console**
   - Navigate to https://console.cloud.google.com/
   - Create a new project or select an existing one

2. **Enable Google+ API**
   - Go to "APIs & Services" → "Library"
   - Search for "Google+ API" and enable it

3. **Create OAuth Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Choose "Web application"
   - Add authorized redirect URI: `http://yourdomain.com/oauth/callback`
   - Save your Client ID and Client Secret

4. **Configure OAuth Consent Screen**
   - Go to "OAuth consent screen"
   - Fill in required information
   - Add scopes: `openid`, `profile`, `email`

### Facebook OAuth Setup

1. **Go to Facebook Developers**
   - Navigate to https://developers.facebook.com/
   - Click "My Apps" → "Create App"

2. **Choose App Type**
   - Select "Consumer" for general use
   - Fill in app details

3. **Add Facebook Login**
   - In your app dashboard, click "Add Product"
   - Select "Facebook Login" → "Set Up"
   - Choose "Web"

4. **Configure OAuth Settings**
   - Go to "Facebook Login" → "Settings"
   - Add Valid OAuth Redirect URI: `http://yourdomain.com/oauth/callback`
   - Save changes

5. **Get App Credentials**
   - Go to "Settings" → "Basic"
   - Copy your App ID and App Secret

### Microsoft OAuth Setup

1. **Go to Azure Portal**
   - Navigate to https://portal.azure.com/
   - Go to "Azure Active Directory" → "App registrations"

2. **Register New Application**
   - Click "New registration"
   - Name your application
   - Select "Accounts in any organizational directory and personal Microsoft accounts"
   - Add Redirect URI: `http://yourdomain.com/oauth/callback` (Web platform)

3. **Configure Application**
   - Note your Application (client) ID
   - Go to "Certificates & secrets"
   - Create a new client secret
   - Copy the secret value immediately (it won't be shown again)

4. **Set API Permissions**
   - Go to "API permissions"
   - Add permissions: `openid`, `profile`, `email`, `User.Read`
   - Grant admin consent if required

### GitHub OAuth Setup

1. **Go to GitHub Settings**
   - Navigate to https://github.com/settings/developers
   - Click "OAuth Apps" in the left sidebar
   - Click "New OAuth App"

2. **Create OAuth Application**
   - Fill in the application details:
     - **Application name**: Your app name (e.g., "NLWeb Local")
     - **Homepage URL**: `http://yourdomain.com` (or `http://localhost:8000` for local development)
     - **Authorization callback URL**: `http://yourdomain.com/oauth/callback`
   - Click "Register application"

3. **Get Your Credentials**
   - After creating the app, you'll see:
     - **Client ID**: Copy this value
     - **Client Secret**: Click "Generate a new client secret" and copy the value
   - Save these values securely

## NLWeb Configuration

1. **Set Environment Variables**
   
   NLWeb reads OAuth credentials from environment variables. Set these before running NLWeb:

   ```bash
   # Google OAuth
   export GOOGLE_OAUTH_CLIENT_ID="your_google_client_id.apps.googleusercontent.com"
   export GOOGLE_OAUTH_CLIENT_SECRET="your_google_client_secret"
   
   # Facebook OAuth (optional)
   export FACEBOOK_OAUTH_CLIENT_ID="your_facebook_app_id"
   export FACEBOOK_OAUTH_CLIENT_SECRET="your_facebook_app_secret"
   
   # Microsoft OAuth (optional)
   export MICROSOFT_OAUTH_CLIENT_ID="your_microsoft_client_id"
   export MICROSOFT_OAUTH_CLIENT_SECRET="your_microsoft_client_secret"
   
   # GitHub OAuth
   export GITHUB_CLIENT_ID="your_github_client_id"
   export GITHUB_CLIENT_SECRET="your_github_client_secret"
   
   # Session Secret (required)
   # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
   export OAUTH_SESSION_SECRET="your_random_session_secret"
   ```
   
   **Note**: GitHub uses `GITHUB_CLIENT_ID` instead of `GITHUB_OAUTH_CLIENT_ID` for compatibility with existing setups.

2. **Configure OAuth Providers**
   
   The OAuth configuration is managed in `/config/config_oauth.yaml`. This file controls which providers are enabled:

   ```yaml
   providers:
     google:
       enabled: true  # Set to true/false to enable/disable
       client_id_env: GOOGLE_OAUTH_CLIENT_ID
       client_secret_env: GOOGLE_OAUTH_CLIENT_SECRET
       
     facebook:
       enabled: false  # Set to true to enable
       client_id_env: FACEBOOK_OAUTH_CLIENT_ID
       client_secret_env: FACEBOOK_OAUTH_CLIENT_SECRET
       
     microsoft:
       enabled: false  # Set to true to enable
       client_id_env: MICROSOFT_OAUTH_CLIENT_ID
       client_secret_env: MICROSOFT_OAUTH_CLIENT_SECRET
       
     github:
       enabled: true
       client_id_env: GITHUB_CLIENT_ID
       client_secret_env: GITHUB_CLIENT_SECRET
   ```

3. **Add to .gitignore**
   
   If you're modifying the configuration file with actual values, add it to `.gitignore`:
   ```
   config/config_oauth.yaml
   ```

## Testing the Integration

1. **Start NLWeb Server**
   ```bash
   cd /path/to/NLWeb/code/python
   python app-file.py
   ```

2. **Access the Web Interface**
   - Open http://localhost:8000 in your browser
   - Click the "Login" button in the top-right corner
   - You should see login options for enabled providers

3. **Test Authentication Flow**
   - Click on a provider (e.g., "Continue with GitHub")
   - Authorize the application
   - You should be redirected back and logged in

4. **Verify Session**
   - Check that your username appears in the top-right
   - Open browser developer tools and check localStorage for `authToken`

## How It Works

### Authentication Flow

1. User clicks "Login" and selects a provider
2. Browser redirects to provider's OAuth authorization page
3. User authorizes the application
4. Provider redirects to `/oauth/callback` with authorization code
5. NLWeb exchanges the code for an access token (server-side)
6. NLWeb fetches user information using the access token
7. Session is created and user info is stored
8. User is logged in and can access authenticated endpoints

### Session Management

- Sessions are stored in memory by default
- Session tokens are included in API requests via `Authorization` header
- Sessions expire after 24 hours (configurable)

### File Structure

```
NLWeb/
├── config/
│   └── config_oauth.yaml          # OAuth configuration
├── static/
│   ├── oauth-login.js            # OAuth client logic
│   ├── oauth-callback.html       # OAuth callback handler (served at /oauth/callback)
│   └── fp-chat-interface.js      # Updated to include auth token
├── code/python/
│   ├── webserver/
│   │   └── WebServer.py          # OAuth endpoints
│   └── core/
│       └── baseHandler.py        # Auth token validation
```

## Security Considerations

1. **HTTPS in Production**
   - Always use HTTPS in production environments
   - OAuth providers may reject HTTP redirect URIs

2. **Session Security**
   - Use a strong, random session secret
   - Rotate session secrets periodically
   - Consider using Redis for session storage in production

3. **Token Storage**
   - Tokens are stored in localStorage (client-side)
   - Server validates tokens on each request
   - Implement token refresh for long-lived sessions

4. **CORS Configuration**
   - Configure CORS headers appropriately
   - Restrict origins in production

## Troubleshooting

### "OAuth configuration not found for provider: unknown"
- The OAuth callback couldn't identify which provider was used
- Check that sessionStorage is enabled in the browser
- Verify the OAuth state parameter is being passed correctly

### "No OAuth providers showing"
- Check that providers are enabled in `config_oauth.yaml`
- Verify environment variables are set correctly
- Check browser console for configuration loading errors

### "Redirect URI mismatch"
- Ensure the callback URL in your OAuth app matches exactly: `http://yourdomain.com/oauth/callback`
- No trailing slashes or different protocols
- Use the same URL you used when registering the app

### "404 on provider authorization page"
- Verify the client ID is correct
- Check that the OAuth app is not in test/sandbox mode
- Ensure the provider URLs in config are correct

## API Reference

### OAuth Endpoints

#### `GET /api/oauth/config`
Returns client-side OAuth configuration

Response:
```json
{
  "google": {
    "enabled": true,
    "client_id": "...",
    "auth_url": "...",
    "redirect_uri": "http://localhost:8000/oauth/callback"
  },
  "github": {
    "enabled": true,
    "client_id": "...",
    "auth_url": "...",
    "redirect_uri": "http://localhost:8000/oauth/callback"
  }
}
```

#### `POST /api/oauth/token`
Exchanges authorization code for access token

Request:
```json
{
  "code": "authorization_code",
  "provider": "google",
  "redirect_uri": "http://localhost:8000/oauth/callback"
}
```

Response:
```json
{
  "access_token": "...",
  "user_info": {
    "id": "...",
    "email": "user@example.com",
    "name": "User Name",
    "provider": "google"
  }
}
```

### Including Auth Token in API Requests

Once authenticated, include the token in API requests:

```javascript
fetch('/api/endpoint', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('authToken')}`
  }
})
```
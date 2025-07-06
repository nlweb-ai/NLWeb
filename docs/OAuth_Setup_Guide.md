# OAuth Authentication Setup Guide for NLWeb

This guide explains how to set up and use OAuth authentication in NLWeb, allowing users to log in with Google, Facebook, or Microsoft accounts.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Provider Setup](#provider-setup)
  - [Google OAuth Setup](#google-oauth-setup)
  - [Facebook OAuth Setup](#facebook-oauth-setup)
  - [Microsoft OAuth Setup](#microsoft-oauth-setup)
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
- Support for Google, Facebook, and Microsoft
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

## NLWeb Configuration

1. **Create OAuth Configuration File**
   
   Create or edit `/config/config_oauth.yaml`:

   ```yaml
   # OAuth Configuration
   oauth:
     # Google OAuth
     google:
       client_id: "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
       client_secret: "YOUR_GOOGLE_CLIENT_SECRET"
       scopes:
         - "openid"
         - "profile"
         - "email"
     
     # Facebook OAuth
     facebook:
       client_id: "YOUR_FACEBOOK_APP_ID"
       client_secret: "YOUR_FACEBOOK_APP_SECRET"
       scopes:
         - "public_profile"
         - "email"
     
     # Microsoft OAuth
     microsoft:
       client_id: "YOUR_MICROSOFT_CLIENT_ID"
       client_secret: "YOUR_MICROSOFT_CLIENT_SECRET"
       scopes:
         - "openid"
         - "profile"
         - "email"
         - "User.Read"

   # Session configuration
   session:
     # Generate a strong random key (use: python -c "import secrets; print(secrets.token_urlsafe(32))")
     secret_key: "YOUR_RANDOM_SECRET_KEY_HERE"
     # Session expiration in seconds (24 hours)
     token_expiration: 86400
     
   # Authentication settings
   auth:
     # Whether authentication is required for API access
     require_auth: false
     # Endpoints that don't require authentication
     anonymous_endpoints:
       - "/sites"
       - "/who"
     # Enable token validation
     validate_token: true
     # Session storage type (memory, redis, or database)
     session_store: "memory"
   ```

2. **Update Frontend Configuration**
   
   Edit `/static/oauth-login.js` and replace the placeholder client IDs:

   ```javascript
   buildGoogleAuthUrl() {
     const clientId = 'YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com';
     // ... rest of the code
   }
   
   buildFacebookAuthUrl() {
     const appId = 'YOUR_FACEBOOK_APP_ID';
     // ... rest of the code
   }
   
   buildMicrosoftAuthUrl() {
     const clientId = 'YOUR_MICROSOFT_CLIENT_ID';
     // ... rest of the code
   }
   ```

3. **Secure Your Configuration**
   
   Add to `.gitignore`:
   ```
   config/config_oauth.yaml
   ```

## Testing the Integration

1. **Start NLWeb Server**
   ```bash
   cd /path/to/NLWeb/code/python
   python -m webserver.WebServer
   ```

2. **Access the Web Interface**
   - Open http://localhost:8000 in your browser
   - Click the "Login" button in the top right

3. **Test Each Provider**
   - Click on each provider button
   - Complete the authentication flow
   - Verify you're logged in (username appears in header)

4. **Test API Integration**
   - Send a chat message
   - Check server logs to verify auth token is included

## How It Works

### Authentication Flow

1. **User Initiates Login**
   - User clicks "Login" button
   - OAuth popup appears with provider options

2. **Provider Selection**
   - User clicks a provider (Google/Facebook/Microsoft)
   - Browser redirects to provider's OAuth page

3. **User Authorization**
   - User logs in to their account (if needed)
   - User approves permissions for NLWeb

4. **Authorization Code Receipt**
   - Provider redirects to `/oauth/callback` with authorization code
   - Callback page extracts the code from URL

5. **Token Exchange (Server-side)**
   - Callback page sends code to `/api/oauth/token`
   - Server exchanges code for access token with provider
   - Server fetches user information

6. **Session Creation**
   - Server generates secure session token
   - Returns token and user info to client

7. **Client Storage**
   - Client stores token in localStorage
   - Updates UI to show logged-in state

8. **API Authentication**
   - All subsequent API calls include the auth token
   - Server validates token for protected endpoints

### File Structure

```
NLWeb/
├── config/
│   └── config_oauth.yaml          # OAuth configuration
├── static/
│   ├── oauth-login.js            # OAuth client logic
│   ├── oauth-callback.html       # OAuth callback handler
│   └── fp-chat-interface.js      # Updated to include auth token
├── code/python/
│   ├── webserver/
│   │   └── WebServer.py          # OAuth endpoints
│   └── core/
│       └── config.py             # OAuth config loader
```

## Security Considerations

### Best Practices

1. **Use HTTPS in Production**
   - OAuth requires secure connections
   - Never send tokens over unencrypted connections

2. **Secure Configuration Files**
   - Never commit OAuth secrets to version control
   - Use environment variables for production
   - Restrict file permissions

3. **Session Security**
   - Generate strong random session keys
   - Implement token expiration
   - Use secure session storage (Redis/Database)

4. **Token Validation**
   - Validate tokens on every API request
   - Implement token refresh mechanisms
   - Log authentication events

### Production Checklist

- [ ] Replace all placeholder client IDs and secrets
- [ ] Generate a strong session secret key
- [ ] Enable HTTPS
- [ ] Implement proper session storage
- [ ] Set up token validation middleware
- [ ] Configure CORS properly
- [ ] Implement rate limiting
- [ ] Set up monitoring and logging
- [ ] Regular security audits

## Troubleshooting

### Common Issues

1. **"OAuth not configured" Error**
   - Ensure `config_oauth.yaml` exists and is properly formatted
   - Check that client IDs and secrets are set
   - Verify the config file is being loaded

2. **Redirect URI Mismatch**
   - Ensure redirect URI in provider settings matches exactly
   - Include the protocol (http/https)
   - Check for trailing slashes

3. **Token Exchange Fails**
   - Verify client secret is correct
   - Check provider API is enabled
   - Look for detailed error in server logs

4. **User Info Not Retrieved**
   - Ensure required scopes are configured
   - Check API permissions in provider settings
   - Verify access token is valid

### Debug Mode

Enable debug logging in `WebServer.py`:
```python
logger.setLevel(logging.DEBUG)
```

Check logs at:
- `/logs/webserver.log`
- Browser console for client-side errors

## API Reference

### Endpoints

#### `GET /oauth/callback`
OAuth callback endpoint that serves the callback handler page.

#### `POST /api/oauth/token`
Exchanges authorization code for access token.

**Request Body:**
```json
{
  "code": "authorization_code",
  "provider": "google|facebook|microsoft",
  "redirect_uri": "http://yourdomain.com/oauth/callback"
}
```

**Response:**
```json
{
  "access_token": "session_token",
  "token_type": "Bearer",
  "user_info": {
    "id": "user_id",
    "email": "user@example.com",
    "name": "User Name",
    "provider": "google"
  }
}
```

### Client Events

#### `authStateChanged`
Fired when authentication state changes.

```javascript
window.addEventListener('authStateChanged', (event) => {
  console.log('Auth state:', event.detail);
  // event.detail = {
  //   isAuthenticated: true,
  //   authToken: "token",
  //   userInfo: {...}
  // }
});
```

### Including Auth Token

The auth token is automatically included in API calls:
```
GET /ask?query=test&auth_token=YOUR_SESSION_TOKEN
```

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review server logs
3. Check browser console for client errors
4. Ensure all configuration is correct

Remember to keep your OAuth credentials secure and never share them publicly!
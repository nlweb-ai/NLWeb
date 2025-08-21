# OAuth Authentication Setup Guide for NLWeb

This guide explains how to set up and use OAuth authentication in NLWeb, allowing users to log in with Google, Facebook, Microsoft, or GitHub accounts.

## Table of Contents

- [OAuth Authentication Setup Guide for NLWeb](#oauth-authentication-setup-guide-for-nlweb)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
    - [Key Features](#key-features)
  - [Prerequisites](#prerequisites)
  - [Provider Setup](#provider-setup)
    - [Google OAuth Setup](#google-oauth-setup)
    - [Facebook OAuth Setup](#facebook-oauth-setup)
    - [Microsoft OAuth Setup](#microsoft-oauth-setup)
    - [GitHub OAuth Setup](#github-oauth-setup)
  - [NLWeb Configuration](#nlweb-configuration)
  - [Testing the Integration](#testing-the-integration)
  - [How It Works](#how-it-works)
    - [Authentication Flow](#authentication-flow)
    - [Security Features](#security-features)
  - [Troubleshooting](#troubleshooting)
    - ["OAuth configuration not found for provider: unknown"](#oauth-configuration-not-found-for-provider-unknown)
    - [Debug Mode](#debug-mode)
  - [Security Best Practices](#security-best-practices)
  - [Advanced Configuration](#advanced-configuration)
    - [Custom Redirect URIs](#custom-redirect-uris)
    - [Session Storage Options](#session-storage-options)
    - [Rate Limiting](#rate-limiting)

## Overview

NLWeb implements OAuth 2.0 authentication to allow users to log in using their existing accounts from major providers. This provides a secure, convenient way for users to authenticate without creating separate credentials for NLWeb.

### Key Features

- Secure server-side token exchange
- Support for Google, Facebook, Microsoft, and GitHub
- Session-based authentication
- Automatic token inclusion in API calls
- Clean, modern login UI

## Prerequisites

Before setting up OAuth, ensure you have:

- NLWeb installed and running
- A public domain or ngrok for local development (OAuth callbacks require HTTPS in production)
- Admin access to create OAuth applications with your chosen providers

## Provider Setup

### Google OAuth Setup

1. **Go to Google Cloud Console**
   - Navigate to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable Google+ API**
   - Go to "APIs & Services" → "Library"
   - Search for "Google+ API" and enable it

3. **Create OAuth Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth client ID"
   - Choose "Web application"
   - Add authorized redirect URIs:
     - `http://localhost:8000/oauth/callback` (for local development)
     - `https://yourdomain.com/oauth/callback` (for production)

4. **Save Your Credentials**
   - Note your Client ID and Client Secret
   - You'll need these for NLWeb configuration

### Facebook OAuth Setup

1. **Go to Facebook Developers**
   - Navigate to [Facebook Developers](https://developers.facebook.com/)
   - Click "My Apps" → "Create App"

2. **Create a New App**
   - Choose "Consumer" as the app type
   - Fill in the app details

3. **Configure Facebook Login**
   - Add "Facebook Login" product
   - In settings, add Valid OAuth Redirect URIs:
     - `http://localhost:8000/oauth/callback` (for local development)
     - `https://yourdomain.com/oauth/callback` (for production)

4. **Get Your App Credentials**
   - Go to Settings → Basic
   - Note your App ID and App Secret

### Microsoft OAuth Setup

1. **Go to Azure Portal**
   - Navigate to [https://portal.azure.com/](https://portal.azure.com/)
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
   - Navigate to [GitHub Developer Settings](https://github.com/settings/developers)
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
   ```bash

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

   If you're using a `.env` file for environment variables, add it to `.gitignore`:

   ```env
   .env
   ```

## Testing the Integration

1. **Start NLWeb Server**

   ```bash
   cd code/python
   python app-file.py
   ```

2. **Access the Web Interface**
   - Open [http://localhost:8000](http://localhost:8000) in your browser
   - Click the "Login" button in the top-right corner
   - You should see login options for enabled providers

3. **Test OAuth Login**
   - Select your preferred provider
   - Complete the OAuth flow
   - Verify you're logged in (username should appear)

## How It Works

### Authentication Flow

1. **User Initiates Login**
   - User clicks "Login" and selects a provider
   - Browser redirects to provider's OAuth page

2. **Provider Authentication**
   - User logs in to their provider account
   - Provider asks for permission to share data

3. **Authorization Code Exchange**
   - Provider redirects back with authorization code
   - NLWeb exchanges code for access token (server-side)

4. **Session Creation**
   - NLWeb creates a session token
   - Token is stored in browser localStorage
   - User info is displayed in the UI

5. **API Authentication**
   - Session token is automatically included in API requests
   - Server validates token before processing requests

### Security Features

- **Server-side token exchange**: OAuth tokens never exposed to client
- **Secure session tokens**: Cryptographically signed JWTs
- **HTTPS enforcement**: OAuth requires secure connections in production
- **Token expiration**: Sessions expire after 24 hours
- **Environment variables**: Credentials never stored in code

## Troubleshooting

### "OAuth configuration not found for provider: unknown"

- The OAuth callback couldn't identify which provider was used
- Check that sessionStorage is enabled in the browser
- Verify the OAuth state parameter is being passed correctly

1. **"OAuth not configured" Error**
   - Ensure environment variables are set
   - Check that the provider is enabled in config_oauth.yaml
   - Restart the server after setting environment variables

2. **Redirect URI Mismatch**
   - Verify the redirect URI in provider settings matches exactly
   - Include both <http://localhost:8000/oauth/callback> and your production URL

3. **Invalid Client Error**
   - Double-check client ID and secret
   - Ensure no extra spaces in environment variables

4. **CORS Issues**
   - For local development, ensure you're accessing via localhost, not 127.0.0.1
   - Check browser console for specific CORS errors

### Debug Mode

Enable debug logging to troubleshoot OAuth issues:

```python
# In your environment
export OAUTH_DEBUG=true
```

## Security Best Practices

1. **Protect Credentials**
   - Never commit credentials to version control
   - Use environment variables or secure vaults
   - Rotate secrets regularly

2. **Use HTTPS in Production**
   - OAuth providers require HTTPS for production redirects
   - Use proper SSL certificates

3. **Validate Tokens**
   - Always validate session tokens on the server
   - Don't trust client-side user info

4. **Limit Scopes**
   - Only request necessary permissions
   - Review and minimize OAuth scopes

5. **Monitor Usage**
   - Track OAuth login attempts
   - Monitor for suspicious activity
   - Set up alerts for failed authentications

## Advanced Configuration

### Custom Redirect URIs

For deployments behind proxies or with custom domains:

```yaml
# In config_oauth.yaml
redirect_uri_base: "https://custom.domain.com"
```

### Session Storage Options

For production deployments with multiple servers:

```yaml
session:
  session_store: "redis"  # or "database"
  redis_url: "redis://localhost:6379"
```

### Rate Limiting

Protect against brute force attempts:

```yaml
auth:
  rate_limit:
    enabled: true
    max_attempts: 5
    window_minutes: 15
```

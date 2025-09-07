# GitHub OAuth Setup for NLWeb

## Quick Setup Guide

### 1. Create a GitHub OAuth App

1. Go to GitHub Settings: https://github.com/settings/developers
2. Click "OAuth Apps" in the left sidebar
3. Click "New OAuth App"
4. Fill in the application details:
   - **Application name**: NLWeb Local (or any name you prefer)
   - **Homepage URL**: http://localhost:8000
   - **Authorization callback URL**: http://localhost:8000/oauth/callback
5. Click "Register application"

### 2. Get Your Credentials

After creating the app, you'll see:
- **Client ID**: Copy this value
- **Client Secret**: Click "Generate a new client secret" and copy the value

### 3. Set Environment Variables

Add these to your environment before running NLWeb:

```bash
export GITHUB_OAUTH_CLIENT_ID="your_client_id_here"
export GITHUB_OAUTH_CLIENT_SECRET="your_client_secret_here"
export OAUTH_SESSION_SECRET="generate_a_random_secret_key"
```

To generate a session secret:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Update the Frontend (if needed)

The client ID also needs to be in the frontend code. Edit `/static/oauth-login.js`:

```javascript
buildGithubAuthUrl() {
    const clientId = 'your_client_id_here';  // Replace with your actual Client ID
    // ... rest of the code
}
```

### 5. Restart NLWeb

After setting the environment variables, restart your NLWeb server:
```bash
python code/python/app-file.py
```

Now when you click "Login", you should see GitHub as an available provider.

## Troubleshooting

- If you still don't see GitHub as a provider, check the browser console for errors
- Make sure the environment variables are set in the same terminal where you run NLWeb
- The callback URL must match exactly what you configured in GitHub
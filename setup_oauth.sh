#!/bin/bash

# OAuth Setup Script for NLWeb
echo "=== NLWeb OAuth Setup ==="
echo ""
echo "This script will help you set up OAuth for NLWeb."
echo ""

# Check if .env file exists
if [ -f .env ]; then
    echo "Loading existing .env file..."
    source .env
fi

# Function to prompt for a value with a default
prompt_with_default() {
    local prompt_text="$1"
    local default_value="$2"
    local var_name="$3"
    
    if [ -n "$default_value" ]; then
        read -p "$prompt_text [$default_value]: " user_input
        if [ -z "$user_input" ]; then
            eval "$var_name='$default_value'"
        else
            eval "$var_name='$user_input'"
        fi
    else
        read -p "$prompt_text: " user_input
        eval "$var_name='$user_input'"
    fi
}

echo "GitHub OAuth Setup"
echo "-----------------"
echo "1. Go to: https://github.com/settings/developers"
echo "2. Click 'OAuth Apps' then 'New OAuth App'"
echo "3. Use these settings:"
echo "   - Application name: NLWeb Local"
echo "   - Homepage URL: http://localhost:8000"
echo "   - Authorization callback URL: http://localhost:8000/oauth/callback"
echo ""

# Prompt for GitHub credentials
prompt_with_default "Enter your GitHub OAuth Client ID" "$GITHUB_OAUTH_CLIENT_ID" "github_client_id"
prompt_with_default "Enter your GitHub OAuth Client Secret" "$GITHUB_OAUTH_CLIENT_SECRET" "github_client_secret"

# Generate session secret if not exists
if [ -z "$OAUTH_SESSION_SECRET" ]; then
    echo ""
    echo "Generating session secret..."
    session_secret=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
else
    session_secret="$OAUTH_SESSION_SECRET"
fi

# Write to .env file
echo ""
echo "Writing configuration to .env file..."
cat > .env << EOF
# GitHub OAuth
export GITHUB_OAUTH_CLIENT_ID="$github_client_id"
export GITHUB_OAUTH_CLIENT_SECRET="$github_client_secret"

# Session Secret
export OAUTH_SESSION_SECRET="$session_secret"

# Optional: Other OAuth providers
# export GOOGLE_OAUTH_CLIENT_ID=""
# export GOOGLE_OAUTH_CLIENT_SECRET=""
# export FACEBOOK_OAUTH_CLIENT_ID=""
# export FACEBOOK_OAUTH_CLIENT_SECRET=""
# export MICROSOFT_OAUTH_CLIENT_ID=""
# export MICROSOFT_OAUTH_CLIENT_SECRET=""
EOF

echo ""
echo "Configuration saved to .env file!"
echo ""
echo "To use these settings, run:"
echo "  source .env"
echo ""
echo "Then restart your NLWeb server:"
echo "  python code/python/app-file.py"
echo ""
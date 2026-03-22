#!/bin/bash
#
# Sets up a local WordPress instance with sample content and the NLWeb plugin.
# Usage: ./setup.sh
#

set -e
cd "$(dirname "$0")"

echo "=== 1. Starting containers ==="
docker compose up -d

echo "=== 2. Waiting for MySQL to be ready ==="
sleep 10   # MySQL needs a moment on first run

echo "=== 3. Installing WordPress ==="
docker compose run --rm cli wp core install \
  --url="http://localhost:8080" \
  --title="NLWeb Test Site" \
  --admin_user=admin \
  --admin_password=admin \
  --admin_email=admin@example.com \
  --skip-email

echo "=== 4. Importing sample content ==="
# WordPress official theme-unit-test data (~100 posts, pages, comments, categories)
docker compose run --rm cli sh -c '
  curl -sL https://raw.githubusercontent.com/WPTT/theme-unit-test/master/themeunittestdata.wordpress.xml -o /tmp/test-data.xml
  wp plugin install wordpress-importer --activate
  wp import /tmp/test-data.xml --authors=create
'

echo "=== 5. Activating NLWeb plugin ==="
docker compose run --rm cli wp plugin activate nlweb

echo ""
echo "============================================"
echo "  WordPress is running at: http://localhost:8080"
echo "  Admin panel:             http://localhost:8080/wp-admin"
echo "  Username: admin / Password: admin"
echo ""
echo "  NLWeb endpoints:"
echo "    Ask:  http://localhost:8080/wp-json/nlweb/v1/ask?query=hello"
echo "    MCP:  http://localhost:8080/wp-json/nlweb/v1/mcp"
echo ""
echo "  Next step: go to Settings → NLWeb and enter your LLM API key."
echo "============================================"

#!/bin/bash

# Azure Web App deployment script

# Function to display usage
usage() {
    echo "Usage: $0 --app-name <webapp-name> --resource-group <resource-group>"
    echo ""
    echo "Options:"
    echo "  -a, --app-name        Azure Web App name (required)"
    echo "  -r, --resource-group  Azure Resource Group name (required)"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 --app-name myapp --resource-group MyResourceGroup"
    echo "  $0 -a myapp -r MyResourceGroup"
    exit 1
}

# Parse command line arguments
WEBAPP_NAME=""
RESOURCE_GROUP=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--app-name)
            WEBAPP_NAME="$2"
            shift 2
            ;;
        -r|--resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [ -z "$WEBAPP_NAME" ] || [ -z "$RESOURCE_GROUP" ]; then
    echo "Error: Both --app-name and --resource-group are required."
    echo ""
    usage
fi

# Generate zip file name with app name and timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ZIP_FILE="${WEBAPP_NAME}_deploy_${TIMESTAMP}.zip"

echo "========================================="
echo "Azure Web App Deployment Script"
echo "========================================="

# Remove old zip if exists
echo "Removing old deployment zip..."
rm -f $ZIP_FILE

# Create deployment zip
echo "Creating deployment zip file..."
zip -r $ZIP_FILE . \
  -x "*.git*" \
  -x "node_modules/*" \
  -x "docs/*" \
  -x "code/logs/*" \
  -x "*__pycache__/*" \
  -x "*.DS_Store*" \
  -x "*json_with_embeddings/*" \
  -x "*jsonl/*" \
  -x "*htmlcov/*" \
  -x "*.pyc" \
  -x "*.pyo" \
  -x "*.pyd" \
  -x ".Python" \
  -x "env/*" \
  -x "venv/*" \
  -x ".venv/*" \
  -x "*.egg-info/*" \
  -x "dist/*" \
  -x "build/*" \
  -x ".pytest_cache/*" \
  -x ".mypy_cache/*" \
  -x "Dockerfile*" \
  -x "*.log" \
  -x "create_*.sh" \
  -x "deploy_*.sh" \
  -x "install_*.sh" \
  -x "*/mahi/*" \
  -x "*.dedup.txt"

# Show zip file size
echo ""
echo "Deployment zip created: $ZIP_FILE"
ls -lh $ZIP_FILE

# Deploy to Azure
echo ""
echo "Deploying to Azure Web App..."
echo "  Web App: $WEBAPP_NAME"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Zip File: $ZIP_FILE"
echo ""

az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $WEBAPP_NAME \
  --src $ZIP_FILE

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================="
    echo "Deployment Successful!"
    echo "========================================="
    echo "Web App URL: https://${WEBAPP_NAME}.azurewebsites.net"
    echo ""
    echo "To view logs:"
    echo "  az webapp log tail --name $WEBAPP_NAME --resource-group $RESOURCE_GROUP"
    echo ""
    echo "To test the /who endpoint:"
    echo "  curl 'https://${WEBAPP_NAME}.azurewebsites.net/who?query=test'"
else
    echo ""
    echo "Deployment failed. Check the error messages above."
    exit 1
fi
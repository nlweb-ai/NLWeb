#!/bin/bash

# Azure Web App deployment script
echo "========================================="
echo "Azure Web App Deployment Script"
echo "========================================="

WEBAPP_NAME="whotoask"
RESOURCE_GROUP="NLW_rvg"
ZIP_FILE="nlwm.zip"

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
echo "Deployment zip created:"
ls -lh $ZIP_FILE

# Deploy to Azure
echo ""
echo "Deploying to Azure Web App..."
echo "  Web App: $WEBAPP_NAME"
echo "  Resource Group: $RESOURCE_GROUP"
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
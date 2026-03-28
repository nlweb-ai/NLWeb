#!/bin/bash
# Upload ModelRouter scoring data to RunPod instance.
#
# Usage:
#   bash runpod/upload_data.sh <RUNPOD_SSH_HOST>
#
# Example:
#   bash runpod/upload_data.sh root@123.45.67.89
#   bash runpod/upload_data.sh runpod  # if configured in ~/.ssh/config

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <RUNPOD_SSH_HOST>"
    echo "Example: $0 root@123.45.67.89"
    exit 1
fi

REMOTE_HOST="$1"
LOCAL_DATA="$(dirname "$0")/../../ModelRouter/nlweb_router/data"
REMOTE_WORKSPACE="/workspace"

echo "=== Uploading NLWebScorer to RunPod ==="

# Upload project files
echo "Uploading project..."
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='checkpoints' \
    --exclude='data/prepared' --exclude='data/prepared_hard' --exclude='data/prepared_hard_old' \
    --exclude='data/hard_negatives/hard_neg_retrieval.json' \
    --exclude='logs' \
    "$(dirname "$0")/../" "$REMOTE_HOST:$REMOTE_WORKSPACE/NLWebScorer/"

# Upload ModelRouter data
if [ -d "$LOCAL_DATA" ]; then
    echo "Uploading ModelRouter data..."
    ssh "$REMOTE_HOST" "mkdir -p $REMOTE_WORKSPACE/ModelRouter/nlweb_router/data"
    rsync -avz "$LOCAL_DATA/" "$REMOTE_HOST:$REMOTE_WORKSPACE/ModelRouter/nlweb_router/data/"
else
    echo "WARNING: ModelRouter data not found at $LOCAL_DATA"
    echo "  You'll need to upload scores_azure_oai_gpt-4.1.json manually."
fi

echo ""
echo "=== Upload Complete ==="
echo ""
echo "Next: ssh into RunPod and run:"
echo "  cd $REMOTE_WORKSPACE/NLWebScorer"
echo "  bash runpod/setup.sh"
echo "  bash runpod/run_finetune.sh"

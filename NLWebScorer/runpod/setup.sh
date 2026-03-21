#!/bin/bash
# NLWebScorer RunPod Setup Script
#
# Run this after launching a RunPod instance with a GPU pod.
# Assumes Ubuntu + CUDA + Python 3.10+ are already available (standard RunPod template).
#
# Usage:
#   # SSH into your RunPod instance, then:
#   bash setup.sh
#
# If using RunPod's "pytorch" template, CUDA and PyTorch are pre-installed.

set -euo pipefail

WORKSPACE="/workspace"
PROJECT_DIR="$WORKSPACE/NLWebScorer"

echo "=== NLWebScorer RunPod Setup ==="

# 1. System packages
echo "Installing system dependencies..."
apt-get update -qq && apt-get install -y -qq git wget curl vim > /dev/null 2>&1

# 2. Clone or update project
if [ -d "$PROJECT_DIR" ]; then
    echo "Project directory exists, pulling latest..."
    cd "$PROJECT_DIR" && git pull 2>/dev/null || true
else
    echo "Please upload or clone NLWebScorer to $PROJECT_DIR"
    echo "  e.g.: rsync -avz ./NLWebScorer/ runpod:$PROJECT_DIR/"
    exit 1
fi

cd "$PROJECT_DIR"

# 3. Install Python dependencies
echo "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

# 4. Verify GPU
echo ""
echo "=== GPU Check ==="
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB')
"

# 5. Verify ModernBERT download
echo ""
echo "=== Downloading ModernBERT ==="
python -c "
from transformers import AutoTokenizer, AutoModel
print('Downloading answerdotai/ModernBERT-base...')
AutoTokenizer.from_pretrained('answerdotai/ModernBERT-base')
AutoModel.from_pretrained('answerdotai/ModernBERT-base')
print('Done.')
"

# 6. Create output directories
mkdir -p checkpoints/modernbert checkpoints/gam data/prepared

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Upload data: scp ModelRouter/nlweb_router/data/*.json runpod:$PROJECT_DIR/../ModelRouter/nlweb_router/data/"
echo "  2. Prepare data:  python -m data.prepare_data"
echo "  3. Train BERT:    bash runpod/run_finetune.sh"
echo "  4. Train GAM:     python -m training.train_gam"

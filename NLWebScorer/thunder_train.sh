#!/bin/bash
# Upload to Thunder instance and start training.
# Usage: bash thunder_train.sh
set -euo pipefail

INSTANCE_ID=0
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Step 1: Creating tarball ==="
cd "$LOCAL_DIR"
tar czf /tmp/nlwebscorer.tar.gz \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='checkpoints' \
  --exclude='data/prepared' --exclude='data/prepared_hard' --exclude='data/prepared_hard_old' \
  --exclude='data/hard_negatives/hard_neg_retrieval.json' --exclude='logs' .
ls -lh /tmp/nlwebscorer.tar.gz

echo ""
echo "=== Step 2: Uploading to Thunder instance $INSTANCE_ID ==="
tnr scp /tmp/nlwebscorer.tar.gz $INSTANCE_ID:/workspace/

echo ""
echo "=== Step 3: Extracting and starting training ==="
tnr connect $INSTANCE_ID -- bash -c '
  cd /workspace && mkdir -p NLWebScorer && cd NLWebScorer && tar xzf ../nlwebscorer.tar.gz

  # Fix pip on Python 3.12 (old pip 22.0.2 crashes with pkgutil.ImpImporter error)
  python3 -m ensurepip --upgrade 2>/dev/null || true
  python3 -m pip install --upgrade pip 2>&1 | tail -3

  python3 -m pip install torch transformers scipy pyyaml 2>&1 | tail -5
  nohup bash runpod/run_finetune.sh > /workspace/training.log 2>&1 &
  echo "Training started in background. PID: $!"
  echo "Monitor with: tail -f /workspace/training.log"
'

echo ""
echo "=== Done ==="
echo "To monitor: tnr connect $INSTANCE_ID -- tail -f /workspace/training.log"
echo "To check GPU: tnr connect $INSTANCE_ID -- nvidia-smi"

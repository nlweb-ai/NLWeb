#!/bin/bash
# Run BERT training on RunPod A100
set -e

cd /workspace/NLWebScorer

# Install dependencies
pip install -q torch transformers scipy pyyaml

# Train
python -u -m training.train_modernbert \
    --config config/training_config_cuda.yaml \
    --pure-text \
    2>&1 | tee training_bert_1024_cuda.log

echo "Training complete. Extracting results..."
ls -lh checkpoints/modernbert_large_pure/

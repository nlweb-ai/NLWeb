#!/bin/bash
# NLWebScorer Full Training Pipeline on RunPod
#
# Usage:
#   cd /workspace/NLWebScorer
#   bash runpod/run_finetune.sh [--phase1-only | --phase2-only | --data-only]
#
# Phases:
#   1. Data preparation (ModelRouter → training format)
#   2. ModernBERT fine-tuning (Phase 1)
#   3. Neural GAM training (Phase 2)

set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"
CONFIG="config/training_config_cuda.yaml"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

PHASE="${1:-all}"

echo "=========================================="
echo "  NLWebScorer Training Pipeline"
echo "  $(date)"
echo "  Phase: $PHASE"
echo "=========================================="

# Check GPU
python -c "
import torch
assert torch.cuda.is_available(), 'No GPU found!'
print(f'GPU: {torch.cuda.get_device_name(0)}')
print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB')
"

# Phase 0: Data preparation
if [[ "$PHASE" == "all" || "$PHASE" == "--data-only" ]]; then
    echo ""
    echo "=== Phase 0: Preparing training data ==="
    python -m data.prepare_data --config "$CONFIG" 2>&1 | tee "$LOG_DIR/prepare_data.log"

    if [[ "$PHASE" == "--data-only" ]]; then
        echo "Data preparation complete."
        exit 0
    fi
fi

# Phase 1: ModernBERT fine-tuning
if [[ "$PHASE" == "all" || "$PHASE" == "--phase1-only" ]]; then
    echo ""
    echo "=== Phase 1: Fine-tuning ModernBERT ==="
    echo "Start: $(date)"

    python -m training.train_modernbert --config "$CONFIG" 2>&1 | tee "$LOG_DIR/train_modernbert.log"

    echo "Phase 1 complete: $(date)"

    if [[ "$PHASE" == "--phase1-only" ]]; then
        exit 0
    fi
fi

# Phase 2: Neural GAM training
if [[ "$PHASE" == "all" || "$PHASE" == "--phase2-only" ]]; then
    echo ""
    echo "=== Phase 2: Training Neural GAM ==="
    echo "Start: $(date)"

    python -m training.train_rubric_gam --config "$CONFIG" 2>&1 | tee "$LOG_DIR/train_rubric_gam.log"

    echo "Phase 2 complete: $(date)"
fi

# Evaluate
echo ""
echo "=== Final Evaluation ==="
python -m training.evaluate --config "$CONFIG" 2>&1 | tee "$LOG_DIR/evaluate.log"

echo ""
echo "=========================================="
echo "  Training complete: $(date)"
echo "  Checkpoints: $PROJECT_DIR/checkpoints/"
echo "  Logs: $LOG_DIR/"
echo "=========================================="

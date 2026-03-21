#!/bin/bash
# Full pipeline: Pure-text ModernBERT-large + Rubric GAM (3 variants)
#
# Usage:
#   cd NLWebScorer
#   bash run_rubric_gam_pipeline.sh
#
# This takes ~6-7 hours total on MPS:
#   - BERT training: ~5.5h (5 epochs × ~65 min)
#   - Embedding extraction: ~30 min
#   - GAM training (3 variants): ~10 min total

set -e

# Ensure pyenv shims are on PATH
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/shims:$PYENV_ROOT/bin:$PATH"

PYTHON="/Users/rvguha/.pyenv/versions/3.12.7/bin/python"
CONFIG="config/training_config_rubric_gam.yaml"

echo "=============================================="
echo "Step 1: Prepare data (filtering noisy queries)"
echo "=============================================="
echo "Removing query-site pairs with max_score < 0.5"
$PYTHON -u -m data.prepare_data \
    --config "$CONFIG" \
    --difficulty 4,5 \
    --holdout-dir data/holdout \
    --output-dir data/prepared_hard \
    --min-query-max-score 0.5

echo ""
echo "=============================================="
echo "Step 2: Train pure-text ModernBERT-large"
echo "=============================================="
echo "This trains BERT without rubric features in the head,"
echo "then extracts [CLS] embeddings for GAM training."
echo ""
$PYTHON -u -m training.train_modernbert \
    --config "$CONFIG" \
    --pure-text \
    2>&1 | tee training_pure_bert.log

echo ""
echo "=============================================="
echo "Step 3: Train Rubric GAM — Additive"
echo "=============================================="
$PYTHON -u -m training.train_rubric_gam \
    --config "$CONFIG" \
    --mode additive \
    2>&1 | tee rubric_gam_additive.log

echo ""
echo "=============================================="
echo "Step 4: Train Rubric GAM — Gated"
echo "=============================================="
$PYTHON -u -m training.train_rubric_gam \
    --config "$CONFIG" \
    --mode gated \
    2>&1 | tee rubric_gam_gated.log

echo ""
echo "=============================================="
echo "Step 5: Train Rubric GAM — Interaction"
echo "=============================================="
$PYTHON -u -m training.train_rubric_gam \
    --config "$CONFIG" \
    --mode interaction \
    2>&1 | tee rubric_gam_interaction.log

echo ""
echo "=============================================="
echo "DONE — Compare results in the log files above"
echo "=============================================="
echo ""
echo "Key files:"
echo "  BERT:        checkpoints/modernbert_large_pure/best_model.pt"
echo "  GAM additive:    checkpoints/rubric_gam/additive/best_rubric_gam.pt"
echo "  GAM gated:       checkpoints/rubric_gam/gated/best_rubric_gam.pt"
echo "  GAM interaction: checkpoints/rubric_gam/interaction/best_rubric_gam.pt"

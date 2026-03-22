#!/bin/bash
# Long-running training data collection for NLWebScorer.
# Runs all three phases sequentially. Safe to Ctrl-C anytime — auto-resumes.
#
# Usage:
#   cd /Users/rvguha/code/Conv2/NLWeb/NLWebScorer
#   source /Users/rvguha/code/Conv2/NLWeb/AskAgent/set_keys.sh
#   nohup bash data/run_data_collection.sh > data/collection.log 2>&1 &
#   tail -f data/collection.log

set -e
cd "$(dirname "$0")/.."

PYTHON=/Users/rvguha/v2/bin/python

echo "============================================================"
echo "NLWebScorer Training Data Collection"
echo "Started: $(date)"
echo "============================================================"

# ── Phase 1: Synthetic queries (20 per site × 16 sites = 320 queries) ──
echo ""
echo "============================================================"
echo "PHASE 1: Synthetic queries — 20 per site"
echo "============================================================"
$PYTHON -m data.generate_hard_negatives --generate-queries 20

# ── Phase 2: More synthetic queries (another 30 per site = 480 more) ──
echo ""
echo "============================================================"
echo "PHASE 2: Synthetic queries — 30 more per site"
echo "============================================================"
$PYTHON -m data.generate_hard_negatives --generate-queries 30

# ── Phase 3: Hard negatives from existing complex queries (≥5 words) ──
echo ""
echo "============================================================"
echo "PHASE 3: Hard negatives from existing queries (>=5 words)"
echo "============================================================"
$PYTHON -m data.generate_hard_negatives --total 428

echo ""
echo "============================================================"
echo "ALL PHASES COMPLETE: $(date)"
echo "============================================================"

# Show final stats
$PYTHON -c "
import json
from pathlib import Path

scores_path = Path('data/hard_negatives/hard_neg_scores.json')
if not scores_path.exists():
    print('No scores file found')
    exit()

with open(scores_path) as f:
    data = json.load(f)

all_scores = [item['score'] for e in data for item in e.get('items', []) if item.get('score', -1) >= 0]
print(f'Total queries: {len(data)}')
print(f'Total scored items: {len(all_scores)}')
print(f'\nDecile distribution:')
for lo in range(0, 100, 10):
    hi = lo + 10
    n = sum(1 for s in all_scores if lo <= s < hi)
    print(f'  {lo:>3}-{hi:<3}: {n:>6} ({n/len(all_scores)*100:>5.1f}%)')
"

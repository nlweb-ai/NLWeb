#!/bin/bash
# Wait for ModernBERT-large training to finish, then fit rubric weights

echo "Waiting for training PID 25731 to finish..."
while kill -0 25731 2>/dev/null; do
    sleep 60
done

echo ""
echo "Training complete! Log tail:"
tail -20 training_large.log

echo ""
echo "=========================================="
echo "Running rubric weight fitting..."
echo "=========================================="
python -u -m training.fit_rubric_weights --config config/training_config_large.yaml 2>&1 | tee rubric_weights.log

echo ""
echo "All done!"

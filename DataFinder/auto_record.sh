#!/bin/bash
# Automated recording script for DataFinder demo
# This will start screen recording and run the demo

echo "🎬 DataFinder Auto-Recording Script"
echo "===================================="
echo ""
echo "This will:"
echo "  1. Start screen recording using macOS built-in recorder"
echo "  2. Wait 3 seconds"
echo "  3. Run the demo"
echo "  4. Stop recording when done"
echo ""
echo "The video will be saved to ~/Desktop/DataFinder-Demo.mov"
echo ""
read -p "Press ENTER to start recording... "

# Start screen recording in background
echo "Starting recording..."
screencapture -v -T 3 ~/Desktop/DataFinder-Demo.mov &
RECORDING_PID=$!

# Wait for countdown
sleep 4

# Clear screen and run demo
clear
python simple_demo.py

# Recording should auto-stop when we're done
# If not, user can press Ctrl+C manually in the recording UI

echo ""
echo "✅ Demo complete!"
echo "Video saved to: ~/Desktop/DataFinder-Demo.mov"

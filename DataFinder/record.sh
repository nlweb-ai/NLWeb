#!/bin/bash
# Screen recording launcher for DataFinder demo

echo "🎬 DataFinder Demo Recording Setup"
echo "===================================="
echo ""
echo "SETUP INSTRUCTIONS:"
echo ""
echo "1. Terminal Setup:"
echo "   - Increase font size: Cmd+Plus (recommend 16-18pt)"
echo "   - Use full screen: Cmd+Ctrl+F"
echo "   - Clear scrollback: Cmd+K"
echo ""
echo "2. Start Screen Recording:"
echo "   - Press Cmd+Shift+5"
echo "   - Select 'Record Entire Screen' or 'Record Selected Window'"
echo "   - Click Options > Show Mouse Clicks (optional)"
echo "   - Click Record button"
echo ""
echo "3. When ready, come back to this terminal and press ENTER"
echo ""
read -p "Press ENTER when recording has started... "

# Small delay to switch back
sleep 2

# Clear screen and run
clear
python simple_demo.py

echo ""
echo "✅ Demo complete!"
echo ""
echo "Stop the recording (click Stop in menu bar or press Cmd+Ctrl+Esc)"
echo "Video will be saved to ~/Desktop/"
echo ""

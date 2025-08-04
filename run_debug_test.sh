#!/bin/bash

# Start server and capture output
echo "Starting server..."
python scripts/run_tests_with_server.py --no-server &
SERVER_PID=$!

# Give server time to start
sleep 3

# Run debug script
echo "Running debug test..."
python test_participant_debug.py

# Kill server
kill $SERVER_PID 2>/dev/null

echo "Done"
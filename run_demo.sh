#!/bin/bash
# Quick demo script

echo "🎬 Starting Hackathon Demo..."
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

echo ""
echo "Starting components in 3 seconds..."
sleep 3

# Start anomaly detector in background
echo "1️⃣ Starting Anomaly Detector..."
python3 anomaly_detector.py &
DETECTOR_PID=$!
sleep 2

# Start simulator with anomaly scheduled
echo "2️⃣ Starting Device Simulator (anomaly at iteration 15)..."
python3 simulator.py --device-id pump1 --anomaly-at 15 --duration 40 &
SIMULATOR_PID=$!

echo ""
echo "✅ Demo running!"
echo ""
echo "📊 Monitor alerts in another terminal:"
echo "   tedge mqtt sub 'te/device/+/e/ai_alert'"
echo ""
echo "Press Ctrl+C to stop..."

# Cleanup on exit
trap "kill $DETECTOR_PID $SIMULATOR_PID 2>/dev/null; echo ''; echo '🛑 Demo stopped'" EXIT

# Wait
wait
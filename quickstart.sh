#!/bin/bash
# Quick Start Script for Expense AI Assistant

set -e

echo "================================"
echo "Expense AI Assistant - Quick Start"
echo "================================"
echo ""

# Check Python version
echo "✓ Checking Python..."
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "  Found Python $python_version"

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found!"
    exit 1
fi

# Install dependencies
echo ""
echo "✓ Installing dependencies..."
pip install -q -r requirements.txt
echo "  Dependencies installed"

# Get Groq API Key
echo ""
echo "⚠️  Groq API Key:"
echo "  Get your free key at: https://console.groq.com"
read -p "  Enter your Groq API Key (or press Enter to skip): " GROQ_KEY

if [ -n "$GROQ_KEY" ]; then
    export GROQ_API_KEY="$GROQ_KEY"
    echo "  ✓ API key set"
fi

# Start backend in background
echo ""
echo "🚀 Starting backend..."
cd src
python -m uvicorn main:app --host 0.0.0.0 --port 8000 > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..
echo "  Backend started (PID: $BACKEND_PID)"

# Wait for backend to be ready
echo "  Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "  ✓ Backend is ready!"
        break
    fi
    sleep 1
done

# Start Streamlit
echo ""
echo "🎨 Starting Streamlit frontend..."
echo "  Opening http://localhost:8501 in your browser..."
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

cd src
streamlit run streamlit_app.py --server.port=8501
cd ..

# Cleanup on exit
trap "kill $BACKEND_PID 2>/dev/null; echo ''; echo '✓ Services stopped'" EXIT
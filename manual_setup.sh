#!/bin/bash

# Echo App - Manual Run Script
# This script starts the backend and frontend without Docker
# Prerequisites: Node.js 20+, Python 3.12+, uv

set -e

echo "🚀 Starting Echo App (Manual Mode)..."
echo ""

# Check prerequisites
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 20+ and try again."
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install uv (https://docs.astral.sh/uv/) and try again."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if backend .env exists
if [ ! -f "$SCRIPT_DIR/backend/.env" ]; then
    echo "⚠️  backend/.env not found. Copying from .env.example..."
    cp "$SCRIPT_DIR/backend/.env.example" "$SCRIPT_DIR/backend/.env"
    echo "📝 Please configure Cosmos DB credentials in backend/.env"
fi

# Start backend
echo "📦 Installing backend dependencies..."
cd "$SCRIPT_DIR/backend"
uv sync

echo "🔧 Starting backend on http://localhost:8000..."
uv run uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "📦 Installing frontend dependencies..."
cd "$SCRIPT_DIR/frontend"
npm install

echo "🎨 Starting frontend on http://localhost:5173..."
npm run dev &
FRONTEND_PID=$!

# Trap to clean up on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo "✅ Echo App is running!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop both services."

# Wait for both processes
wait


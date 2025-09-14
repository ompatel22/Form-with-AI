#!/bin/bash

# Form Builder Application Startup Script with Ngrok
echo "🎯 Starting Form Builder Application with Ngrok"
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

# Function to check if a process is running on a port
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to kill processes on a port
kill_port() {
    local port=$1
    print_info "Killing any existing processes on port $port..."
    lsof -ti:$port | xargs kill -9 2>/dev/null || true
}

# Cleanup function
cleanup() {
    print_info "Cleaning up processes..."
    kill_port 8000
    kill_port 5173
    pkill -f ngrok || true
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

# Check if ngrok is installed
if ! command -v ngrok >/dev/null 2>&1; then
    print_error "Ngrok is not installed!"
    print_info "Please install ngrok from https://ngrok.com/download"
    exit 1
fi

# Check for ngrok auth
if [ ! -f ~/.config/ngrok/ngrok.yml ] && [ ! -f ~/.ngrok2/ngrok.yml ]; then
    print_warning "Ngrok config not found. You may need to authenticate:"
    print_info "Run: ngrok authtoken YOUR_AUTH_TOKEN"
    print_info "Get your auth token from: https://dashboard.ngrok.com/get-started/your-authtoken"
fi

# Kill any existing processes
kill_port 8000
kill_port 5173
pkill -f ngrok || true

sleep 2

# Start backend server
print_info "Starting backend server on port 8000..."
cd /app/server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
sleep 5

if check_port 8000; then
    print_status "Backend server started successfully"
else
    print_error "Failed to start backend server"
    print_info "Check logs: tail -f /tmp/backend.log"
    exit 1
fi

# Start ngrok tunnels
print_info "Starting ngrok tunnels..."

# Start backend tunnel
ngrok http 8000 --log stdout > /tmp/ngrok_backend.log 2>&1 &
NGROK_BACKEND_PID=$!

sleep 3

# Start frontend tunnel  
ngrok http 5173 --log stdout > /tmp/ngrok_frontend.log 2>&1 &
NGROK_FRONTEND_PID=$!

sleep 3

# Get tunnel URLs
BACKEND_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    for tunnel in tunnels:
        if '8000' in tunnel.get('config', {}).get('addr', ''):
            print(tunnel['public_url'])
            break
except:
    pass
" 2>/dev/null)

FRONTEND_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    for tunnel in tunnels:
        if '5173' in tunnel.get('config', {}).get('addr', ''):
            print(tunnel['public_url'])
            break
except:
    pass
" 2>/dev/null)

if [ -n "$BACKEND_URL" ] && [ -n "$FRONTEND_URL" ]; then
    print_status "Ngrok tunnels started successfully!"
    
    # Update frontend .env file
    echo "VITE_BACKEND_URL=$BACKEND_URL" > /app/Form-with-AI-Frontend/.env
    print_info "Updated frontend .env with backend URL"
    
    # Install frontend dependencies if needed
    cd /app/Form-with-AI-Frontend
    if [ ! -d "node_modules" ]; then
        print_info "Installing frontend dependencies..."
        npm install
        if [ $? -ne 0 ]; then
            print_error "Failed to install frontend dependencies"
            exit 1
        fi
    fi

    # Start frontend server
    print_info "Starting frontend server on port 5173..."
    npm run dev > /tmp/frontend.log 2>&1 &
    FRONTEND_PID=$!

    # Wait for frontend to start
    sleep 5

    if check_port 5173; then
        print_status "Frontend server started successfully"
    else
        print_error "Failed to start frontend server"
        print_info "Check logs: tail -f /tmp/frontend.log"
        exit 1
    fi
    
    echo ""
    echo "============================================================"
    echo -e "${GREEN}🎉 APPLICATION READY!${NC}"
    echo "============================================================"
    echo -e "${BLUE}📱 Access your app at: ${NC}$FRONTEND_URL"
    echo -e "${BLUE}🔧 Backend API at: ${NC}$BACKEND_URL"
    echo -e "${BLUE}📊 Ngrok dashboard: ${NC}http://localhost:4040"
    echo "============================================================"
    echo ""
    print_info "Press Ctrl+C to stop all services"
    
    # Monitor processes
    while true; do
        if ! kill -0 $BACKEND_PID 2>/dev/null; then
            print_error "Backend process died"
            break
        fi
        if ! kill -0 $FRONTEND_PID 2>/dev/null; then
            print_error "Frontend process died"
            break
        fi
        if ! kill -0 $NGROK_BACKEND_PID 2>/dev/null; then
            print_error "Backend ngrok tunnel died"
            break
        fi
        if ! kill -0 $NGROK_FRONTEND_PID 2>/dev/null; then
            print_error "Frontend ngrok tunnel died"
            break
        fi
        sleep 10
    done
    
else
    print_error "Failed to get ngrok tunnel URLs"
    print_info "Check ngrok logs:"
    print_info "Backend tunnel: tail -f /tmp/ngrok_backend.log"
    print_info "Frontend tunnel: tail -f /tmp/ngrok_frontend.log"
fi

# Cleanup will be called automatically by trap
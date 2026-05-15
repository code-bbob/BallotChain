#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_DIR="venv"
BACKEND_PORT=8001
NODES=${NODES:-1}
FRONTEND_PORT=5173
DIFFICULTY=3
BLOCKCHAIN_DATA="blockchain_data.json"
PEER_NODES=""

# Function to print colored output
print_step() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓${NC} $1"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Cleanup function
cleanup() {
    print_info "Shutting down services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    print_info "Cleanup complete"
    exit 0
}

# Trap Ctrl+C to cleanup
trap cleanup SIGINT SIGTERM

# Check Python version
print_step "Checking Python version"
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found. Please install Python 3.9+"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_info "Python version: $PYTHON_VERSION"

# Check Node.js
print_step "Checking Node.js"
if ! command -v node &> /dev/null; then
    print_error "Node.js not found. Please install Node.js"
    exit 1
fi
NODE_VERSION=$(node --version)
print_info "Node.js version: $NODE_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    print_step "Creating Python virtual environment"
    python3 -m venv "$VENV_DIR"
    print_info "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

# Activate virtual environment
print_step "Activating virtual environment"
source "$VENV_DIR/bin/activate"
print_info "Virtual environment activated"

# Install/upgrade pip
print_step "Upgrading pip"
pip install --upgrade pip setuptools wheel -q
print_info "pip upgraded"

# Install backend dependencies
print_step "Installing backend dependencies"
if pip install -r requirements.txt -q; then
    print_info "Backend dependencies installed"
else
    print_error "Failed to install backend dependencies"
    exit 1
fi

# Install frontend dependencies
print_step "Installing frontend dependencies"
cd frontend
if npm install --legacy-peer-deps -q 2>/dev/null; then
    print_info "Frontend dependencies installed"
else
    print_error "Failed to install frontend dependencies"
    exit 1
fi
cd ..

# Start Backend Server(s)
print_step "Starting Backend Server(s)"
echo "Starting $NODES node(s) starting at port $BACKEND_PORT"
export DIFFICULTY=$DIFFICULTY

BACKEND_PIDS=()
BACKEND_PORTS=()
for i in $(seq 0 $((NODES - 1))); do
    port=$((BACKEND_PORT + i))
    datafile="node$((i + 1)).json"
    export BLOCKCHAIN_DATA=$datafile
    print_info "Starting node on http://127.0.0.1:$port (data: $datafile)"
    DIFFICULTY=$DIFFICULTY BLOCKCHAIN_DATA=$datafile uvicorn main:app --host 127.0.0.1 --port $port --reload > /tmp/backend_$port.log 2>&1 &
    pid=$!
    BACKEND_PIDS+=("$pid")
    BACKEND_PORTS+=("$port")
    print_info "Backend PID ($port): $pid"
    sleep 1
done

# Give backends a moment to start
sleep 3

# Verify backends started
for idx in "${!BACKEND_PIDS[@]}"; do
    pid=${BACKEND_PIDS[$idx]}
    port=${BACKEND_PORTS[$idx]}
    if ! kill -0 $pid 2>/dev/null; then
        print_error "Failed to start backend on port $port. Check logs:"
        sed -n '1,200p' /tmp/backend_${port}.log
        exit 1
    fi
done

# Register peers with each node so they know each other
if [ "$NODES" -gt 1 ]; then
    print_step "Registering peer nodes"
    nodes_json="["
    for port in "${BACKEND_PORTS[@]}"; do
        nodes_json="$nodes_json\"http://127.0.0.1:$port\"," 
    done
    # trim trailing comma and close
    nodes_json="${nodes_json%,}]"

    for port in "${BACKEND_PORTS[@]}"; do
        print_info "Registering peers at node $port"
        curl -s -X POST "http://127.0.0.1:$port/nodes/register" -H 'Content-Type: application/json' -d "$nodes_json" >/tmp/register_${port}.out 2>&1 || true
    done
fi

# Start Frontend Development Server
print_step "Starting Frontend Development Server"
print_info "Frontend will run on http://127.0.0.1:$FRONTEND_PORT"
cd frontend
npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
print_info "Frontend PID: $FRONTEND_PID"
cd ..
sleep 4

# Check if frontend started
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    print_error "Failed to start frontend. Check logs:"
    cat /tmp/frontend.log
    kill $BACKEND_PID
    exit 1
fi

# Print status
print_step "System Status"
echo -e "${GREEN}✓ Backend Server${NC} running on http://127.0.0.1:$BACKEND_PORT"
echo -e "${GREEN}✓ Frontend Server${NC} running on http://127.0.0.1:$FRONTEND_PORT"
echo ""

# Open browser (if available)
print_step "Opening Browser"
if command -v xdg-open &> /dev/null; then
    xdg-open "http://127.0.0.1:$FRONTEND_PORT" 2>/dev/null
    print_info "Browser opened at http://127.0.0.1:$FRONTEND_PORT"
elif command -v open &> /dev/null; then
    open "http://127.0.0.1:$FRONTEND_PORT"
    print_info "Browser opened at http://127.0.0.1:$FRONTEND_PORT"
else
    print_info "Please open your browser and navigate to http://127.0.0.1:$FRONTEND_PORT"
fi

# Show service information
print_step "Service Information"
cat << EOF
${GREEN}🔗 Quick Links:${NC}
  • Frontend:     http://127.0.0.1:$FRONTEND_PORT
  • Backend API:  http://127.0.0.1:$BACKEND_PORT
  • API Docs:     http://127.0.0.1:$BACKEND_PORT/docs

${GREEN}📝 Quick Start (in the UI):${NC}
  1. Go to Voter Console (🗳️)
  2. Click "Generate New Wallet"
  3. Click "Register This Wallet"
  4. Enter a candidate name and election ID
  5. Click "Submit Vote"
  6. Go to Admin Console (⚙️)
  7. Click "Mine Pending Votes"
  8. View results in the Voter Console

${GREEN}🔧 Environment:${NC}
  DIFFICULTY:     $DIFFICULTY
  BLOCKCHAIN:     $BLOCKCHAIN_DATA
  Backend PID:    $BACKEND_PID
  Frontend PID:   $FRONTEND_PID

${YELLOW}Press Ctrl+C to stop all services${NC}
EOF

print_step "Ready!"
print_info "System is running. Waiting for requests..."

# Keep the script running
wait $BACKEND_PID $FRONTEND_PID

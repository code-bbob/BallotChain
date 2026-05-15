#!/usr/bin/env python3
"""
Master run script for the Voting Blockchain system.
Starts backend, frontend, and opens browser - all in one command!
Works on Linux, macOS, and Windows.

Usage:
    python run_all.py [--difficulty 3] [--port 8001] [--no-browser]
"""

import os
import sys
import subprocess
import time
import webbrowser
import shutil
import argparse
import signal
from pathlib import Path

# Colors for output
class Colors:
    RESET = '\033[0m'
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    BOLD = '\033[1m'

def print_step(msg):
    print(f"\n{Colors.BLUE}{'━' * 50}{Colors.RESET}")
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")
    print(f"{Colors.BLUE}{'━' * 50}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.YELLOW}ℹ{Colors.RESET} {msg}")

def print_error(msg):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")

def print_success(msg):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")

def check_command_exists(cmd):
    """Check if a command exists in PATH"""
    return shutil.which(cmd) is not None

def run_command(cmd, description, background=False):
    """Run a command and handle errors"""
    try:
        if background:
            if sys.platform == 'win32':
                # Windows: use subprocess with CREATE_NEW_CONSOLE
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                )
            else:
                # Unix: use nohup
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid if sys.platform != 'win32' else None
                )
            return process
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print_error(f"Failed to {description}")
                if result.stderr:
                    print(f"  Error: {result.stderr}")
                return None
            return result
    except Exception as e:
        print_error(f"Error running command: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(
        description='Start the Voting Blockchain system (backend + frontend)'
    )
    parser.add_argument('--mode', choices=['single', 'docker', 'multi'], default='single',
                        help='Run mode: single=single node, docker=3 nodes in Docker, multi=3 local nodes')
    parser.add_argument('--difficulty', type=int, default=3, help='Mining difficulty (default: 3)')
    parser.add_argument('--port', type=int, default=8001, help='Backend port for single mode (default: 8001)')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser')
    parser.add_argument('--peer-nodes', type=str, default='', help='Comma-separated peer nodes')
    args = parser.parse_args()

    backend_port = args.port
    frontend_port = 5173
    difficulty = args.difficulty
    blockchain_data = 'blockchain_data.json'
    peer_nodes = args.peer_nodes

    print_step("Voting Blockchain System - Startup Script")
    
    # Check Python
    print_step("Checking Environment")
    py_version = sys.version.split()[0]
    print_info(f"Python version: {py_version}")

    # Check Node.js
    if not check_command_exists('node'):
        print_error("Node.js not found. Please install Node.js from https://nodejs.org/")
        sys.exit(1)
    result = subprocess.run('node --version', shell=True, capture_output=True, text=True)
    print_info(f"Node.js version: {result.stdout.strip()}")

    # Handle Docker mode
    if args.mode == 'docker':
        print_step("Docker Multi-Node Mode")
        if not check_command_exists('docker'):
            print_error("Docker not found. Please install Docker from https://www.docker.com/")
            sys.exit(1)
        if not check_command_exists('docker-compose'):
            print_error("Docker Compose not found. Please install Docker Compose.")
            sys.exit(1)
        
        print_info("Starting 3 blockchain nodes in Docker...")
        docker_cmd = 'docker-compose up -d'
        if run_command(docker_cmd, "start Docker containers"):
            print_success("Docker containers started!")
            print_info("Nodes running:")
            print_info("  • Node 1: http://127.0.0.1:8001")
            print_info("  • Node 2: http://127.0.0.1:8002")
            print_info("  • Node 3: http://127.0.0.1:8003")
        else:
            sys.exit(1)
        
        # Start frontend only
        print_step("Installing Frontend Dependencies")
        os.chdir('frontend')
        npm_cmd = 'npm install --legacy-peer-deps -q'
        if run_command(npm_cmd, "install frontend dependencies"):
            print_success("Frontend dependencies installed")
        else:
            os.chdir('..')
            sys.exit(1)
        os.chdir('..')

        frontend_port = 5173
        print_step("Starting Frontend Development Server")
        frontend_cmd = 'cd frontend && npm run dev'
        frontend_proc = run_command(frontend_cmd, "start frontend", background=True)
        if not frontend_proc:
            print_error("Failed to start frontend server")
            run_command('docker-compose down', "stop Docker containers")
            sys.exit(1)
        print_info(f"Frontend will run on http://127.0.0.1:{frontend_port}")
        time.sleep(4)

        # Open Browser
        frontend_url = f"http://127.0.0.1:{frontend_port}"
        if not args.no_browser:
            print_step("Opening Browser")
            try:
                webbrowser.open(frontend_url)
                print_success(f"Browser opened at {frontend_url}")
            except Exception as e:
                print_info(f"Could not open browser automatically: {e}")
                print_info(f"Please visit: {frontend_url}")

        # Print Summary
        print_step("🚀 Docker Multi-Node System Ready!")
        print(f"""
{Colors.GREEN}✓ Node 1{Colors.RESET} running on http://127.0.0.1:8001
{Colors.GREEN}✓ Node 2{Colors.RESET} running on http://127.0.0.1:8002
{Colors.GREEN}✓ Node 3{Colors.RESET} running on http://127.0.0.1:8003
{Colors.GREEN}✓ Frontend Server{Colors.RESET} running on http://127.0.0.1:{frontend_port}

{Colors.BOLD}🔗 Quick Links:{Colors.RESET}
  • Frontend:     {frontend_url}
  • Node 1 API:   http://127.0.0.1:8001/docs
  • Node 2 API:   http://127.0.0.1:8002/docs
  • Node 3 API:   http://127.0.0.1:8003/docs

{Colors.BOLD}📝 Test Multi-Node Consensus:{Colors.RESET}
  1. Go to Voter Console
  2. Generate wallet and register
  3. Cast a vote to Node 1
  4. Go to Admin Console -> set Node URL to Node 1
  5. Click "Mine Pending Votes"
  6. Change Node URL to Node 2
  7. Verify the block was synced automatically!

{Colors.YELLOW}Press Ctrl+C to stop all services{Colors.RESET}
""")

        try:
            frontend_proc.wait()
        except KeyboardInterrupt:
            print_info("\nShutting down services...")
            frontend_proc.terminate()
            run_command('docker-compose down', "stop Docker containers")
            try:
                frontend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_proc.kill()
            print_info("Cleanup complete")
            sys.exit(0)
        
        return  # End here for Docker mode

    # Handle multi-node local mode
    if args.mode == 'multi':
        print_step("Multi-Node Local Mode (3 nodes)")
        
        # Create venv
        venv_dir = 'venv'
        if not os.path.exists(venv_dir):
            print_step("Creating Virtual Environment")
            if sys.platform == 'win32':
                venv_cmd = f'python -m venv {venv_dir}'
            else:
                venv_cmd = f'python3 -m venv {venv_dir}'
            
            if run_command(venv_cmd, "create virtual environment"):
                print_success("Virtual environment created")
            else:
                sys.exit(1)
        else:
            print_info("Virtual environment already exists")

        # Get Python executable
        if sys.platform == 'win32':
            python_exe = os.path.join(venv_dir, 'Scripts', 'python.exe')
            pip_exe = os.path.join(venv_dir, 'Scripts', 'pip.exe')
        else:
            python_exe = os.path.join(venv_dir, 'bin', 'python')
            pip_exe = os.path.join(venv_dir, 'bin', 'pip')

        # Install dependencies
        print_step("Installing Backend Dependencies")
        pip_cmd = f'"{pip_exe}" install -r requirements.txt -q'
        if run_command(pip_cmd, "install backend dependencies"):
            print_success("Backend dependencies installed")
        else:
            sys.exit(1)

        # Install frontend
        print_step("Installing Frontend Dependencies")
        os.chdir('frontend')
        npm_cmd = 'npm install --legacy-peer-deps -q'
        if run_command(npm_cmd, "install frontend dependencies"):
            print_success("Frontend dependencies installed")
        else:
            os.chdir('..')
            sys.exit(1)
        os.chdir('..')

        print_step("Starting 3 Blockchain Nodes")
        
        nodes = [
            {'num': 1, 'port': 8001, 'data': 'data/node1.json', 'peers': 'http://127.0.0.1:8002,http://127.0.0.1:8003'},
            {'num': 2, 'port': 8002, 'data': 'data/node2.json', 'peers': 'http://127.0.0.1:8001,http://127.0.0.1:8003'},
            {'num': 3, 'port': 8003, 'data': 'data/node3.json', 'peers': 'http://127.0.0.1:8001,http://127.0.0.1:8002'},
        ]
        
        node_procs = []
        for node in nodes:
            if sys.platform == 'win32':
                cmd = f'set DIFFICULTY={args.difficulty} && set BLOCKCHAIN_DATA={node["data"]} && set PEER_NODES={node["peers"]} && "{python_exe}" -m uvicorn main:app --host 127.0.0.1 --port {node["port"]}'
            else:
                cmd = f'DIFFICULTY={args.difficulty} BLOCKCHAIN_DATA={node["data"]} PEER_NODES="{node["peers"]}" uvicorn main:app --host 127.0.0.1 --port {node["port"]} --reload'
            
            proc = run_command(cmd, f"start node {node['num']}", background=True)
            if proc:
                node_procs.append(proc)
                print_info(f"Node {node['num']} started on port {node['port']}")
            else:
                print_error(f"Failed to start node {node['num']}")
                for p in node_procs:
                    p.terminate()
                sys.exit(1)
            time.sleep(1)

        # Start frontend
        print_step("Starting Frontend Development Server")
        frontend_port = 5173
        frontend_cmd = 'cd frontend && npm run dev'
        frontend_proc = run_command(frontend_cmd, "start frontend", background=True)
        if not frontend_proc:
            print_error("Failed to start frontend server")
            for p in node_procs:
                p.terminate()
            sys.exit(1)
        print_info(f"Frontend will run on http://127.0.0.1:{frontend_port}")
        time.sleep(4)

        # Open Browser
        frontend_url = f"http://127.0.0.1:{frontend_port}"
        if not args.no_browser:
            print_step("Opening Browser")
            try:
                webbrowser.open(frontend_url)
                print_success(f"Browser opened at {frontend_url}")
            except Exception as e:
                print_info(f"Could not open browser automatically: {e}")
                print_info(f"Please visit: {frontend_url}")

        # Print Summary
        print_step("🚀 Multi-Node System Ready!")
        print(f"""
{Colors.GREEN}✓ Node 1{Colors.RESET} running on http://127.0.0.1:8001
{Colors.GREEN}✓ Node 2{Colors.RESET} running on http://127.0.0.1:8002
{Colors.GREEN}✓ Node 3{Colors.RESET} running on http://127.0.0.1:8003
{Colors.GREEN}✓ Frontend Server{Colors.RESET} running on http://127.0.0.1:{frontend_port}

{Colors.BOLD}🔗 Quick Links:{Colors.RESET}
  • Frontend:     {frontend_url}
  • Node 1 API:   http://127.0.0.1:8001/docs
  • Node 2 API:   http://127.0.0.1:8002/docs
  • Node 3 API:   http://127.0.0.1:8003/docs

{Colors.BOLD}📝 Test Multi-Node Consensus:{Colors.RESET}
  1. Go to Voter Console -> Generate wallet
  2. Register on Node 1
  3. Cast vote on Node 1
  4. Go to Admin Console -> set Node URL to Node 1
  5. Click "Mine Pending Votes"
  6. Change Node URL to Node 2
  7. Verify block synced! (Consensus working)

{Colors.YELLOW}Press Ctrl+C to stop all services{Colors.RESET}
""")

        try:
            for proc in node_procs + [frontend_proc]:
                proc.wait()
        except KeyboardInterrupt:
            print_info("\nShutting down services...")
            for proc in node_procs + [frontend_proc]:
                proc.terminate()
            try:
                for proc in node_procs + [frontend_proc]:
                    proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                for proc in node_procs + [frontend_proc]:
                    proc.kill()
            print_info("Cleanup complete")
            sys.exit(0)
        
        return  # End here for multi-node mode

    # Create venv if needed
    venv_dir = 'venv'
    if not os.path.exists(venv_dir):
        print_step("Creating Virtual Environment")
        if sys.platform == 'win32':
            venv_cmd = f'python -m venv {venv_dir}'
        else:
            venv_cmd = f'python3 -m venv {venv_dir}'
        
        if run_command(venv_cmd, "create virtual environment"):
            print_success("Virtual environment created")
        else:
            sys.exit(1)
    else:
        print_info("Virtual environment already exists")

    # Get Python executable in venv
    if sys.platform == 'win32':
        python_exe = os.path.join(venv_dir, 'Scripts', 'python.exe')
        pip_exe = os.path.join(venv_dir, 'Scripts', 'pip.exe')
    else:
        python_exe = os.path.join(venv_dir, 'bin', 'python')
        pip_exe = os.path.join(venv_dir, 'bin', 'pip')

    # Activate and install backend dependencies
    print_step("Installing Backend Dependencies")
    pip_cmd = f'"{pip_exe}" install -r requirements.txt -q'
    if run_command(pip_cmd, "install backend dependencies"):
        print_success("Backend dependencies installed")
    else:
        sys.exit(1)

    # Install frontend dependencies
    print_step("Installing Frontend Dependencies")
    os.chdir('frontend')
    npm_cmd = 'npm install --legacy-peer-deps -q'
    if run_command(npm_cmd, "install frontend dependencies"):
        print_success("Frontend dependencies installed")
    else:
        os.chdir('..')
        sys.exit(1)
    os.chdir('..')

    # Setup environment variables
    env = os.environ.copy()
    env['DIFFICULTY'] = str(difficulty)
    env['BLOCKCHAIN_DATA'] = blockchain_data
    if peer_nodes:
        env['PEER_NODES'] = peer_nodes

    # Start Backend
    print_step("Starting Backend Server")
    if sys.platform == 'win32':
        backend_cmd = f'"{python_exe}" -m uvicorn main:app --host 127.0.0.1 --port {backend_port}'
    else:
        backend_cmd = f'source {venv_dir}/bin/activate && uvicorn main:app --host 127.0.0.1 --port {backend_port} --reload'
    
    backend_proc = run_command(backend_cmd, "start backend", background=True)
    if not backend_proc:
        print_error("Failed to start backend server")
        sys.exit(1)
    print_info(f"Backend will run on http://127.0.0.1:{backend_port}")
    time.sleep(3)

    # Start Frontend
    print_step("Starting Frontend Development Server")
    frontend_cmd = 'cd frontend && npm run dev'
    frontend_proc = run_command(frontend_cmd, "start frontend", background=True)
    if not frontend_proc:
        print_error("Failed to start frontend server")
        if backend_proc:
            backend_proc.terminate()
        sys.exit(1)
    print_info(f"Frontend will run on http://127.0.0.1:{frontend_port}")
    time.sleep(4)

    # Open Browser
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    if not args.no_browser:
        print_step("Opening Browser")
        try:
            webbrowser.open(frontend_url)
            print_success(f"Browser opened at {frontend_url}")
        except Exception as e:
            print_info(f"Could not open browser automatically: {e}")
            print_info(f"Please visit: {frontend_url}")
    
    # Print Summary
    print_step("🚀 System Ready!")
    print(f"""
{Colors.GREEN}✓ Backend Server{Colors.RESET} running on http://127.0.0.1:{backend_port}
{Colors.GREEN}✓ Frontend Server{Colors.RESET} running on http://127.0.0.1:{frontend_port}

{Colors.BOLD}🔗 Quick Links:{Colors.RESET}
  • Frontend:     {frontend_url}
  • Backend API:  http://127.0.0.1:{backend_port}
  • API Docs:     http://127.0.0.1:{backend_port}/docs

{Colors.BOLD}📝 Quick Start (in the UI):{Colors.RESET}
  1. Go to Voter Console (🗳️)
  2. Click "Generate New Wallet"
  3. Click "Register This Wallet"
  4. Enter a candidate name and election ID
  5. Click "Submit Vote"
  6. Go to Admin Console (⚙️)
  7. Click "Mine Pending Votes"
  8. View results in Voter Console

{Colors.BOLD}🔧 Configuration:{Colors.RESET}
  DIFFICULTY:     {difficulty}
  BLOCKCHAIN:     {blockchain_data}
  Backend Port:   {backend_port}
  Frontend Port:  {frontend_port}
{('  Peer Nodes:    ' + peer_nodes) if peer_nodes else ''}

{Colors.YELLOW}Press Ctrl+C to stop all services{Colors.RESET}
""")

    # Keep running
    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        print_info("\nShutting down services...")
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
            frontend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
            frontend_proc.kill()
        print_info("Cleanup complete")
        sys.exit(0)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Persistent test runner with background server.
Starts server once and runs tests without restarting.

Usage:
    python scripts/run_tests_with_server.py                    # Run all tests
    python scripts/run_tests_with_server.py integration       # Run integration tests only
    python scripts/run_tests_with_server.py unit             # Run unit tests only
    python scripts/run_tests_with_server.py <specific_test>  # Run specific test module
"""

import threading
import subprocess
import time
import sys
import os
import signal
import queue
import argparse
from pathlib import Path

class ServerManager:
    def __init__(self):
        self.process = None
        self.output_queue = queue.Queue()
        self.error_queue = queue.Queue()
        self.running = False
        self.thread = None
        
    def start(self):
        """Start the server in a background thread"""
        # Kill any existing process on port 8000
        print("Checking for existing server on port 8000...")
        result = subprocess.run(['lsof', '-ti:8000'], capture_output=True, text=True)
        if result.stdout.strip():
            for pid in result.stdout.strip().split('\n'):
                if pid:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        print(f"Killed existing process {pid}")
                    except:
                        pass
            time.sleep(1)
        
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        
        # Wait for server to start
        print("Starting server in background thread...")
        timeout = time.time() + 20
        started = False
        
        while time.time() < timeout and self.running:
            try:
                line = self.output_queue.get(timeout=0.1)
                print(f"[SERVER] {line}")
                if "Server started at" in line:
                    started = True
                    break
            except queue.Empty:
                continue
                
        if started:
            print("\n✅ Server is running on http://localhost:8000\n")
            return True
        else:
            print("\n❌ Server failed to start\n")
            self.stop()
            return False
            
    def _run_server(self):
        """Run the server process"""
        # Get the project root directory
        project_root = Path(__file__).parent.parent
        python_dir = project_root / 'code' / 'python'
        
        env = os.environ.copy()
        env['PYTHONPATH'] = str(python_dir)
        
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'webserver.aiohttp_server'],
            cwd=str(python_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Read all output
        for line in iter(self.process.stdout.readline, ''):
            if line and self.running:
                line = line.strip()
                self.output_queue.put(line)
                if "ERROR" in line or "Traceback" in line or "Exception" in line:
                    self.error_queue.put(line)
                    
    def get_errors(self):
        """Get any server errors"""
        errors = []
        while True:
            try:
                errors.append(self.error_queue.get_nowait())
            except queue.Empty:
                break
        return errors
        
    def stop(self):
        """Stop the server"""
        self.running = False
        if self.process:
            self.process.terminate()
            time.sleep(0.5)
            if self.process.poll() is None:
                self.process.kill()
        print("Server stopped")

def run_tests(test_path=None, verbose=True):
    """Run pytest with specified path"""
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    
    cmd = [sys.executable, '-m', 'pytest']
    
    if test_path:
        cmd.append(test_path)
    
    if verbose:
        cmd.extend(['-v', '--tb=short'])
    
    # Add coverage if running all tests
    if not test_path or test_path == 'tests':
        cmd.extend(['--cov=code/python', '--cov-report=term-missing:skip-covered'])
    
    print(f"\nRunning: {' '.join(cmd)}\n")
    
    result = subprocess.run(
        cmd,
        cwd=str(project_root)
    )
    
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description='Run tests with background server')
    parser.add_argument('test_type', nargs='?', default='all',
                       help='Test type: all, integration, unit, e2e, or specific test path')
    parser.add_argument('--no-server', action='store_true',
                       help='Skip starting server (assume it\'s already running)')
    parser.add_argument('--keep-server', action='store_true',
                       help='Keep server running after tests')
    args = parser.parse_args()
    
    server = None
    
    try:
        # Start server if needed
        if not args.no_server:
            server = ServerManager()
            if not server.start():
                print("Failed to start server!")
                return 1
            
            # Give server a moment to fully initialize
            time.sleep(2)
        
        # Determine test path
        test_paths = {
            'all': 'tests',
            'integration': 'tests/integration',
            'unit': 'tests/unit',
            'e2e': 'tests/e2e',
            'websocket': 'tests/integration/test_websocket.py',
            'rest': 'tests/integration/test_rest_api.py',
            'performance': 'tests/performance',
            'security': 'tests/security',
            'reliability': 'tests/reliability'
        }
        
        test_path = test_paths.get(args.test_type, args.test_type)
        
        # Run tests
        print(f"Running {args.test_type} tests...")
        success = run_tests(test_path)
        
        if not success:
            print("\n❌ Tests failed!")
            # Check for server errors
            if server:
                errors = server.get_errors()
                if errors:
                    print("\nServer errors detected:")
                    for error in errors[:10]:  # Show first 10 errors
                        print(f"  [ERROR] {error}")
            return 1
        else:
            print("\n✅ All tests passed!")
            return 0
            
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    finally:
        # Stop server unless asked to keep it running
        if server and not args.keep_server:
            print("\nStopping server...")
            server.stop()

if __name__ == "__main__":
    sys.exit(main())
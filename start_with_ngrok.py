#!/usr/bin/env python3
"""
Startup script for Form Builder Application with Ngrok tunnels
Compatible with Windows PowerShell and Unix systems
"""
import os
import sys
import time
import subprocess
import signal
import atexit
import platform
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from ngrok_config import ngrok_manager

class ApplicationManager:
    def __init__(self):
        self.backend_process = None
        self.frontend_process = None
        self.tunnels_started = False

        # Determine project root
        self.project_root = Path(__file__).parent.resolve()
        self.backend_path = self.project_root / "server"
        self.frontend_path = self.project_root / "Form-with-AI-Frontend"

        # Determine platform-specific commands
        self.npm_cmd = 'npm.cmd' if platform.system() == 'Windows' else 'npm'

    def kill_existing_ngrok(self):
        """Kill any existing ngrok processes"""
        try:
            if platform.system() == 'Windows':
                subprocess.run(['taskkill', '/f', '/im', 'ngrok.exe'], capture_output=True)
            else:
                subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
        except Exception:
            pass  # Ignore if no processes are running

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}. Shutting down gracefully...")
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        atexit.register(self.shutdown)

    def start_backend(self):
        """Start the FastAPI backend server"""
        print("🚀 Starting backend server...")

        if not self.backend_path.exists():
            print(f"❌ Backend path not found: {self.backend_path}")
            return False

        os.chdir(self.backend_path)

        self.backend_process = subprocess.Popen([
            'uvicorn',
            'app.main:app',
            '--host', '0.0.0.0',
            '--port', '8000',
            '--reload'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        time.sleep(3)

        if self.backend_process.poll() is None:
            print("✅ Backend server started successfully on port 8000")
        else:
            print("❌ Failed to start backend server")
            return False

        return True

    def start_frontend(self):
        """Start the React frontend server"""
        print("🚀 Starting frontend server...")

        if not self.frontend_path.exists():
            print(f"❌ Frontend path not found: {self.frontend_path}")
            return False

        os.chdir(self.frontend_path)

        # Install dependencies if node_modules doesn't exist
        if not (self.frontend_path / "node_modules").exists():
            print("📦 Installing frontend dependencies...")
            npm_install = subprocess.run([self.npm_cmd, 'install'], capture_output=True, text=True)
            if npm_install.returncode != 0:
                print("❌ Failed to install frontend dependencies")
                print(npm_install.stderr)
                return False

        self.frontend_process = subprocess.Popen([
            self.npm_cmd, 'run', 'dev'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        time.sleep(5)

        if self.frontend_process.poll() is None:
            print("✅ Frontend server started successfully on port 5173")
        else:
            print("❌ Failed to start frontend server")
            return False

        return True

    def start_ngrok_tunnels(self):
        """Start ngrok tunnels"""
        print("🌐 Starting ngrok tunnels...")
        self.kill_existing_ngrok()

        # <-- FIX: Remove ngrok_executable argument -->
        result = ngrok_manager.start_tunnels()

        if result.get("status") == "success":
            print("✅ Ngrok tunnels started successfully!")
            print(f"🔗 Backend URL: {result['backend_url']}")
            print(f"🔗 Frontend URL: {result['frontend_url']}")
            print("\n" + "=" * 60)
            print("🎉 APPLICATION READY!")
            print("=" * 60)
            self.tunnels_started = True
            return True
        else:
            print(f"❌ Failed to start ngrok tunnels: {result.get('error')}")
            return False

    def monitor_processes(self):
        """Monitor backend and frontend processes"""
        print("\n👀 Monitoring application processes...")
        print("Press Ctrl+C to stop all services")

        while True:
            try:
                if self.backend_process and self.backend_process.poll() is not None:
                    print("⚠️ Backend process died. Restarting...")
                    if not self.start_backend():
                        print("❌ Failed to restart backend")
                        break

                if self.frontend_process and self.frontend_process.poll() is not None:
                    print("⚠️ Frontend process died. Restarting...")
                    if not self.start_frontend():
                        print("❌ Failed to restart frontend")
                        break

                time.sleep(30)
                if self.tunnels_started:
                    health = ngrok_manager.health_check()
                    if not health.get("backend_healthy", False):
                        print("⚠️ Backend health check failed")
                    if not health.get("frontend_healthy", False):
                        print("⚠️ Frontend health check failed")

            except KeyboardInterrupt:
                print("\n🛑 Shutdown requested by user")
                break
            except Exception as e:
                print(f"❌ Error monitoring processes: {e}")
                time.sleep(5)

    def shutdown(self):
        """Shutdown all processes and tunnels"""
        print("\n🛑 Shutting down application...")

        if self.backend_process:
            print("Stopping backend server...")
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.backend_process.kill()
            self.backend_process = None

        if self.frontend_process:
            print("Stopping frontend server...")
            self.frontend_process.terminate()
            try:
                self.frontend_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.frontend_process.kill()
            self.frontend_process = None

        if self.tunnels_started:
            print("Stopping ngrok tunnels...")
            ngrok_manager.stop_tunnels()
            self.tunnels_started = False

        print("✅ Shutdown complete")

    def run(self):
        print("🎯 Starting Form Builder Application with Ngrok")
        print("=" * 50)

        self.setup_signal_handlers()

        if not self.start_backend():
            return False

        if not self.start_ngrok_tunnels():
            return False

        if not self.start_frontend():
            return False

        self.monitor_processes()
        return True


def main():
    cmd = ['where', 'ngrok'] if platform.system() == 'Windows' else ['which', 'ngrok']

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("❌ Ngrok is not installed or not in PATH")
        print("Please install ngrok from https://ngrok.com/download")
        return False

    app_manager = ApplicationManager()
    success = app_manager.run()

    if not success:
        print("❌ Failed to start application")
        app_manager.shutdown()
        return False

    return True


if __name__ == "__main__":
    main()

"""
Ngrok Configuration for Form Builder Application
"""
import os
import subprocess
import time
import json
from pyngrok import ngrok, conf
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class NgrokManager:
    def __init__(self):
        self.backend_tunnel = None
        self.frontend_tunnel = None
        self.backend_url = None
        self.frontend_url = None
        
    def start_tunnels(self):
        """Start ngrok tunnels for both backend and frontend"""
        try:
            # Kill any existing ngrok processes
            self.stop_tunnels()
            
            logger.info("Starting ngrok tunnels...")
            
            # Start backend tunnel (port 8000)
            self.backend_tunnel = ngrok.connect(8000, "http")
            self.backend_url = self.backend_tunnel.public_url
            logger.info(f"Backend tunnel started: {self.backend_url}")
            
            # Start frontend tunnel (port 5173)
            self.frontend_tunnel = ngrok.connect(5173, "http") 
            self.frontend_url = self.frontend_tunnel.public_url
            logger.info(f"Frontend tunnel started: {self.frontend_url}")
            
            # Update environment variables
            self.update_frontend_env()
            
            return {
                "backend_url": self.backend_url,
                "frontend_url": self.frontend_url,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Failed to start ngrok tunnels: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    def stop_tunnels(self):
        """Stop all ngrok tunnels"""
        try:
            # Disconnect specific tunnels
            if self.backend_tunnel:
                ngrok.disconnect(self.backend_tunnel.public_url)
                self.backend_tunnel = None
                
            if self.frontend_tunnel:
                ngrok.disconnect(self.frontend_tunnel.public_url)
                self.frontend_tunnel = None
            
            # Kill all ngrok processes
            ngrok.kill()
            
            logger.info("All ngrok tunnels stopped")
            
        except Exception as e:
            logger.warning(f"Error stopping tunnels: {e}")
    
    def update_frontend_env(self):
        """Update frontend .env file with backend URL"""
        if not self.backend_url:
            return
            
        project_root = Path(__file__).parent.resolve()
        frontend_path = project_root / "Form-with-AI-Frontend"
        env_path = frontend_path / ".env"
        
        # Create or update .env file
        env_content = f"VITE_BACKEND_URL={self.backend_url}\n"
        
        # If .env exists, preserve other variables
        if env_path.exists():
            with env_path.open('r') as f:
                lines = f.readlines()
            
            # Filter out old VITE_BACKEND_URL entries
            new_lines = [line for line in lines if not line.startswith('VITE_BACKEND_URL')]
            env_content = ''.join(new_lines) + env_content
        
        with env_path.open('w') as f:
            f.write(env_content)
            
        logger.info(f"Updated frontend .env with backend URL: {self.backend_url}")
    
    def get_tunnel_info(self):
        """Get current tunnel information"""
        tunnels = ngrok.get_tunnels()
        
        info = {
            "active_tunnels": len(tunnels),
            "tunnels": []
        }
        
        for tunnel in tunnels:
            info["tunnels"].append({
                "name": tunnel.name,
                "public_url": tunnel.public_url,
                "local_port": tunnel.config.get("addr", "unknown")
            })
        
        return info
    
    def health_check(self):
        """Check if tunnels are healthy"""
        try:
            import requests
            
            results = {
                "backend_healthy": False,
                "frontend_healthy": False,
                "backend_url": self.backend_url,
                "frontend_url": self.frontend_url
            }
            
            # Check backend health
            if self.backend_url:
                try:
                    response = requests.get(f"{self.backend_url}/health", timeout=10)
                    results["backend_healthy"] = response.status_code == 200
                except:
                    results["backend_healthy"] = False
            
            # Check frontend (simple connection test)
            if self.frontend_url:
                try:
                    response = requests.head(self.frontend_url, timeout=10)
                    results["frontend_healthy"] = response.status_code in [200, 404]  # 404 is ok for SPA
                except:
                    results["frontend_healthy"] = False
            
            return results
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"error": str(e)}

# Global ngrok manager instance
ngrok_manager = NgrokManager()

if __name__ == "__main__":
    # Direct execution for testing
    result = ngrok_manager.start_tunnels()
    print(json.dumps(result, indent=2))
    
    # Keep running
    try:
        while True:
            time.sleep(60)
            info = ngrok_manager.get_tunnel_info()
            print(f"Active tunnels: {info['active_tunnels']}")
    except KeyboardInterrupt:
        print("Stopping tunnels...")
        ngrok_manager.stop_tunnels()
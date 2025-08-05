"""
Vercel-compatible entry point using class-based handler
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add the parent directory to the path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

class VercelHandler(BaseHTTPRequestHandler):
    """HTTP Handler class that Vercel can properly inspect"""
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            # Parse the URL
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            query_params = parse_qs(parsed_url.query)
            
            # Route the request
            if path == '/' or path == '':
                response_data = {
                    "message": "House Finance Tracker API",
                    "status": "running",
                    "version": "1.0.0",
                    "timestamp": datetime.now().isoformat(),
                    "method": "GET",
                    "endpoints": {
                        "health": "/health",
                        "api": "/api"
                    }
                }
                
            elif path == '/health':
                response_data = {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "application": "House Finance Tracker",
                    "version": "1.0.0",
                    "environment": "serverless"
                }
                
            elif path == '/api':
                response_data = {
                    "name": "House Finance Tracker API",
                    "version": "1.0.0",
                    "status": "active",
                    "timestamp": datetime.now().isoformat(),
                    "description": "REST API for house finance tracking"
                }
                
            else:
                # 404 for unknown paths
                response_data = {
                    "error": "Not Found",
                    "message": f"The endpoint {path} was not found",
                    "timestamp": datetime.now().isoformat(),
                    "available_endpoints": ["/", "/health", "/api"]
                }
                self.send_error_response(404, response_data)
                return
            
            # Send successful response
            self.send_json_response(200, response_data)
            
        except Exception as e:
            # Error response
            error_data = {
                "error": "Internal Server Error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.send_error_response(500, error_data)
    
    def do_POST(self):
        """Handle POST requests"""
        response_data = {
            "message": "POST requests not implemented yet",
            "status": "not_implemented",
            "timestamp": datetime.now().isoformat()
        }
        self.send_json_response(501, response_data)
    
    def send_json_response(self, status_code, data):
        """Send a JSON response"""
        response_body = json.dumps(data, indent=2).encode('utf-8')
        
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        
        self.wfile.write(response_body)
    
    def send_error_response(self, status_code, data):
        """Send an error response"""
        self.send_json_response(status_code, data)
    
    def log_message(self, format, *args):
        """Override log message to prevent console spam"""
        pass

# Export the handler class for Vercel
handler = VercelHandler
app = VercelHandler

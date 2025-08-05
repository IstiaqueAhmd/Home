"""
Simple WSGI application for Vercel deployment
This bypasses FastAPI to avoid ASGI compatibility issues
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import parse_qs

# Add parent directory to path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

def application(environ, start_response):
    """Main WSGI application"""
    try:
        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO', '/')
        query_string = environ.get('QUERY_STRING', '')
        
        # Parse query parameters
        query_params = parse_qs(query_string)
        
        # Basic routing
        if path == '/' or path == '':
            response_data = {
                "message": "House Finance Tracker API",
                "status": "running",
                "version": "1.0.0",
                "timestamp": datetime.now().isoformat(),
                "method": method,
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
            
            response_body = json.dumps(response_data, indent=2).encode('utf-8')
            status = '404 Not Found'
            headers = [
                ('Content-Type', 'application/json'),
                ('Content-Length', str(len(response_body)))
            ]
            start_response(status, headers)
            return [response_body]
        
        # Success response
        response_body = json.dumps(response_data, indent=2).encode('utf-8')
        status = '200 OK'
        headers = [
            ('Content-Type', 'application/json'),
            ('Content-Length', str(len(response_body))),
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        ]
        
        start_response(status, headers)
        return [response_body]
        
    except Exception as e:
        # Error response
        error_data = {
            "error": "Internal Server Error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
        response_body = json.dumps(error_data, indent=2).encode('utf-8')
        status = '500 Internal Server Error'
        headers = [
            ('Content-Type', 'application/json'),
            ('Content-Length', str(len(response_body)))
        ]
        
        start_response(status, headers)
        return [response_body]

# Export for Vercel
app = application

"""
Vercel-compatible entry point
"""
import sys
import os
from pathlib import Path

# Add the parent directory to the path
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

try:
    # Import the simple WSGI app
    from api.wsgi_app import application
    print("Successfully imported WSGI application")
    
    # Export for Vercel
    app = application
    handler = application
    
except ImportError as e:
    print(f"Failed to import WSGI app: {e}")
    
    # Ultimate fallback - pure function
    import json
    from datetime import datetime
    
    def fallback_app(environ, start_response):
        """Ultimate fallback WSGI application"""
        response_data = {
            "message": "House Finance Tracker - Fallback Mode",
            "error": f"Import failed: {e}",
            "status": "fallback",
            "timestamp": datetime.now().isoformat()
        }
        
        response_body = json.dumps(response_data).encode('utf-8')
        status = '200 OK'
        headers = [
            ('Content-Type', 'application/json'),
            ('Content-Length', str(len(response_body)))
        ]
        
        start_response(status, headers)
        return [response_body]
    
    app = fallback_app
    handler = fallback_app

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import our modules
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

try:
    # Try to import the main FastAPI app
    from main import app
    print("Successfully imported main app")
    
except ImportError as e:
    print(f"Failed to import main app: {e}")
    try:
        # Try serverless fallback
        from serverless import app
        print("Using serverless fallback app")
    except ImportError as e2:
        print(f"Failed to import serverless app: {e2}")
        # Create minimal fallback
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from datetime import datetime
        
        app = FastAPI(title="Fallback App")
        
        @app.get("/")
        async def root():
            return JSONResponse({
                "message": "Fallback application", 
                "error": f"Main app failed: {e}",
                "status": "fallback",
                "timestamp": datetime.now().isoformat()
            })
        
        @app.get("/health")
        async def health():
            return JSONResponse({
                "status": "unhealthy", 
                "message": "Running on fallback application",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

# Export for Vercel
handler = app

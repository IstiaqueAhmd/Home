import sys
import os

# Add the parent directory to the path so we can import our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    # Import the FastAPI app
    from main import app
    
    # Export the app for Vercel
    handler = app
except ImportError as e:
    print(f"Import error: {e}")
    # Create a simple fallback app
    from fastapi import FastAPI
    fallback_app = FastAPI()
    
    @fallback_app.get("/")
    def read_root():
        return {"message": "Import error occurred", "error": str(e)}
    
    handler = fallback_app

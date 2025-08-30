import os
import sys

# Add the parent directory to the Python path so we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.main import app

# Export the app for Vercel
app = app

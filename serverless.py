"""
Serverless-optimized version of the FastAPI app for Vercel deployment
"""
import os
import sys
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Set environment variables for serverless
os.environ.setdefault('PYTHONPATH', str(current_dir))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging

# Configure logging for serverless
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="House Finance Tracker",
    description="Track house contributions and expenses - Serverless",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": "serverless",
        "message": "Application is running"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return JSONResponse({
        "message": "House Finance Tracker API",
        "version": "1.0.0",
        "status": "running",
        "environment": "serverless",
        "endpoints": {
            "health": "/health",
            "api_docs": "/docs",
            "redoc": "/redoc"
        }
    })

@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "name": "House Finance Tracker API",
        "version": "1.0.0",
        "status": "active",
        "timestamp": datetime.now().isoformat()
    }

# Error handler for 404
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The path {request.url.path} was not found",
            "timestamp": datetime.now().isoformat()
        }
    )

# Error handler for 500
@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

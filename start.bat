@echo off
echo Starting House Finance Tracker...
echo.
echo Database: SQLite (Production-ready PostgreSQL also supported)
echo Environment: %1
echo.

if "%1"=="production" (
    echo Running in production mode...
    .venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
) else (
    echo Running in development mode...
    .venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
)

pause

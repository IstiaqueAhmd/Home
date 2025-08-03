@echo off
echo ====================================
echo House Finance Tracker
echo ====================================

REM Check if virtual environment exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Check if .env file exists
if not exist ".env" (
    echo Creating .env file from template...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit .env file with your MongoDB connection details
    echo Press any key to continue after editing .env file...
    pause
)

REM Ask if user wants to run setup
echo.
set /p setup_choice="Do you want to run the setup wizard? (y/n): "
if /i "%setup_choice%"=="y" (
    echo.
    echo Running setup wizard...
    python setup.py
    echo.
)

REM Start the application
echo Starting FastAPI server...
echo Application will be available at: http://localhost:8000
echo Press Ctrl+C to stop the server
echo.
uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause

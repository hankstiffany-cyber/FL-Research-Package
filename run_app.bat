@echo off
echo ==========================================
echo FORGOTTEN LANGUAGES RESEARCH INTERFACE
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if requirements are installed
echo Checking dependencies...
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    pip install -r requirements.txt
)

echo.
echo Starting web interface...
echo.
echo The app will open in your browser at: http://localhost:8501
echo Press Ctrl+C to stop the server
echo.

streamlit run fl_app.py --server.headless true

pause

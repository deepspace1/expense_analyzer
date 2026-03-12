@echo off
REM Quick Start Script for Expense AI Assistant (Windows)

echo ================================
echo Expense AI Assistant - Quick Start
echo ================================
echo.

REM Check Python
echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Install Python from https://python.org
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo   Found Python %PYTHON_VERSION%

REM Check requirements.txt
if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found!
    pause
    exit /b 1
)

REM Install dependencies
echo.
echo Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo   Dependencies installed

REM Get Groq API Key
echo.
echo WARNING: Groq API Key:
echo   Get your free key at: https://console.groq.com
set /p GROQ_KEY="   Enter your Groq API Key (or press Enter to skip): "

if not "%GROQ_KEY%"=="" (
    set GROQ_API_KEY=%GROQ_KEY%
    echo   API key set
)

REM Start backend
echo.
echo Starting backend...
start "Expense AI - Backend" python main.py
timeout /t 3 /nobreak
echo   Backend started

REM Verify backend is ready
echo   Waiting for backend to be ready...
:check_backend
timeout /t 1 /nobreak
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 goto check_backend
echo   Backend is ready!

REM Start Streamlit
echo.
echo Starting Streamlit frontend...
echo   Opening http://localhost:8501 in your browser...
echo.
echo Press Ctrl+C in each window to stop services
echo.
start "Expense AI - Frontend" cmd /k streamlit run streamlit_app.py --server.port=8501

pause

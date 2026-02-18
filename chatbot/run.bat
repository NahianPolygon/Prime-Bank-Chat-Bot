@echo off
REM Prime Bank Chatbot - Startup Script (Windows)
REM Automates the setup and running of all components

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set BACKEND_DIR=%SCRIPT_DIR%backend
set FRONTEND_DIR=%SCRIPT_DIR%frontend
set VENV_DIR=%SCRIPT_DIR%venv

:menu
cls
echo.
echo ╔════════════════════════════════════════════╗
echo ║   Prime Bank Chatbot - Setup ^& Run         ║
echo ╚════════════════════════════════════════════╝
echo.
echo 1) Quick start (setup + run backend)
echo 2) Backend only (FastAPI server)
echo 3) Frontend only (HTTP server)
echo 4) Check system health
echo 5) Exit
echo.
set /p choice="Select option (1-5): "

if "%choice%"=="1" goto quick_start
if "%choice%"=="2" goto backend
if "%choice%"=="3" goto frontend
if "%choice%"=="4" goto health
if "%choice%"=="5" goto end
goto menu

:quick_start
echo.
echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+
    pause
    goto menu
)
echo [OK] Python found

echo.
echo Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama is not running
    echo Start Ollama with: ollama serve
    pause
    goto menu
)
echo [OK] Ollama running

echo.
echo Setting up virtual environment...
if not exist "%VENV_DIR%" (
    python -m venv "%VENV_DIR%"
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

echo.
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo Installing dependencies...
cd /d "%BACKEND_DIR%"
pip install -r requirements.txt -q
echo [OK] Dependencies installed

echo.
echo Setup complete! Starting backend...
timeout /t 2
goto backend_run

:backend
echo.
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama is not running
    echo Start Ollama with: ollama serve
    pause
    goto menu
)
echo [OK] Ollama running

echo.
echo Starting FastAPI backend...

:backend_run
cd /d "%BACKEND_DIR%"
python app.py
pause
goto menu

:frontend
echo.
echo Starting frontend HTTP server...
echo.
echo Access chatbot at: http://localhost:8001/index.html
echo.
cd /d "%FRONTEND_DIR%"
python -m http.server 8001
goto menu

:health
echo.
echo Checking system health...
echo.
echo Python version:
python --version

echo.
echo Ollama status:
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama is not running
) else (
    echo [OK] Ollama is running
)

echo.
echo Backend API status:
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Backend is not running
) else (
    echo [OK] Backend is running
    curl -s http://localhost:8000/health
)

echo.
pause
goto menu

:end
echo Goodbye!
exit /b 0

@echo off
REM start_client.bat
REM Opens the client CLI in a new terminal window

set PROJECT_DIR=%~dp0
set VENV_PATH=%PROJECT_DIR%venv
set PYTHON_EXE=%VENV_PATH%\Scripts\python.exe

echo.
echo Launching Client CLI in new terminal...
echo.

REM --- VENV Check ---
if not exist "%VENV_PATH%\Scripts\activate.bat" (
    echo.
    echo ERROR: Virtual environment not found!
    echo Please run start_cluster_terminals.bat first
    goto :eof
)

REM Command to launch client in a new CMD window
set CLIENT_CMD=cd /d "%PROJECT_DIR%" ^& call "%VENV_PATH%\Scripts\activate.bat" ^& cls ^& echo =================================================================== ^& echo   🎫 Distributed Ticket Booking System - Client ^& echo =================================================================== ^& echo. ^& echo ✅ Connected to cluster ^& echo 📡 Auth: 127.0.0.1:8000 ^& echo 💳 Payment: 127.0.0.1:6000 ^& echo 🤖 Chatbot: 127.0.0.1:9000 ^& echo 🎫 Booking Nodes: 50051-50053 ^& echo. ^& python client/client-cli.py ^& pause

start "Booking System Client" cmd /k "%CLIENT_CMD%"

echo Client terminal opened!
@echo off
REM start_cluster_terminals.bat
REM Opens each service in a separate CMD window for monitoring.
setlocal

set PROJECT_DIR=%~dp0
set VENV_PATH=%PROJECT_DIR%venv
set PYTHON_EXE=%VENV_PATH%\Scripts\python.exe

echo.
echo ========================================
echo Starting Distributed Booking Cluster
echo ========================================
echo.

REM --- VENV Setup ---
if not exist "%VENV_PATH%\Scripts\activate.bat" (
    echo  Virtual environment not found. Creating it...
    python -m venv "%VENV_PATH%"
    call "%VENV_PATH%\Scripts\activate.bat"
    echo Installing dependencies from requirements.txt...
    pip install -r "%PROJECT_DIR%requirements.txt"
)

REM Command template to launch a service in a new CMD window
set LAUNCH_CMD=cd /d "%PROJECT_DIR%" ^& call "%VENV_PATH%\Scripts\activate.bat" ^& cls ^& echo ======================================= ^& echo. ^& echo Service:

REM --- Launch Services in New Windows ---
echo Launching Auth Service...
start "Auth Service (Port 8000)" cmd /k "%LAUNCH_CMD% Auth Service (Port 8000) ^& python auth-service/auth-server.py"
timeout /t 1 /nobreak > nul

echo Launching Payment Service...
start "Payment Service (Port 6000)" cmd /k "%LAUNCH_CMD% Payment Service (Port 6000) ^& python payment-service/payment-server.py"
timeout /t 1 /nobreak > nul

echo Launching Chatbot Service...
start "Chatbot Service (Port 9000)" cmd /k "%LAUNCH_CMD% Chatbot Service (Port 9000) ^& python chatbot-service/chatbot-server.py"
timeout /t 1 /nobreak > nul

echo Launching Booking Node 1...
start "Booking Node 1 (Port 50051)" cmd /k "%LAUNCH_CMD% Booking Node 1 (Port 50051) ^& python booking-node/main.py --config booking-node/config-node1.json"
timeout /t 2 /nobreak > nul

echo Launching Booking Node 2...
start "Booking Node 2 (Port 50052)" cmd /k "%LAUNCH_CMD% Booking Node 2 (Port 50052) ^& python booking-node/main.py --config booking-node/config-node2.json"
timeout /t 2 /nobreak > nul

echo Launching Booking Node 3...
start "Booking Node 3 (Port 50053)" cmd /k "%LAUNCH_CMD% Booking Node 3 (Port 50053) ^& python booking-node/main.py --config booking-node/config-node3.json"
timeout /t 1 /nobreak > nul

echo.
echo ========================================
echo All services launched!
echo To start the client: start_client.bat
echo To stop all services: stop_cluster.bat
echo ========================================
echo.
pause
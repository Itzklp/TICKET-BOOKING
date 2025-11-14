@echo off
REM start_cluster.bat
REM Starts all services detached in the background.
setlocal

set PROJECT_DIR=%~dp0
set VENV_PATH=%PROJECT_DIR%venv
set PYTHON_EXE=%VENV_PATH%\Scripts\python.exe

if not exist "%VENV_PATH%\Scripts\activate.bat" (
    echo.
    echo ERROR: Virtual environment not found!
    echo Please run start_cluster_terminals.bat first to set up the environment.
    goto :eof
)

call "%VENV_PATH%\Scripts\activate.bat"

echo Starting services in the background...

REM Using 'start /B' runs the processes in the background of the current window, detached.
REM If the current window is closed, these processes may remain orphaned.

echo Starting Auth Service...
start "Auth Service" /B "%PYTHON_EXE%" auth-service/auth-server.py

echo Starting Payment Service...
start "Payment Service" /B "%PYTHON_EXE%" payment-service/payment-server.py

echo Starting Chatbot Service...
start "Chatbot Service" /B "%PYTHON_EXE%" chatbot-service/chatbot-server.py

echo Starting Booking Node 1...
start "Booking Node 1" /B "%PYTHON_EXE%" booking-node/main.py --config booking-node/config-node1.json

REM Sleep for 2 seconds (using timeout command)
timeout /t 2 /nobreak > nul

echo Starting Booking Node 2...
start "Booking Node 2" /B "%PYTHON_EXE%" booking-node/main.py --config booking-node/config-node2.json

REM Sleep for 2 seconds
timeout /t 2 /nobreak > nul

echo Starting Booking Node 3...
start "Booking Node 3" /B "%PYTHON_EXE%" booking-node/main.py --config booking-node/config-node3.json

echo.
echo All services started in the background!
echo Run stop_cluster.bat to stop them.
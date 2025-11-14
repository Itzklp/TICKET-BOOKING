@echo off
REM stop_cluster.bat
setlocal enableDelayedExpansion

:KILL_PROCESS
REM Subroutine to find and kill Python processes whose commandline contains the argument
set TARGET_CMD=%1
echo Attempting to stop: %TARGET_CMD%
for /f "tokens=2" %%i in ('wmic process where "Caption='python.exe' and CommandLine Like '%%%TARGET_CMD%%%'" get ProcessId /value ^| find "="') do (
    set PID=%%i
    if not "!PID!"=="" (
        echo Killing PID: !PID!
        taskkill /PID !PID! /F
    )
)
goto :eof

echo Stopping all cluster services...

REM Note: Running this will terminate the service and client Python processes
call :KILL_PROCESS "auth-server.py"
call :KILL_PROCESS "payment-server.py"
call :KILL_PROCESS "chatbot-server.py"
call :KILL_PROCESS "booking-node\main.py"
call :KILL_PROCESS "client\client-cli.py"

echo.
echo All services stopped!
endlocal
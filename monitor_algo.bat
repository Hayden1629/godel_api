@echo off
REM Barebones Windows batch file to monitor algo_loop.py
REM Restarts the script if it closes for any reason

echo Starting monitor for algo_loop.py...
echo Press Ctrl+C to stop monitoring
echo.

:loop
python algo_loop.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [%date% %time%] Process exited with error code %ERRORLEVEL%
    echo Restarting in 5 seconds...
    timeout /t 5 /nobreak >nul
) else (
    echo.
    echo [%date% %time%] Process exited normally
    echo Restarting in 5 seconds...
    timeout /t 5 /nobreak >nul
)
goto loop


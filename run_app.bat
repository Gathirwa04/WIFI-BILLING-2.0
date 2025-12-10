@echo off
echo Starting WiFi Billing System...
echo Please ensure this window remains OPEN.

:start_server
echo Starting Server...
.\venv\Scripts\python.exe app.py
echo Server crashed or stopped! Restarting in 2 seconds...
timeout /t 2
goto start_server

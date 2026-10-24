@echo off
title ExaSettle Platform Launcher
echo ===================================================
echo Starting ExaSettle Services (Track 01 Prototype)
echo ===================================================

echo [1/3] Starting Exasol Database in WSL Podman...
wsl -d podman-machine-default podman start exasol-db-72362f61

echo [2/3] Starting MiroFish Swarm Intelligence (Port 5001)...
start "MiroFish Backend" /min cmd /c "python vendor\MiroFish\backend\run.py"

echo [3/3] Starting ExaSettle Dashboard Server (Port 8000)...
echo.
echo ===================================================
echo Dashboard is running at: http://127.0.0.1:8000
echo Keep this window open while using the dashboard!
echo ===================================================
echo.
python -m exasettle.cli server --host 127.0.0.1 --port 8000
pause

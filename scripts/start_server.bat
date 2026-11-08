@echo off
rem Double-click to start the backend API server at http://127.0.0.1:8000
rem (API docs: http://127.0.0.1:8000/docs). Close the window or press Ctrl+C to stop.
rem Settings come from .env in the project root (copy .env.example to .env).

title FreedomBank API server
cd /d "%~dp0.."

if not exist ".env" echo Note: no .env found - using defaults. Copy .env.example to .env to configure the LLM.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m uvicorn hackathon_26_freedombank.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir src
) else (
    where uv >nul 2>nul || (echo uv is not installed and .venv is missing. Install uv: https://docs.astral.sh/uv/ & goto :end)
    uv run uvicorn hackathon_26_freedombank.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir src
)

:end
echo.
echo Server stopped.
pause

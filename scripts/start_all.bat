@echo off
rem Double-click to start everything: Ollama (if LLM_PROVIDER=ollama), the API server
rem and the web interface, then open the app in the browser.
rem Each server runs in its own window; close those windows to stop them.

setlocal
title FreedomBank - start all
cd /d "%~dp0.."

if not exist ".env" (
    echo No .env found - creating it from .env.example. Edit .env to change the settings.
    copy ".env.example" ".env" >nul
)

set "PROVIDER=gemini"
for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do if /i "%%a"=="LLM_PROVIDER" set "PROVIDER=%%b"

rem --- 1. Ollama (waits until the model is loaded) ---------------------------
if /i "%PROVIDER%"=="ollama" (
    echo [1/3] Ollama
    set NOPAUSE=1
    call "%~dp0start_ollama.bat" || (
        echo.
        echo Ollama failed to start - see the message above. The app will start anyway,
        echo but evaluations will fail until Ollama works.
        pause
    )
    set NOPAUSE=
) else (
    echo [1/3] LLM_PROVIDER=%PROVIDER% - Ollama not needed, skipping.
)

rem --- 2. API server ----------------------------------------------------------
echo.
echo [2/3] API server: http://127.0.0.1:8000
start "FreedomBank API server" "%~dp0start_server.bat"
for /l %%i in (1,1,30) do (
    curl -s -o nul http://127.0.0.1:8000/health && goto :front
    timeout /t 1 /nobreak >nul
)
echo The API server did not answer within 30 seconds - check its window.

rem --- 3. Frontend -----------------------------------------------------------
:front
echo [3/3] Frontend: http://127.0.0.1:5500
start "FreedomBank frontend" "%~dp0start_frontend.bat"
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:5500

echo.
echo Everything is running. Close the "API server" and "frontend" windows to stop.
timeout /t 10
endlocal

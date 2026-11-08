@echo off
rem Double-click to start Ollama and load the evaluation model into memory.
rem The model name is OLLAMA_MODEL from .env (or .env.example if there is no .env).
rem Another model can be passed as an argument:  start_ollama.bat qwen3.5:9b
rem The Ollama server keeps running after this window closes.

setlocal
title Ollama
cd /d "%~dp0.."

set "ENVFILE=.env"
if not exist "%ENVFILE%" set "ENVFILE=.env.example"
set "MODEL="
set "HOST=http://localhost:11434"
set "NUM_CTX=16384"
if exist "%ENVFILE%" for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%ENVFILE%") do (
    if /i "%%a"=="OLLAMA_MODEL" set "MODEL=%%b"
    if /i "%%a"=="OLLAMA_HOST" set "HOST=%%b"
    if /i "%%a"=="OLLAMA_NUM_CTX" set "NUM_CTX=%%b"
)
if not "%~1"=="" set "MODEL=%~1"
if "%MODEL%"=="" set "MODEL=llama3.1"

where ollama >nul 2>nul || (
    echo Ollama is not installed or not in PATH. Download it from https://ollama.com/download
    goto :fail
)

rem --- 1. Server -------------------------------------------------------------
ollama list >nul 2>nul && (
    echo Ollama server is already running at %HOST%.
    goto :model
)
echo Starting Ollama server...
start "Ollama server" /min ollama serve
for /l %%i in (1,1,30) do (
    ollama list >nul 2>nul && goto :model
    timeout /t 1 /nobreak >nul
)
echo Ollama server did not start within 30 seconds.
goto :fail

rem --- 2. Model --------------------------------------------------------------
:model
ollama show "%MODEL%" >nul 2>nul || (
    echo.
    echo Model "%MODEL%" is not installed. Installed models:
    ollama list
    echo.
    echo Set OLLAMA_MODEL in %ENVFILE% to one of the names above, or download it with:  ollama pull %MODEL%
    goto :fail
)

rem Load with the same context size the backend uses (OLLAMA_NUM_CTX), or Ollama reloads it on the first evaluation.
echo Loading "%MODEL%" into memory with a %NUM_CTX%-token context (the first time can take a minute)...
curl -s -o nul -w "%%{http_code}" %HOST%/api/generate -d "{\"model\":\"%MODEL%\",\"keep_alive\":\"60m\",\"options\":{\"num_ctx\":%NUM_CTX%}}" > "%TEMP%\ollama_load.txt" 2>nul
set /p CODE=<"%TEMP%\ollama_load.txt"
del "%TEMP%\ollama_load.txt" >nul 2>nul
if not "%CODE%"=="200" (
    echo Could not load the model, HTTP status: %CODE%
    goto :fail
)
echo.
ollama ps
echo.
echo Ollama is ready: model "%MODEL%" stays loaded for 60 minutes of inactivity.
if not defined NOPAUSE pause
endlocal & exit /b 0

:fail
echo.
if not defined NOPAUSE pause
endlocal & exit /b 1

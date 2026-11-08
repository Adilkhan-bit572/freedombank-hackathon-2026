@echo off
rem Double-click to serve the web interface (front/) at http://127.0.0.1:5500
rem Close the window or press Ctrl+C to stop.

title FreedomBank frontend
cd /d "%~dp0.."

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo Frontend: http://127.0.0.1:5500   (needs the API server: start_server.bat)
rem Python's built-in server is used with explicit MIME types: on Windows the registry
rem can map .js to text/plain, which makes browsers refuse to load the page's scripts.
"%PY%" -c "import functools, http.server as h; H = functools.partial(h.SimpleHTTPRequestHandler, directory='front'); H.func.extensions_map = {**h.SimpleHTTPRequestHandler.extensions_map, '.js': 'text/javascript', '.css': 'text/css'}; h.ThreadingHTTPServer(('127.0.0.1', 5500), H).serve_forever()"

echo.
echo Frontend stopped.
pause

@echo off
setlocal

set "ROOT=%~dp0"
set "LOG_DIR=%ROOT%logs"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Khong tim thay Python virtual environment:
    echo         %PYTHON%
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] Khong tim thay frontend:
    echo         %FRONTEND_DIR%
    pause
    exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [%date% %time%] Starting Scopus-Ictu local servers>> "%LOG_DIR%\launcher.log"

echo Applying database migrations...
cd /d "%BACKEND_DIR%"
"%PYTHON%" -m alembic upgrade head >> "%LOG_DIR%\migration.log" 2>&1
if errorlevel 1 (
    echo [ERROR] Database migration failed. See:
    echo         %LOG_DIR%\migration.log
    pause
    exit /b 1
)

netstat -ano | findstr /R /C:":8000 .*LISTENING" > nul
if errorlevel 1 (
    start "" /b cmd /c "cd /d ""%BACKEND_DIR%"" && ""%PYTHON%"" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload >> ""%LOG_DIR%\backend.log"" 2>&1"
) else (
    echo Backend port 8000 is already in use; keeping the existing server.
)

netstat -ano | findstr /R /C:":5173 .*LISTENING" > nul
if errorlevel 1 (
    start "" /b cmd /c "cd /d ""%FRONTEND_DIR%"" && npm run dev -- --host 127.0.0.1 >> ""%LOG_DIR%\frontend.log"" 2>&1"
) else (
    echo Frontend port 5173 is already in use; keeping the existing server.
)

echo Da mo 2 server:
echo   Frontend: http://127.0.0.1:5173
echo   Backend:  http://127.0.0.1:8000/docs
echo.
echo Log files:
echo   %LOG_DIR%\backend.log
echo   %LOG_DIR%\frontend.log
echo.
echo Backend va frontend dang chay trong cung cua so nay.
echo Dong cua so nay de ket thuc phien chay.
echo.
pause
exit /b 0

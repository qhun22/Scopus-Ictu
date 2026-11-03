@echo off
setlocal

rem ============================================================
rem  Scopus-Ictu - MOT file khoi dong duy nhat (nhap dup de chay)
rem  PostgreSQL demo -> Backend -> Frontend -> mo trinh duyet.
rem  Dung phan mem:  chon S o cuoi, hoac chay:  scopus-ictu-qhun22.bat stop
rem  Mat khau/cau hinh nam o thu muc secrets NGOAI Git (khong nam trong tep nay).
rem ============================================================

set "ROOT=%~dp0"
if not exist "%ROOT%backend\scripts\demo_launcher.py" (
    if exist "%ROOT%Scopus-Ictu\backend\scripts\demo_launcher.py" (
        set "ROOT=%ROOT%Scopus-Ictu\"
    )
)
for %%I in ("%ROOT%..") do set "DOAN=%%~fI"
set "PYTHON=%DOAN%\_venv_backend_demo_py312\Scripts\python.exe"
set "LAUNCHER=%ROOT%backend\scripts\demo_launcher.py"
set "TEE=%ROOT%backend\scripts\bat_tee.py"
set "PYTHONUTF8=1"

rem --- Thu muc log ---
set "LOG_DIR=%DOAN%\_quan_ly_do_an\logs\demo"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

rem --- Ten file log theo phien (dung PowerShell de lay timestamp nhat quan) ---
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "_DT=%%T"
set "SESSION_LOG=%LOG_DIR%\session_%_DT%.log"

if not exist "%PYTHON%" (
    echo [LOI] Khong tim thay Python 3.12 virtual environment:
    echo       %PYTHON%
    pause
    exit /b 1
)
if not exist "%LAUNCHER%" (
    echo [LOI] Khong tim thay bo dieu phoi khoi dong:
    echo       %LAUNCHER%
    pause
    exit /b 1
)

rem === STOP ===
if /i "%~1"=="stop" (
    echo ============================================================
    echo  Scopus-Ictu - DUNG phan mem
    echo ============================================================
    "%PYTHON%" "%TEE%" "%SESSION_LOG%" "Nguoi dung chay lenh STOP" stop
    echo.
    echo Nhat ky: %SESSION_LOG%
    pause
    exit /b 0
)

rem === MIGRATE ===
if /i "%~1"=="migrate" (
    echo ============================================================
    echo  Scopus-Ictu - NANG CAP schema database
    echo ============================================================
    "%PYTHON%" "%TEE%" "%SESSION_LOG%" "Nguoi dung chay lenh MIGRATE" migrate
    echo.
    echo Nhat ky: %SESSION_LOG%
    pause
    exit /b 0
)

rem === START ===
echo ============================================================
echo  Scopus-Ictu - khoi dong phan mem demo
echo ============================================================
"%PYTHON%" "%TEE%" "%SESSION_LOG%" "Nguoi dung khoi dong phan mem" start
if errorlevel 1 (
    echo.
    echo [LOI] Khoi dong that bai. Doc thong bao o tren.
    echo       Nhat ky phien: %SESSION_LOG%
    echo       Nhat ky dich vu: %LOG_DIR%\backend.log / frontend.log
    pause
    exit /b 1
)

echo.
echo Phan mem dang chay nen. Dong cua so nay KHONG dung phan mem.
echo Nhat ky phien: %SESSION_LOG%
choice /c SK /n /m "Nhan S de DUNG phan mem, K de giu phan mem chay va thoat: "
if errorlevel 2 (
    echo [%date% %time%] HANH VI: Nguoi dung chon GIU phan mem chay (K) >> "%SESSION_LOG%"
    exit /b 0
)
echo [%date% %time%] HANH VI: Nguoi dung chon DUNG phan mem (S) >> "%SESSION_LOG%"
"%PYTHON%" "%TEE%" "%SESSION_LOG%" "Nguoi dung chon DUNG phan mem (S)" stop
echo.
echo Nhat ky: %SESSION_LOG%
pause
exit /b 0

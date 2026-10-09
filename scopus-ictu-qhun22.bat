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
set "PYTHONUTF8=1"

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

if /i "%~1"=="stop" (
    "%PYTHON%" "%LAUNCHER%" stop
    echo.
    pause
    exit /b 0
)

echo ============================================================
echo  Scopus-Ictu - khoi dong phan mem demo
echo ============================================================
"%PYTHON%" "%LAUNCHER%" start
if errorlevel 1 (
    echo.
    echo [LOI] Khoi dong that bai. Doc thong bao [LOI] o tren.
    echo       Nhat ky: %DOAN%\_quan_ly_do_an\logs\demo\
    pause
    exit /b 1
)

echo.
echo Phan mem dang chay nen. Dong cua so nay KHONG dung phan mem.
choice /c SK /n /m "Nhan S de DUNG phan mem, K de giu phan mem chay va thoat: "
if errorlevel 2 exit /b 0
"%PYTHON%" "%LAUNCHER%" stop
echo.
pause
exit /b 0

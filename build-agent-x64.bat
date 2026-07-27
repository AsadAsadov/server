@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV=.venv-agent-x64"
set "PYTHON_CMD=py -3.8-64"
set "ICON_OPTION="

%PYTHON_CMD% -c "import sys,struct; assert sys.version_info[:2]==(3,8); assert struct.calcsize('P')*8==64" >nul 2>&1
if not errorlevel 1 goto python_ok

if exist "%USERPROFILE%\Python38\python.exe" (
  set PYTHON_CMD="%USERPROFILE%\Python38\python.exe"
)

%PYTHON_CMD% -c "import sys,struct; assert sys.version_info[:2]==(3,8); assert struct.calcsize('P')*8==64" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.8.10 64-bit tapilmadi.
  echo Python 3.8.10 x64 qurasdir, sonra bu fayli yeniden ac.
  exit /b 1
)

:python_ok
if exist "%CD%\logo.ico" (
  set ICON_OPTION=--icon="%CD%\logo.ico"
  echo [OK] EXE ikonu tapildi: %CD%\logo.ico
) else (
  echo [INFO] logo.ico tapilmadi, standart EXE ikonu istifade olunacaq.
)

if not exist "%VENV%\Scripts\python.exe" (
  %PYTHON_CMD% -m venv "%VENV%"
  if errorlevel 1 exit /b 1
)

call "%VENV%\Scripts\activate.bat"
python -m pip install --upgrade pip==24.3.1 --retries 20 --timeout 180 --no-cache-dir
if errorlevel 1 exit /b 1
python -m pip install -r requirements-agent-win38.txt --retries 20 --timeout 180 --no-cache-dir
if errorlevel 1 exit /b 1

set "PYINSTALLER_CMD=python -m PyInstaller --noconfirm --clean --onefile --windowed --name BestHomeMonitor-x64 --hidden-import tkinter --collect-submodules pywinauto --collect-submodules comtypes"
%PYINSTALLER_CMD% %ICON_OPTION% cms_remote.py
if errorlevel 1 exit /b 1

copy /Y agent_config.example.json dist\agent_config.example.json >nul

echo.
echo Build tamamlandi:
echo %CD%\dist\BestHomeMonitor-x64.exe
if defined ICON_OPTION echo Ikon: %CD%\logo.ico
echo Konfiqurasiya numunesi:
echo %CD%\dist\agent_config.example.json
endlocal
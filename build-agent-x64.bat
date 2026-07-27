@echo off
setlocal
cd /d "%~dp0"

set "VENV=.venv-agent-x64"
set "PYTHON_CMD=py -3.8-64"

%PYTHON_CMD% -c "import sys,struct; assert sys.version_info[:2]==(3,8); assert struct.calcsize('P')*8==64" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python 3.8.10 64-bit tapilmadi.
  echo Python 3.8.10 x64 qurasdir, sonra bu fayli yeniden ac.
  exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
  %PYTHON_CMD% -m venv "%VENV%"
  if errorlevel 1 exit /b 1
)

call "%VENV%\Scripts\activate.bat"
python -m pip install --upgrade pip==24.3.1
if errorlevel 1 exit /b 1
python -m pip install -r requirements-agent-win38.txt
if errorlevel 1 exit /b 1

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name BestHomeMonitor-x64 ^
  --hidden-import tkinter ^
  --collect-submodules pywinauto ^
  --collect-submodules comtypes ^
  cms_remote.py
if errorlevel 1 exit /b 1

copy /Y agent_config.example.json dist\agent_config.example.json >nul

echo.
echo Build tamamlandi:
echo %CD%\dist\BestHomeMonitor-x64.exe
echo Konfiqurasiya numunesi:
echo %CD%\dist\agent_config.example.json
endlocal

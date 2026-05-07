@echo off
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo Creating local virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create .venv. Please install Python 3.11 or newer.
    pause
    exit /b 1
  )
)

"%VENV_PY%" -c "import docx" >nul 2>nul
if errorlevel 1 (
  echo Installing dependencies from requirements.txt ...
  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
  )
)

"%VENV_PY%" gui.py
pause

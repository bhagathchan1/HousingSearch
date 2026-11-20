@echo off
REM One-command start for Windows: creates a virtualenv, installs deps, starts the app.
cd /d "%~dp0"
if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv
)
.venv\Scripts\python -m pip install -q --upgrade pip
.venv\Scripts\pip install -q -r requirements.txt
echo Starting HousingSearch on http://localhost:8000
.venv\Scripts\python -m housingsearch serve %*

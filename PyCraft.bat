@echo off
rem Double-click to run PyCraft on Windows: on the first launch, makes a virtual environment in .venv
rem and installs the game's dependencies; again whenever pyproject.toml changes.
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo First launch: creating the virtual environment...
    py -3 -m venv .venv 2>nul || python -m venv .venv || (echo Python 3 not found: install it from python.org. & pause & exit /b 1)
    .venv\Scripts\python -m pip install --upgrade pip || (echo Could not update pip. & pause & exit /b 1)
)
for %%F in (pyproject.toml) do set "STAMP=%%~zF %%~tF"
set "DONE="
if exist .venv\.installed set /p DONE=<.venv\.installed
if not "%DONE%"=="%STAMP%" (
    .venv\Scripts\python -m pip install -e . || (echo Dependency install failed. & pause & exit /b 1)
    >.venv\.installed echo %STAMP%
)

.venv\Scripts\python -m pycraft
if errorlevel 1 pause

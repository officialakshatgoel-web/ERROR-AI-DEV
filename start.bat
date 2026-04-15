@echo off
setlocal enabledelayedexpansion
title Error AI - Ultimate Mastermind Combo

:: ----------------------------------------------------
:: OLLAMA STORAGE CONFIGURATION (E: DRIVE)
:: ----------------------------------------------------
set "OLLAMA_STORAGE=E:\ErrorAI_Models"
set "OLLAMA_MODELS=%OLLAMA_STORAGE%"

if not exist "%OLLAMA_STORAGE%" (
    echo Creating model storage directory on E: drive...
    mkdir "%OLLAMA_STORAGE%" 2>nul
    if errorlevel 1 (
        echo [WARN] Could not create E:\ErrorAI_Models. Using default C: drive space.
        set "OLLAMA_MODELS="
    )
)

:: Define Colors (ANSI)
set "C_BLUE=[94m"
set "C_GREEN=[92m"
set "C_YELLOW=[93m"
set "C_RED=[91m"
set "C_CYAN=[96m"
set "C_RESET=[0m"
set "ESC="

:: Enable ANSI if possible (Windows 10+)
for /f "tokens=2 delims=[]" %%a in ('ver') do for /f "tokens=2 delims=. " %%b in ("%%a") do if %%b geq 10 (
    set "ESC= "
    for /f "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do set "ESC=%%b"
)

echo %ESC%%C_CYAN%====================================================%ESC%%C_RESET%
echo %ESC%%C_CYAN%  ERROR AI - ADVANCED DEPLOYMENT ^& PROJECT PUSH %ESC%%C_RESET%
echo %ESC%%C_CYAN%====================================================%ESC%%C_RESET%
if defined OLLAMA_MODELS (
    echo %ESC%%C_GREEN%  STORAGE: %OLLAMA_MODELS% %ESC%%C_RESET%
)
echo %ESC%%C_CYAN%====================================================%ESC%%C_RESET%
echo.

:: 1. Process Cleanup (Fixes Telegram conflict)
echo %ESC%%C_YELLOW%[1/6] Cleaning up previous instances...%ESC%%C_RESET%
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE ne %TITLE%" /T >nul 2>&1
echo [OK] Old processes cleaned.
echo.

:: 2. Check for Requirements
echo %ESC%%C_YELLOW%[2/6] Checking System Requirements...%ESC%%C_RESET%

:: Check Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %ESC%%C_RED%[ERROR] Git is not installed!%ESC%%C_RESET%
    pause
    exit /b
) else (
    echo [OK] Git detected.
)

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %ESC%%C_RED%[ERROR] Python is not installed!%ESC%%C_RESET%
    pause
    exit /b
) else (
    echo [OK] Python detected.
)

:: Check Ollama
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %ESC%%C_YELLOW%[WARN] Ollama is not installed or not in PATH!%ESC%%C_RESET%
    echo Please install Ollama from https://ollama.com to use AI features.
) else (
    echo [OK] Ollama detected.
)
echo.

:: 3. Check .env file
echo %ESC%%C_YELLOW%[3/6] Checking Configuration...%ESC%%C_RESET%
if not exist .env (
    if exist .env.example (
        echo [INFO] Creating .env from .env.example...
        copy .env.example .env >nul
        echo %ESC%%C_RED%[ACTION REQUIRED] Please edit .env and add your tokens before continuing!%ESC%%C_RESET%
        notepad .env
        pause
    ) else (
        echo %ESC%%C_RED%[ERROR] .env file is missing!%ESC%%C_RESET%
        pause
    )
) else (
    echo [OK] .env file detected.
)
echo.

:: 4. Sync with GitHub
echo %ESC%%C_YELLOW%[4/6] Syncing with GitHub...%ESC%%C_RESET%
echo Staging files...
git add .
echo Committing changes...
git commit -m "Auto-deployment update: %date% %time%" >nul 2>&1
echo Pushing to GitHub...
git push -u origin main
echo %ESC%%C_GREEN%[OK] Project synced successfully!%ESC%%C_RESET%
echo.

:: 5. Python Dependencies ^& Models
echo %ESC%%C_YELLOW%[5/6] Finalizing Dependencies ^& Models...%ESC%%C_RESET%
echo Installing Python libraries...
python -m pip install -r requirements.txt --quiet --user

:: Pull Models
echo Checking/Pulling AI Models (to E: drive location)...
echo - Dolphin 3 (Chat)
ollama pull dolphin3:8b
echo - Qwen 2.5 Coder (Coding)
ollama pull qwen2.5-coder:32b
echo %ESC%%C_GREEN%[OK] Everything is ready!%ESC%%C_RESET%
echo.

:: 6. Launch
echo %ESC%%C_CYAN%====================================================%ESC%%C_RESET%
echo %ESC%%C_CYAN%   STARTING ERROR AI ECOSYSTEM...%ESC%%C_RESET%
echo %ESC%%C_CYAN%====================================================%ESC%%C_RESET%
echo.

:: Start the application
python main.py

pause

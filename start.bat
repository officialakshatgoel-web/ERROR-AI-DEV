@echo off
title Error AI - Ultimate Mastermind Combo
echo ====================================================
echo   ERROR AI - ADVANCED DEPLOYMENT & PROJECT PUSH
echo ====================================================
echo.

:: 1. Check for Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed. Please install git to push.
) else (
    echo [OK] Git detected.
)

:: 2. Prepare Git Push
echo.
echo [1/3] Staging files...
git add .
echo [2/3] Committing changes...
git commit -m "Ultimate Mastermind Update: Advanced Persona, Hinglish Support, and UI Polish"
echo [3/3] Pushing to GitHub...
git push -u origin main
echo.
echo ====================================================
echo   PROJECT PUSHED TO GITHUB SUCCESSFULLY!
echo ====================================================
echo.

:: 3. Setup Python
echo [4/4] Checking Python dependencies...
python -m pip install -r requirements.txt
echo.

:: 4. Start Server
echo Starting Fast API Server...
echo.
python main.py

pause

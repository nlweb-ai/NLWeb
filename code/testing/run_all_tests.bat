@echo off
REM Copyright (c) 2025 Microsoft Corporation.
REM Licensed under the MIT License

REM Script to run all NLWeb tests on Windows
REM This script should be run from the code directory

echo ===============================================
echo Running NLWeb Test Suite
echo ===============================================
echo.

REM Check if we're in the correct directory
if not exist "testing\run_tests.py" (
    echo Error: This script must be run from the code directory.
    echo Please navigate to the code directory and run: testing\run_all_tests.bat
    exit /b 1
)

REM Set default Python command
if "%PYTHON_CMD%"=="" set PYTHON_CMD=python

REM Check if Python is available
where %PYTHON_CMD% >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Python not found. Please ensure Python is installed and in your PATH.
    exit /b 1
)

echo Using Python: %PYTHON_CMD%
echo.

REM Run all default test files
echo Running all test types...
echo ----------------------------------------
%PYTHON_CMD% -m testing.run_tests --all

REM Check exit code
if %ERRORLEVEL% equ 0 (
    echo.
    echo ===============================================
    echo All tests completed successfully!
    echo ===============================================
) else (
    echo.
    echo ===============================================
    echo Tests completed with errors. Please check the output above.
    echo ===============================================
    exit /b 1
)
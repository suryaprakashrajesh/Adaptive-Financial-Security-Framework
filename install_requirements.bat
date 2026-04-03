@echo off
REM Install all Python requirements for QRATM project

ECHO Installing/upgrading pip...
python -m pip install --upgrade pip
IF %ERRORLEVEL% NEQ 0 (
    ECHO Failed to upgrade pip. Exiting.
    EXIT /B 1
)

ECHO Installing requirements from requirements.txt...
pip install -r requirements.txt
IF %ERRORLEVEL% EQU 0 (
    ECHO.
    ECHO All requirements installed successfully!
) ELSE (
    ECHO.
    ECHO There was a problem installing the requirements.
)
PAUSE

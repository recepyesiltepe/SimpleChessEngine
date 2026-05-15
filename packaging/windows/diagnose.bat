@echo off
REM Run from the folder that contains SimpleChessEngine.exe and _internal\
cd /d "%~dp0"
echo Running SimpleChessEngine.exe ...
SimpleChessEngine.exe
set ERR=%ERRORLEVEL%
echo.
echo Exit code: %ERR%
echo.
set LOG=%LOCALAPPDATA%\simple-chess-engine\launch.log
if exist "%LOG%" (
  echo === %LOG% ===
  type "%LOG%"
) else (
  echo No log at %LOG%
)
echo.
pause

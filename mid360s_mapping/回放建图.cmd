@echo off
if "%~1"=="" (
  echo Drag the raw bag folder onto this file.
  pause
  exit /b 2
)
wsl.exe -d Ubuntu-22.04 -- bash /mnt/e/chatgpt_project/mid360s_mapping/demo.sh --replay "%~f1"
if errorlevel 1 pause

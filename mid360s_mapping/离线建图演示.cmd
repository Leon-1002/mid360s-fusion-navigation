@echo off
wsl.exe -d Ubuntu-22.04 -- bash /mnt/e/chatgpt_project/mid360s_mapping/demo.sh
if errorlevel 1 pause

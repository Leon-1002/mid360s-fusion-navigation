@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0启动相机.ps1" -HardwareTrigger -TriggerSource Line2
pause

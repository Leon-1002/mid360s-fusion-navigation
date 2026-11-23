@echo off
wsl.exe -d Ubuntu-22.04 -- bash -c "source /opt/ros/humble/setup.bash && timeout 60 ros2 service call /map_save std_srvs/srv/Trigger {}"
pause

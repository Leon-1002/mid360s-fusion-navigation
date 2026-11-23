#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$HOME/mid360s_lio/install/setup.bash"
export ROS_DOMAIN_ID=83 ROS_LOCALHOST_ONLY=1
project=$(cd "$(dirname "$0")" && pwd)
bash "$project/check-offline.sh" > "$project/validation-normal-diagnostic.log" 2>&1 &
test_pid=$!
sleep 5
timeout 5 ros2 topic info /livox/imu --verbose --no-daemon || echo "Graph probe timed out"
timeout 5 ros2 topic echo /livox/imu --once || echo "IMU probe timed out"
ros2 param get /laser_mapping use_sim_time
wait "$test_pid"

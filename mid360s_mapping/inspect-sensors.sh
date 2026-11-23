#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$HOME/mid360s_lio/install/setup.bash"
export LD_LIBRARY_PATH="$HOME/mid360s_lio/sdk-build/sdk_core:$LD_LIBRARY_PATH"
export ROS_DOMAIN_ID=86 ROS_LOCALHOST_ONLY=1
project=$(cd "$(dirname "$0")" && pwd)
session=$(mktemp -d "$project/static-$(date +%Y%m%d-%H%M%S)-XXXX")
cd "$session"
echo "静止数据采集，请保持雷达不动。输出目录：$session"
setsid ros2 run livox_ros_driver2 livox_ros_driver2_node --ros-args -p user_config_path:="$project/MID360s_config.json" -p xfer_format:=1 -p publish_freq:=10.0 >driver.log 2>&1 &
driver=$!
setsid ros2 bag record -o raw /livox/lidar /livox/imu >record.log 2>&1 &
recorder=$!
cleanup() {
    kill -INT -- "-$recorder" "-$driver" 2>/dev/null || true
    wait "$recorder" || true
    wait "$driver" || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
python3 "$project/inspect_sensors.py" | tee progress.log

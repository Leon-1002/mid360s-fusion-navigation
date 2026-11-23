#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$HOME/mid360s_lio/install/setup.bash"
export ROS_DOMAIN_ID=0
project=$(cd "$(dirname "$0")" && pwd)
session=$(mktemp -d "$project/observed-$(date +%Y%m%d-%H%M%S)-XXXX")
cd "$session"
echo "读取当前正在运行的雷达数据，输出目录 $session"
setsid ros2 bag record -o raw /livox/lidar /livox/imu /Odometry >record.log 2>&1 &
recorder=$!
cleanup() {
    kill -INT -- "-$recorder" 2>/dev/null || true
    wait "$recorder" || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
python3 "$project/inspect_sensors.py" | tee progress.log

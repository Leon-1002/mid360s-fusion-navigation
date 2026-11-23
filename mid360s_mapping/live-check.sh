#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$HOME/mid360s_lio/install/setup.bash"
export ROS_DOMAIN_ID=0 ROS_LOCALHOST_ONLY=0
project=$(cd "$(dirname "$0")" && pwd)
session=$(mktemp -d "$project/live-check-$(date +%Y%m%d-%H%M%S)-XXXX")
cd "$session"
echo "现场验收数据目录：$session"
setsid ros2 bag record --include-unpublished-topics --qos-profile-overrides-path "$project/record_qos.yaml" -o raw /livox/lidar /livox/imu /Odometry >record.log 2>&1 &
recorder=$!
cleanup() {
    kill -INT -- "-$recorder" 2>/dev/null || true
    wait "$recorder" || { echo "录制器异常退出，请检查 record.log" >&2; exit 1; }
}
trap cleanup EXIT
trap 'exit 130' INT TERM
python3 "$project/live_health.py" --recorder-pid "$recorder" "$@" | tee health.log

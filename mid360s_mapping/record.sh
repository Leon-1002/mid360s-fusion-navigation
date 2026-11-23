#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$HOME/mid360s_lio/install/setup.bash"
project=$(cd "$(dirname "$0")" && pwd)
prefix=field
if [[ ${1:-} == --demo ]]; then
    export ROS_DOMAIN_ID=84 ROS_LOCALHOST_ONLY=1
    prefix=synthetic
fi
session=$(mktemp -d "$project/$prefix-$(date +%Y%m%d-%H%M%S)-XXXX")
echo "原始数据目录：$(wslpath -w "$session/raw")"
echo "出现订阅提示后开始采集。按 Ctrl+C 结束录制。"
exec ros2 bag record --include-unpublished-topics --qos-profile-overrides-path "$project/record_qos.yaml" -o "$session/raw" /livox/lidar /livox/imu

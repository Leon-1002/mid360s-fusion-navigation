#!/usr/bin/env bash
set -eo pipefail
exec 8>"/tmp/mid360s-mapping-$UID.lock"
flock -n 8 || { echo "建图程序已经在运行，请先结束现有建图再启动回放或演示。"; exit 1; }
source /opt/ros/humble/setup.bash
source "$HOME/mid360s_lio/install/setup.bash"
export ROS_DOMAIN_ID=84 ROS_LOCALHOST_ONLY=1
mode=demo
extra_launch_args=()
if [[ ${1:-} == --replay ]]; then
    mode=replay
    export ROS_DOMAIN_ID=85
    if [[ $2 == /* ]]; then
        bag=$(realpath "$2")
    else
        bag=$(realpath "$(wslpath -u "$2")")
    fi
    [[ -f "$bag/metadata.yaml" ]] || { echo "找不到录包目录：$bag"; exit 2; }
    extra_launch_args=("${@:3}")
fi
exec 9>"/tmp/mid360s-$mode-$UID.lock"
flock -n 9 || { echo "已有离线演示正在运行。请先结束上一次演示。"; exit 1; }
project=$(cd "$(dirname "$0")" && pwd)
session=$(mktemp -d "$project/$mode-$(date +%Y%m%d-%H%M%S)-XXXX")
cd "$session"
echo "本次离线地图目录：$(wslpath -w "$session")"
echo "正在启动 FAST-LIO 和 RViz，等待地图窗口连接……"
setsid ros2 launch "$project/live.launch.py" driver:=false "${extra_launch_args[@]}" >mapping.log 2>&1 &
mapping_pid=$!
cleanup() {
    if [[ -n ${recorder:-} ]]; then
        kill -INT -- "-$recorder" 2>/dev/null || true
        wait "$recorder" || true
    fi
    kill -INT -- "-$mapping_pid" 2>/dev/null || true
    wait "$mapping_pid" || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
if [[ ${1:-} == --record ]]; then
    echo "同步录制本次合成点云与 IMU"
    setsid ros2 bag record -o "$session/raw" /livox/lidar /livox/imu >record.log 2>&1 &
    recorder=$!
fi
test_cmd=(python3 "$project/check_pipeline.py" --wait-for-rviz)
if [[ $mode == replay ]]; then
    test_cmd=(python3 "$project/replay.py" "$bag")
fi
if ! "${test_cmd[@]}" | tee progress.log; then
    tail -40 mapping.log
    exit 1
fi
if [[ -n ${recorder:-} ]]; then
    kill -INT -- "-$recorder"
    wait "$recorder"
    unset recorder
    ros2 bag info "$session/raw"
fi
echo "地图已保存为 map.pcd。可以在 RViz 中旋转和缩放，查看完成后回到此窗口按 Enter 退出。"
read -r || true

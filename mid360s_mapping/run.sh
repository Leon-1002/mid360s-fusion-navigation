#!/usr/bin/env bash
set -eo pipefail
exec 8>"/tmp/mid360s-mapping-$UID.lock"
flock -n 8 || { echo "建图程序已经在运行，请使用已打开的窗口。"; exit 1; }
source /opt/ros/humble/setup.bash
source "$HOME/mid360s_lio/install/setup.bash"
# livox_ros_driver2 loads the SDK with dlopen at runtime. colcon does not
# export this separately, so make the locally built SDK visible to the node.
sdk_dir="$HOME/mid360s_lio/sdk-build/sdk_core"
if [[ ! -f "$sdk_dir/liblivox_lidar_sdk_shared.so" ]]; then
    echo "找不到 Livox SDK 动态库: $sdk_dir/liblivox_lidar_sdk_shared.so" >&2
    exit 3
fi
export LD_LIBRARY_PATH="$sdk_dir:$LD_LIBRARY_PATH"
project=$(cd "$(dirname "$0")" && pwd)
if [[ ${1:-} != --offline ]]; then
    if ! ip -o -4 addr show | grep -q 'inet 192\.168\.1\.50/'; then
        echo "Ubuntu 未检测到雷达网卡 192.168.1.50。请检查以太网、Windows 雷达网卡 IP 以及 WSL 镜像网络。" >&2
        exit 2
    fi
else
    shift
    set -- driver:=false "$@"
fi
session=$(mktemp -d "$project/session-$(date +%Y%m%d-%H%M%S)-XXXX")
cd "$session"
exec > >(tee -a "$session/console.log") 2>&1
echo "本次建图目录: $session"
exec ros2 launch "$project/live.launch.py" "$@"

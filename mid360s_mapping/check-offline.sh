#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$HOME/mid360s_lio/install/setup.bash"
export ROS_DOMAIN_ID=83
export ROS_LOCALHOST_ONLY=1
project=$(cd "$(dirname "$0")" && pwd)
exec 8>"/tmp/mid360s-mapping-$UID.lock"
flock -n 8 || { echo "请先结束当前建图，避免共享日志被覆盖。"; exit 1; }
cd "$(mktemp -d /tmp/mid360s-check-XXXXXX)"
setsid ros2 launch "$project/live.launch.py" driver:=false rviz:=false >mapping.log 2>&1 &
pid=$!
trap 'kill -INT -- "-$pid" 2>/dev/null || true; wait "$pid" || true' EXIT
if ! python3 "$project/check_pipeline.py" "$@"; then
    tail -50 mapping.log
    exit 1
fi

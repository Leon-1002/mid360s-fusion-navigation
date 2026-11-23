#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$HOME/mid360s_lio/install/setup.bash"
export ROS_DOMAIN_ID=0 ROS_LOCALHOST_ONLY=0
project=$(cd "$(dirname "$0")" && pwd)
session=$(mktemp -d "$project/recorder-check-$(date +%Y%m%d-%H%M%S)-XXXX")
cd "$session"
echo "Recorder validation: $session"
setsid ros2 bag record --include-unpublished-topics --qos-profile-overrides-path "$project/record_qos.yaml" -o raw /livox/lidar /livox/imu /Odometry >record.log 2>&1 &
recorder=$!
trap 'kill -INT -- "-$recorder" 2>/dev/null || true; wait "$recorder" || true' EXIT
sleep 25
kill -INT -- "-$recorder"
wait "$recorder"
trap - EXIT
python3 - <<'PY'
import sqlite3
from pathlib import Path
db = sqlite3.connect(f'file:{Path("raw/raw_0.db3").resolve()}?mode=ro', uri=True)
counts = dict(db.execute('SELECT topics.name, count(*) FROM messages JOIN topics ON messages.topic_id=topics.id GROUP BY topics.name'))
print(counts)
ratio = counts.get('/livox/imu', 0) / max(counts.get('/livox/lidar', 0), 1)
print('IMU/lidar count ratio:', ratio, '(expected about 20)')
if counts.get('/livox/lidar', 0) < 150 or not 19 <= ratio <= 21:
    raise RuntimeError('Recorder still missing data; not accepted')
print('PASS: sensor recording rates match 200 Hz IMU / 10 Hz lidar')
PY
timeout 30 ros2 service call /map_save std_srvs/srv/Trigger '{}'

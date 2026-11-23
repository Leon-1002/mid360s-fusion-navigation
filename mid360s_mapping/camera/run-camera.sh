#!/bin/bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$(dirname "$0")/sdk-env.sh"
exec 9>/tmp/zm-camera-$UID.lock
flock -n 9 || { echo 'Camera capture is already running'; exit 1; }
session=$(mktemp -d "$CAMERA_DIR/capture-$(date +%Y%m%d-%H%M%S)-XXXX")
cd "$session"
echo "Camera session: $session"
echo 'Camera acquisition. Header timestamp = host receive time; see node log for trigger mode.'
"$CAMERA_DIR/build/zm_camera" "$@" 2>&1 | tee console.log

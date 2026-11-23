#!/usr/bin/env bash
# Loader and CLI checks only; does not open or configure a camera.
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$(dirname "$0")/sdk-env.sh"
file "$CAMERA_BUILD_DIR/zm_camera" "$CAMERA_SDK_LIBRARY"
loader_report="$CAMERA_DIR/loader-$CAMERA_ARCH-$(date +%Y%m%d-%H%M%S).txt"
ldd "$CAMERA_BUILD_DIR/zm_camera" > "$loader_report"
if grep -q 'not found' "$loader_report"; then cat "$loader_report"; exit 3; fi
python3 - <<'PY'
import ctypes,os
sdk=ctypes.CDLL(os.environ['CAMERA_SDK_LIBRARY'])
sdk.IMV_GetVersion.restype=ctypes.c_char_p
print('Native SDK load PASS:',sdk.IMV_GetVersion().decode())
PY
"$CAMERA_BUILD_DIR/zm_camera" --ros-args -p check_runtime:=true | tee "$CAMERA_DIR/ros-runtime-$CAMERA_ARCH.txt"
printf 'Native build, SDK loader and ROS node initialization checks PASS. No camera acquisition started.\n'

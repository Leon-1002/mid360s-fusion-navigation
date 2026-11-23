#!/bin/bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$(dirname "$0")/sdk-env.sh"
mkdir -p "$CAMERA_DIR/runtime"
ln -sfn "$CAMERA_LIB/liblog4cpp.so" "$CAMERA_DIR/runtime/liblog4cpp.so.5"
ln -sfn "$CAMERA_LIB/libMVSDK.so.2.1.0.194985" "$CAMERA_DIR/runtime/libMVSDK.so"
cmake -S "$CAMERA_DIR" -B "$CAMERA_DIR/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$CAMERA_DIR/build" -j2

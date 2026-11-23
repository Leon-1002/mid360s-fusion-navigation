#!/bin/bash
set -eo pipefail
source /opt/ros/humble/setup.bash
source "$(dirname "$0")/sdk-env.sh"
mkdir -p "$CAMERA_RUNTIME"
ln -sfn "$CAMERA_LIB/liblog4cpp.so" "$CAMERA_RUNTIME/liblog4cpp.so.5"
ln -sfn "$CAMERA_SDK_LIBRARY" "$CAMERA_RUNTIME/libMVSDK.so"
cmake -S "$CAMERA_DIR" -B "$CAMERA_BUILD_DIR" -DCMAKE_BUILD_TYPE=Release \
    "-DCAMERA_SDK_ROOT=$CAMERA_SDK_ROOT" "-DCAMERA_SDK_LIBRARY=$CAMERA_SDK_LIBRARY" \
    "-DCAMERA_GENICAM_LIB=$CAMERA_GENICAM_LIB" "-DCAMERA_RUNTIME_DIR=$CAMERA_RUNTIME"
cmake --build "$CAMERA_BUILD_DIR" -j2

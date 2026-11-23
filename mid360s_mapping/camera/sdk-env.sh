#!/bin/bash
CAMERA_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
CAMERA_LIB="$CAMERA_DIR/vendor/extracted/lib/m64x86"
export LD_LIBRARY_PATH="$CAMERA_DIR/runtime:$CAMERA_LIB:$CAMERA_LIB/GenICam/bin/Linux64_x64:${LD_LIBRARY_PATH:-}"

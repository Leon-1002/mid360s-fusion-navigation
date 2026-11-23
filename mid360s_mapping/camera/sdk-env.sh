#!/bin/bash
CAMERA_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
CAMERA_ARCH=$(uname -m)
case "$CAMERA_ARCH" in
    x86_64)
        CAMERA_SDK_ROOT=${ZMCAMERA_SDK_ROOT:-"$CAMERA_DIR/vendor/extracted"}
        CAMERA_LIB="$CAMERA_SDK_ROOT/lib/m64x86"
        CAMERA_GENICAM_LIB="$CAMERA_LIB/GenICam/bin/Linux64_x64"
        CAMERA_RUNTIME="$CAMERA_DIR/runtime"
        CAMERA_BUILD_DIR="$CAMERA_DIR/build"
        CAMERA_ELF_MACHINE=62
        ;;
    aarch64)
        CAMERA_SDK_ROOT=${ZMCAMERA_SDK_ROOT:-"$CAMERA_DIR/vendor/arm64/extracted"}
        CAMERA_LIB="$CAMERA_SDK_ROOT/lib/Jetson_TX1"
        CAMERA_GENICAM_LIB="$CAMERA_LIB/GenICam/bin"
        CAMERA_RUNTIME="$CAMERA_DIR/runtime-aarch64"
        CAMERA_BUILD_DIR="$CAMERA_DIR/build-aarch64"
        CAMERA_ELF_MACHINE=183
        ;;
    *) echo "Unsupported camera host architecture: $CAMERA_ARCH" >&2; return 2 ;;
esac
camera_sdk_candidates=("$CAMERA_LIB"/libMVSDK.so.*)
if [[ ${#camera_sdk_candidates[@]} != 1 || ! -f ${camera_sdk_candidates[0]} ]]; then
    echo "Expected exactly one versioned MVSDK library in $CAMERA_LIB" >&2
    return 2
fi
CAMERA_SDK_LIBRARY=${camera_sdk_candidates[0]}
python3 - "$CAMERA_SDK_LIBRARY" "$CAMERA_ELF_MACHINE" <<'PY'
import struct,sys
with open(sys.argv[1],'rb') as stream: header=stream.read(20)
if len(header)!=20 or header[:6]!=b'\x7fELF\x02\x01':
    raise SystemExit('SDK is not little-endian ELF64')
if struct.unpack_from('<H',header,18)[0]!=int(sys.argv[2]):
    raise SystemExit('SDK architecture does not match the host; refusing to load')
PY
if [[ $? != 0 ]]; then return 2; fi
export CAMERA_DIR CAMERA_ARCH CAMERA_SDK_ROOT CAMERA_LIB CAMERA_GENICAM_LIB
export CAMERA_RUNTIME CAMERA_BUILD_DIR CAMERA_SDK_LIBRARY
export LD_LIBRARY_PATH="$CAMERA_RUNTIME:$CAMERA_LIB:$CAMERA_GENICAM_LIB:${LD_LIBRARY_PATH:-}"

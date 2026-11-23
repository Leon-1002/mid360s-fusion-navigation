#!/usr/bin/env bash
set -euo pipefail
cd /home/door/mid360s_orin_20261123/camera
test ! -e vendor/arm64/extracted || { echo 'ARM SDK directory exists; inspect it instead of overwriting.' >&2; exit 2; }
sh vendor/packages/MVviewer_Ver2.3.2_Linux_arm_aarch64_Build20220402.run \
    --noexec --nox11 --nochown --target "$PWD/vendor/arm64/extracted"
bash build.sh 2>&1 | tee build-aarch64.log
bash check-runtime.sh
printf 'Camera ARM64 build and loader checks passed; capture is not yet tested.\n'

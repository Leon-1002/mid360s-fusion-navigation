#!/usr/bin/env bash
set -euo pipefail
cd /home/door/mid360s_orin_20261123
python3 - <<'PY'
import json,hashlib
from pathlib import Path
m=json.loads(Path('lidar-source-manifest.json').read_text())
p=Path(m['archive'])
if hashlib.sha256(p.read_bytes()).hexdigest()!=m['sha256']:
    raise SystemExit('Source archive checksum mismatch')
print('Source archive checksum PASS')
PY
test ! -e workspace || { echo 'Workspace already exists; refusing to extract over it.' >&2; exit 2; }
tar -xzf lidar-source-20261123.tar.gz
bash preflight.sh > preflight-before.txt
bash build-lidar.sh 2>&1 | tee build-lidar.log

"""Locate clock-corrupted clouds and motion in a CDR rosbag without decoding points."""
import json
import math
import sqlite3
import struct
import sys
from pathlib import Path
import numpy as np

path = Path(sys.argv[1])
if not (path.parent / "metadata.yaml").is_file():
    raise RuntimeError("Stop recording and finalize/reindex the bag before auditing")
report = {"clock_events": [], "bad_clouds": [], "imu_windows": {}}
first_time = None
last_imu = None
with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as db:
    topics = dict(db.execute("SELECT id, name FROM topics"))
    for ident, tid, received, data in db.execute("SELECT id,topic_id,timestamp,data FROM messages ORDER BY id"):
        topic = topics[tid]
        if topic not in ("/livox/imu", "/livox/lidar"):
            continue
        if data[:2] != b"\x00\x01":
            raise ValueError("Only CDR little-endian is supported")
        sec, ns, length = struct.unpack_from("<iII", data, 4)
        stamp = sec * 10**9 + ns
        if first_time is None:
            first_time = stamp
        elapsed = (stamp - first_time) / 1e9
        offset = 4 + ((16 + length - 4 + 7)//8)*8
        if topic == "/livox/imu":
            if last_imu is not None and stamp < last_imu:
                report["clock_events"].append(dict(id=ident, elapsed_s=elapsed, header_ns=stamp, received_ns=received, delta_s=(stamp-last_imu)/1e9))
            last_imu = stamp
            gyro = struct.unpack_from("<3d", data, offset + 32 + 72)
            accel = struct.unpack_from("<3d", data, offset + 32 + 72 + 24 + 72)
            bucket = report["imu_windows"].setdefault(str(int(elapsed//5)*5), dict(count=0, max_gyro=0., max_accel_deviation_g=0.))
            bucket["count"] += 1
            bucket["max_gyro"] = max(bucket["max_gyro"], math.sqrt(sum(x*x for x in gyro)))
            bucket["max_accel_deviation_g"] = max(bucket["max_accel_deviation_g"], abs(math.sqrt(sum(x*x for x in accel))-1))
        else:
            timebase, pointnum = struct.unpack_from("<QI", data, offset)
            n = struct.unpack_from("<I", data, offset + 16)[0]
            if n != pointnum or timebase != stamp:
                raise ValueError("Unexpected CustomMsg layout")
            offsets = np.ndarray((n,), dtype="<u4", buffer=data, offset=offset+20, strides=(20,))
            duration = float(offsets.max()) / 1e9 if n else 0.
            if duration > .2:
                report["bad_clouds"].append(dict(id=ident, elapsed_s=elapsed, header_ns=stamp, received_ns=received, points=n, duration_s=duration))
report["first_header_ns"] = first_time
report["last_imu_ns"] = last_imu
output = path.parent.parent / "clock_motion_audit.json"
output.write_text(json.dumps(report, indent=2))
print("Clock events:", report["clock_events"])
print("Corrupted/long clouds:", report["bad_clouds"])
print("Motion windows (5 s):", {k:v for k,v in report["imu_windows"].items() if v["max_gyro"] > .08 or v["max_accel_deviation_g"] > .15})
print("Saved", output)

"""Review a finalized capture using a local disposable database copy."""
import json
import math
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import numpy as np

project = Path(__file__).resolve().parent
capture, session = map(Path, sys.argv[1:3])
if not (capture / "raw/metadata.yaml").is_file():
    raise RuntimeError("Recording is not finalized")
health = json.loads((capture / "live_health.json").read_text())
poses = np.asarray(health["poses"])
position = poses[:, 1:4]
dist = np.linalg.norm(position - position[0], axis=1)
q0, q1 = poses[0, 4:8], poses[-1, 4:8]
angle = math.degrees(2 * math.acos(min(1., abs(np.dot(q0, q1)) / (np.linalg.norm(q0)*np.linalg.norm(q1)))))
summary = dict(odometry_frames=len(poses), duration_s=float(poses[-1,0]-poses[0,0]),
               endpoint_displacement_m=float(dist[-1]), max_displacement_m=float(dist.max()),
               endpoint_orientation_error_deg=angle,
               last_10s_position_min_max_m=[float(dist[poses[:,0] > poses[-1,0]-10].min()), float(dist[poses[:,0] > poses[-1,0]-10].max())])
with tempfile.TemporaryDirectory(prefix="mid360s-final-review-") as temp:
    local = Path(temp) / "raw"
    local.mkdir()
    shutil.copy2(capture / "raw/raw_0.db3", local / "raw_0.db3")
    shutil.copy2(capture / "raw/metadata.yaml", local / "metadata.yaml")
    with sqlite3.connect(f"file:{local / 'raw_0.db3'}?mode=ro", uri=True) as db:
        summary["recorded_messages"] = dict(db.execute("SELECT topics.name,count(*) FROM messages JOIN topics ON messages.topic_id=topics.id GROUP BY topics.name"))
    for script in ("audit_bag_clock.py", "analyze_bag_motion.py"):
        result = subprocess.run([sys.executable, str(project / script), str(local / "raw_0.db3")], check=True, text=True, capture_output=True)
        (capture / f"{Path(script).stem}.log").write_text(result.stdout)
        print(result.stdout, flush=True)
    audit = json.loads((Path(temp) / "clock_motion_audit.json").read_text())
    (capture / "clock_motion_audit.json").write_text(json.dumps(audit, indent=2))
    summary["imu_clock_reversals"] = len(audit["clock_events"])
    summary["clouds_with_duration_over_200ms"] = len(audit["bad_clouds"])
with (session / "map.pcd").open("rb") as stream:
    while True:
        line = stream.readline()
        if not line:
            raise ValueError("Incomplete PCD")
        if line.startswith(b"DATA"):
            if line.strip() != b"DATA binary":
                raise ValueError("Unexpected PCD encoding")
            break
    points = np.fromfile(stream, dtype="<f4").reshape(-1,8)[:, :3]
summary["map"] = dict(points=len(points), all_finite=bool(np.isfinite(points).all()),
                      min_xyz_m=points.min(axis=0).tolist(), max_xyz_m=points.max(axis=0).tolist())
(capture / "review.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2), flush=True)
if summary["imu_clock_reversals"] or summary["clouds_with_duration_over_200ms"] or not summary["map"]["all_finite"]:
    raise RuntimeError("Clock/map integrity checks did not pass")

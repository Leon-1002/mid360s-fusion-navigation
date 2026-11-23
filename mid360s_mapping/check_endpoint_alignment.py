"""Independently align endpoint raw clouds to assess the reported return pose."""
import json
import math
import sqlite3
import struct
import sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

capture = Path(sys.argv[1])
if not (capture / "raw/metadata.yaml").is_file():
    raise RuntimeError("Finish recording before reading its database")
poses = np.asarray(json.loads((capture / "live_health.json").read_text())["poses"])
initial = poses[0]
final = poses[-1]

def clouds(db, time_s):
    rows = db.execute("SELECT data FROM messages WHERE topic_id=(SELECT id FROM topics WHERE name='/livox/lidar') AND timestamp>=? ORDER BY timestamp LIMIT 6", (int(time_s*1e9),))
    chunks = []
    for (data,) in rows:
        size = struct.unpack_from("<I", data, 12)[0]
        offset = 4 + ((16 + size - 4 + 7)//8)*8
        count = struct.unpack_from("<I", data, offset+16)[0]
        xyz = np.ndarray((count,3), dtype="<f4", buffer=data, offset=offset+24, strides=(20,4)).copy()
        tags = np.ndarray((count,), dtype="u1", buffer=data, offset=offset+37, strides=(20,))
        radius = np.linalg.norm(xyz, axis=1)
        valid = np.isfinite(xyz).all(axis=1) & (radius>.7) & (radius<20) & (((tags & 0x30)==0) | ((tags & 0x30)==0x10))
        chunks.append(xyz[valid])
    if not chunks:
        raise RuntimeError("No endpoint cloud found")
    points = np.concatenate(chunks)
    _, keep = np.unique(np.floor(points/.08).astype(np.int64), axis=0, return_index=True)
    return points[keep].astype(np.float64)

with sqlite3.connect(f"file:{(capture/'raw/raw_0.db3').resolve()}?mode=ro", uri=True) as db:
    target = clouds(db, initial[0]+3)
    moving = clouds(db, final[0]-5)
tree = cKDTree(target)
R0 = Rotation.from_quat(initial[4:8]).as_matrix()
R1 = Rotation.from_quat(final[4:8]).as_matrix()
lio_R = R0.T @ R1
lio_t = R0.T @ (final[1:4]-initial[1:4])

def align(R, t):
    R, t = R.copy(), t.copy()
    for iteration in range(60):
        transformed = moving @ R.T + t
        distance, index = tree.query(transformed)
        valid = distance < min(.7, np.quantile(distance,.8))
        if valid.sum() < 100:
            raise RuntimeError("Too few point correspondences")
        a, b = transformed[valid], target[index[valid]]
        ac, bc = a.mean(axis=0), b.mean(axis=0)
        u, _, vt = np.linalg.svd((a-ac).T @ (b-bc))
        correction = np.eye(3)
        correction[2,2] = np.linalg.det(vt.T @ u.T)
        delta_R = vt.T @ correction @ u.T
        delta_t = bc-delta_R@ac
        R, t = delta_R@R, delta_R@t+delta_t
        if np.linalg.norm(delta_t)<1e-5 and Rotation.from_matrix(delta_R).magnitude()<1e-5:
            break
    distances, _ = tree.query(moving @ R.T+t)
    near = distances < .2
    return dict(rotation_deg=float(np.degrees(Rotation.from_matrix(R).magnitude())),
                position_m=t.tolist(), position_norm_m=float(np.linalg.norm(t)),
                overlap_within_20cm=float(near.mean()), rmse_within_20cm_m=float(np.sqrt(np.mean(distances[near]**2))),
                orientation_difference_from_lio_deg=float(np.degrees(Rotation.from_matrix(R.T@lio_R).magnitude())),
                iterations=iteration+1)

result = dict(target_points=len(target), endpoint_points=len(moving),
              lio_return_angle_deg=float(np.degrees(Rotation.from_matrix(lio_R).magnitude())),
              from_identity=align(np.eye(3), np.zeros(3)), from_lio=align(lio_R, lio_t),
              note="Independent cloud registration diagnostic, not externally measured ground truth")
(capture / "endpoint_alignment.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))

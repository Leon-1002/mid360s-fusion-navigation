"""Compare identical movement data; report estimated closure, not survey accuracy."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent
runs = [root / "replay-20261118-201249-58RL", root / "replay-20261118-202047-7Rzj"]
fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
report = {}
for name, run in zip(["Original / 0.50 m voxel", "Repaired / 0.15 m voxel"], runs):
    a = np.loadtxt(run / "trajectory.txt")
    xyz = a[:, 4:7] - a[0, 4:7]
    axes[0].plot(xyz[:, 0], xyz[:, 1], label=name, linewidth=1.2)
    axes[0].scatter(*xyz[-1, :2], marker="x", s=65)
    axes[1].plot(a[:, 0] - a[0, 0], np.linalg.norm(xyz, axis=1), label=name)
    with (run / "map.pcd").open("rb") as f:
        header = []
        while True:
            line = f.readline()
            if not line:
                raise ValueError("PCD header incomplete")
            header.append(line.decode().strip())
            if line.startswith(b"DATA"):
                if line.strip() != b"DATA binary":
                    raise ValueError("Expected binary PCD")
                break
        fields = next(x.split()[1:] for x in header if x.startswith("FIELDS "))
        sizes = next(x.split()[1:] for x in header if x.startswith("SIZE "))
        types = next(x.split()[1:] for x in header if x.startswith("TYPE "))
        counts = next(x.split()[1:] for x in header if x.startswith("COUNT "))
        if any(s != "4" for s in sizes) or any(t != "F" for t in types) or any(c != "1" for c in counts):
            raise ValueError("Unsupported point representation")
        cloud = np.fromfile(f, dtype="<f4").reshape(-1, len(fields))[:, :3]
    if not np.isfinite(cloud).all():
        raise ValueError("Non-finite map coordinates")
    report[name] = dict(trajectory_source="mat_pre.txt (prediction before scan update)",
        frames=len(a), endpoint_displacement_m=float(np.linalg.norm(xyz[-1])),
        max_displacement_m=float(np.linalg.norm(xyz, axis=1).max()),
        max_step_m=float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).max()),
        points=len(cloud), bounds_min_m=cloud.min(axis=0).tolist(), bounds_max_m=cloud.max(axis=0).tolist())
axes[0].set(xlabel="X displacement (m)", ylabel="Y displacement (m)", title="Same recorded movement: top view")
axes[0].set_aspect("equal", adjustable="datalim")
axes[0].scatter(0, 0, marker="o", color="black", s=25)
axes[1].set(xlabel="Elapsed sensor time (s)", ylabel="Displacement from start (m)", title="Translation and rotation return test")
for ax in axes:
    ax.grid(alpha=.25)
    ax.legend(fontsize=8)
fig.savefig(root / "repair-comparison-20261118.png", dpi=160)
(root / "repair-comparison-20261118.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))

"""Apply narrow, checked changes; preserve a dated copy of each upstream file."""
from pathlib import Path
import shutil

root = Path.home() / "mid360s_lio/src/FAST_LIO_ROS2"
backup = Path("/mnt/e/chatgpt_project/mid360s_mapping/source-backup-20261118")
backup.mkdir(exist_ok=True)
changes = {
    "src/IMU_Processing.hpp": [
        ("  V3D acc_s_last;", "  V3D acc_s_last = V3D::Zero();"),
        ("  double last_lidar_end_time_;", "  double last_lidar_end_time_ = 0.0;"),
        ("  angvel_last       = Zero3d;", "  angvel_last       = Zero3d;\n  acc_s_last       = Zero3d;\n  last_lidar_end_time_ = 0.0;"),
        ("    last_imu_   = meas.imu.back();", "    last_imu_   = meas.imu.back();\n    // Prediction must start at the initialized state's scan boundary.\n    last_lidar_end_time_ = meas.lidar_end_time;"),
    ],
    "src/laserMapping.cpp": [
        ('(imu_topic, 10, imu_cbk);', '(imu_topic, 1000, imu_cbk);'),
    ],
}
prepared = []
for relative, replacements in changes.items():
    path = root / relative
    text = path.read_text()
    for old, new in replacements:
        if text.count(old) != 1:
            raise RuntimeError(f"Expected exactly one original match in {relative}: {old}")
        text = text.replace(old, new)
    saved = backup / path.name
    if saved.exists():
        raise RuntimeError(f"Backup exists, refusing to overwrite: {saved}")
    prepared.append((path, saved, text))
for path, saved, text in prepared:
    shutil.copy2(path, saved)
    path.write_text(text)
    print(f"Updated {path}; original saved at {saved}")

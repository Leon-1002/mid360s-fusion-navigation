"""Measure incoming sensor values and timestamps without running mapping."""
import json
import time
from pathlib import Path

import numpy as np
import rclpy
from livox_ros_driver2.msg import CustomMsg
from sensor_msgs.msg import Imu
from rclpy.qos import qos_profile_sensor_data


def main():
    rclpy.init()
    node = rclpy.create_node('inspect_static_sensors')
    imu_rows, scans = [], []

    def imu_callback(msg):
        a, g = msg.linear_acceleration, msg.angular_velocity
        imu_rows.append([msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                         a.x, a.y, a.z, g.x, g.y, g.z])

    def lidar_callback(msg):
        xyz = np.array([[p.x, p.y, p.z] for p in msg.points])
        offsets = np.array([p.offset_time for p in msg.points])
        valid = sum(p.line < 4 and (p.tag & 0x30) in (0, 0x10) for p in msg.points)
        scans.append(dict(time=msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                          timebase=int(msg.timebase), points=len(msg.points), valid=valid,
                          offset_min_ns=int(offsets.min()) if len(offsets) else None,
                          offset_max_ns=int(offsets.max()) if len(offsets) else None,
                          xyz_min=xyz.min(axis=0).tolist() if len(xyz) else [],
                          xyz_max=xyz.max(axis=0).tolist() if len(xyz) else []))

    node.create_subscription(Imu, '/livox/imu', imu_callback, qos_profile_sensor_data)
    node.create_subscription(CustomMsg, '/livox/lidar', lidar_callback, qos_profile_sensor_data)
    start, report = time.monotonic(), 0
    first_data = None
    while time.monotonic() - start < 90:
        rclpy.spin_once(node, timeout_sec=.1)
        if first_data is None and imu_rows and scans:
            first_data = time.monotonic()
        if first_data is not None and time.monotonic() - first_data >= 20:
            break
        if time.monotonic() - start > report:
            report += 1
            print(f'IMU={len(imu_rows)} scans={len(scans)} latest_IMU={imu_rows[-1] if imu_rows else None}', flush=True)
    data = np.array(imu_rows)
    summary = dict(imu_count=len(imu_rows), scan_count=len(scans))
    if len(data) > 1:
        summary.update(imu_mean=data[:, 1:].mean(axis=0).tolist(),
                       imu_std=data[:, 1:].std(axis=0).tolist(),
                       imu_dt_quantiles=np.quantile(np.diff(data[:, 0]), [0, .5, .99, 1]).tolist(),
                       imu_time_range=data[[0, -1], 0].tolist())
    if len(scans) > 1:
        summary['lidar_dt_quantiles'] = np.quantile(np.diff([s['time'] for s in scans]), [0, .5, .99, 1]).tolist()
        summary['first_scan'] = scans[0]
        summary['last_scan'] = scans[-1]
    Path('sensor_stats.json').write_text(json.dumps(dict(summary=summary, scans=scans, imu=imu_rows), indent=2))
    print(json.dumps(summary, indent=2), flush=True)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

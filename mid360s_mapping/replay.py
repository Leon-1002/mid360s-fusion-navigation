"""Display live FAST-LIO output while playing the two recorded sensor topics."""
from pathlib import Path
import subprocess
import sys
import time
import csv
import json
import math

import rclpy
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2
from std_srvs.srv import Trigger


def main():
    bag = sys.argv[1]
    rclpy.init()
    node = rclpy.create_node("offline_replay_monitor")
    odometry_count = cloud_count = 0
    position = None
    trajectory = []

    def odometry(msg):
        nonlocal odometry_count, position
        odometry_count += 1
        position = msg.pose.pose.position
        q = msg.pose.pose.orientation
        trajectory.append([msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                           position.x, position.y, position.z, q.x, q.y, q.z, q.w])

    def cloud(msg):
        nonlocal cloud_count
        if msg.width * msg.height:
            cloud_count += 1

    node.create_subscription(Odometry, "/Odometry", odometry, 20)
    node.create_subscription(PointCloud2, "/cloud_registered", cloud, 10)
    save = node.create_client(Trigger, "/map_save")
    start = time.monotonic()
    while not (save.service_is_ready() and node.count_subscribers("/livox/lidar")
               and node.count_subscribers("/livox/imu") and
               any(i.node_name.startswith("rviz") for topic in ("/cloud_registered", "/Laser_map", "/path")
                   for i in node.get_subscriptions_info_by_topic(topic))):
        if time.monotonic() - start > 45:
            raise RuntimeError("等待 FAST-LIO 或 RViz 超时")
        rclpy.spin_once(node, timeout_sec=.1)
    print(f"开始回放：{bag}", flush=True)
    cmd = ["ros2", "bag", "play", bag, "--disable-keyboard-controls",
           "--delay", "2", "--topics", "/livox/lidar", "/livox/imu"]
    player = subprocess.Popen(cmd)
    try:
        next_report = time.monotonic()
        finished = None
        while finished is None or time.monotonic() - finished < 2:
            rclpy.spin_once(node, timeout_sec=.05)
            if finished is None and player.poll() is not None:
                finished = time.monotonic()
            if time.monotonic() >= next_report:
                xyz = (f"{position.x:.3f}, {position.y:.3f}, {position.z:.3f} m"
                       if position else "等待第一帧")
                print(f"里程计 {odometry_count} 帧  配准点云 {cloud_count} 帧  XYZ {xyz}", flush=True)
                next_report = time.monotonic() + 1
        if player.returncode or not (odometry_count and cloud_count):
            raise RuntimeError("回放未产生有效建图输出")
    finally:
        if player.poll() is None:
            player.terminate()
            player.wait()
    future = save.call_async(Trigger.Request())
    rclpy.spin_until_future_complete(node, future, timeout_sec=60)
    if not future.done() or not future.result().success or not Path("map.pcd").is_file():
        raise RuntimeError("回放地图保存失败")
    with Path("trajectory.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time", "x", "y", "z", "qx", "qy", "qz", "qw"])
        writer.writerows(trajectory)
    distances = [math.dist(row[1:4], trajectory[0][1:4]) for row in trajectory]
    summary = dict(bag=bag, odometry_count=odometry_count, cloud_count=cloud_count,
                   endpoint_displacement_m=distances[-1], max_displacement_m=max(distances),
                   max_frame_step_m=max(math.dist(a[1:4], b[1:4])
                                        for a, b in zip(trajectory, trajectory[1:])))
    Path("replay_stats.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    rclpy.shutdown()


if __name__ == "__main__":
    main()

"""Feed a small synthetic room to an isolated ROS domain; expect 0.6 m translation."""
import argparse
import math
import random
import time

import rclpy
from builtin_interfaces.msg import Time
from livox_ros_driver2.msg import CustomMsg, CustomPoint
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu, PointCloud2
from std_srvs.srv import Trigger
from pathlib import Path


def stamp(ns):
    return Time(sec=ns // 10**9, nanosec=ns % 10**9)


def motion(t):
    # One second accelerating, two at constant speed, one decelerating.
    t = max(0., t - 3.)
    if t < 1.:
        return .1*t*t
    if t < 3.:
        return .1 + .2*(t-1)
    t = min(1., t-3.)
    return .5 + .2*t - .1*t*t


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-for-rviz", action="store_true")
    parser.add_argument("--inject-time-gap", action="store_true",
                        help="Inject a 2 s clock jump and require mapping to latch safely")
    args = parser.parse_args()
    rclpy.init()
    n = rclpy.create_node("synthetic_room")
    lidar = n.create_publisher(CustomMsg, "/livox/lidar", 10)
    imu = n.create_publisher(Imu, "/livox/imu", 100)
    odom, clouds = [], []
    n.create_subscription(Odometry, "/Odometry", lambda m: odom.append(m.pose.pose.position), 50)
    n.create_subscription(PointCloud2, "/cloud_registered", lambda m: clouds.append(m.width*m.height), 10)
    save = n.create_client(Trigger, "/map_save")
    deadline = time.monotonic() + 25
    while not (imu.get_subscription_count() and lidar.get_subscription_count()):
        rclpy.spin_once(n, timeout_sec=.05)
        if time.monotonic() > deadline:
            raise RuntimeError("mapping input subscriptions missing")
    if args.wait_for_rviz:
        deadline = time.monotonic() + 45
        while not any(info.node_name.startswith("rviz") for topic in
                      ("/cloud_registered", "/Laser_map", "/path")
                      for info in n.get_subscriptions_info_by_topic(topic)):
            rclpy.spin_once(n, timeout_sec=.1)
            if time.monotonic() > deadline:
                raise RuntimeError("RViz did not subscribe to mapping output")
        print("RViz 已连接。开始模拟扫描房间，随后雷达沿 X 轴移动 0.60 米。", flush=True)
    rng = random.Random(42)
    room = []
    for i in range(2100):
        p = [rng.uniform(-4, 4), rng.uniform(-3, 3), rng.uniform(-1.5, 2)]
        axis = i % 3
        p[axis] = ((4., -4.), (3., -3.), (2., -1.5))[axis][i % 2]
        room.append(p)
    # FAST-LIO keeps every third valid point. Interleave the six faces so
    # that downsampling still observes constraints on all three axes.
    rng.shuffle(room)
    # DDS discovery is not proof of data delivery. Keep publishing a stationary
    # pre-roll until the mapper actually produces output, before testing motion.
    ready_deadline = time.monotonic() + 45
    while not (odom and clouds):
        frame_epoch = time.time_ns()
        for j in range(20):
            m = Imu()
            m.header.stamp = stamp(frame_epoch + j*5000000)
            m.linear_acceleration.z = 1.
            imu.publish(m)
        scan = CustomMsg()
        scan.timebase = frame_epoch
        scan.header.stamp = stamp(frame_epoch)
        scan.header.frame_id = "livox_frame"
        scan.point_num = len(room)
        scan.points = [CustomPoint(x=x, y=y, z=z, offset_time=i*100000000//len(room),
                                   reflectivity=80, line=i%4, tag=16)
                       for i, (x, y, z) in enumerate(room)]
        lidar.publish(scan)
        until = time.monotonic() + .1
        while time.monotonic() < until:
            rclpy.spin_once(n, timeout_sec=.005)
        if time.monotonic() > ready_deadline:
            raise RuntimeError("mapper produced no output during 45 s stationary pre-roll")
    print("Mapper received stationary data and is ready; beginning motion test", flush=True)
    odom.clear()
    clouds.clear()
    epoch = time.time_ns()
    start = time.monotonic()
    before_gap = None
    for k in range(100):
        if args.inject_time_gap and k == 50:
            before_gap = len(odom)
        time_gap = 2000000000 if args.inject_time_gap and k >= 50 else 0
        for j in range(20):
            t = k*.1 + j*.005
            m = Imu()
            m.header.stamp = stamp(epoch + time_gap + k*100000000 + j*5000000)
            m.linear_acceleration.z = 1.
            m.linear_acceleration.x = (.2 if 3 <= t < 4 else -.2 if 6 <= t < 7 else 0.) / 9.81
            imu.publish(m)
        scan = CustomMsg()
        scan.timebase = epoch + time_gap + k*100000000
        scan.header.stamp = stamp(scan.timebase)
        scan.header.frame_id = "livox_frame"
        scan.point_num = len(room)
        scan.points = [CustomPoint(x=x-motion(k*.1+i*.1/len(room)), y=y, z=z,
                                   offset_time=i*100000000//len(room), reflectivity=80,
                                   line=i%4, tag=16) for i,(x,y,z) in enumerate(room)]
        lidar.publish(scan)
        while time.monotonic() < start+(k+1)*.1:
            rclpy.spin_once(n, timeout_sec=.005)
        if args.wait_for_rviz and (k+1) % 10 == 0:
            xyz = (f"({odom[-1].x:.3f}, {odom[-1].y:.3f}, {odom[-1].z:.3f}) m"
                   if odom else "初始化中")
            print(f"{(k+1)//10:2d}/10 秒  已发扫描 {k+1}  已发 IMU {20*(k+1)}  "
                  f"配准点云 {len(clouds)}  估计位置 {xyz}", flush=True)
    end = time.monotonic()+1
    while time.monotonic()<end:
        rclpy.spin_once(n, timeout_sec=.02)
    if len(odom)<20 or len(clouds)<10 or not max(clouds):
        raise RuntimeError(f"insufficient output: odometry={len(odom)} clouds={len(clouds)}")
    p = odom[-1]
    print(f"odometry={len(odom)}, clouds={len(clouds)}, final XYZ={p.x:.3f},{p.y:.3f},{p.z:.3f}", flush=True)
    if args.inject_time_gap:
        if before_gap is None or before_gap < 20 or len(odom) - before_gap > 2:
            raise RuntimeError("mapping did not stop on the injected timestamp jump")
        if not math.dist((p.x,p.y,p.z),(.28,0,0)) < .15:
            raise RuntimeError("last retained pose is inconsistent with pre-gap motion")
        print("Timestamp jump correctly latched mapping; last valid state retained", flush=True)
    elif not math.dist((p.x,p.y,p.z),(.6,0,0)) < .15:
        raise RuntimeError("trajectory disagrees with synthetic motion")
    fut = save.call_async(Trigger.Request())
    rclpy.spin_until_future_complete(n, fut, timeout_sec=10)
    if not fut.done() or not fut.result().success or not Path("map.pcd").is_file():
        raise RuntimeError("map saving failed")
    with open("map.pcd", "rb") as f:
        header = f.read(512).split(b"DATA binary")[0]
    if not any(line.startswith(b"POINTS ") and int(line.split()[1])>0 for line in header.splitlines()):
        raise RuntimeError("saved map empty")
    print("Saved nonempty synthetic map", flush=True)
    rclpy.shutdown()


if __name__ == "__main__":
    main()

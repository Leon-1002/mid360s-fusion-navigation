"""Observe a stationary mapping run and save its measured trajectory."""
import json
import time
from pathlib import Path
import rclpy
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2
from std_srvs.srv import Trigger

rclpy.init()
node = rclpy.create_node('static_mapping_monitor')
poses, clouds = [], []

def odometry(msg):
    p = msg.pose.pose.position
    poses.append([msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9, p.x, p.y, p.z])

node.create_subscription(Odometry, '/Odometry', odometry, 100)
node.create_subscription(PointCloud2, '/cloud_registered', lambda msg: clouds.append(msg.width * msg.height), 10)
start, next_report = time.monotonic(), 0
while time.monotonic() - start < 45:
    rclpy.spin_once(node, timeout_sec=.1)
    if time.monotonic() - start > next_report:
        next_report += 1
        print(f'里程计 {len(poses)} 帧，点云 {len(clouds)} 帧，最新 XYZ {poses[-1][1:] if poses else None}', flush=True)
Path('static_trajectory.json').write_text(json.dumps(poses))
if len(poses) < 20:
    raise RuntimeError('没有收到足够的建图输出')
distance = max((x*x+y*y+z*z)**.5 for _, x,y,z in poses)
print(f'最大原点距离 {distance:.4f} m', flush=True)
if distance > 1:
    raise RuntimeError('静止位置偏移超过 1 m，仍然异常')
save = node.create_client(Trigger, '/map_save')
if not save.wait_for_service(timeout_sec=5):
    raise RuntimeError('地图保存服务不可用')
future = save.call_async(Trigger.Request())
rclpy.spin_until_future_complete(node, future, timeout_sec=30)
if not future.done() or not future.result().success:
    raise RuntimeError('地图保存失败')
print('静止运行完成，地图已保存。', flush=True)
rclpy.shutdown()

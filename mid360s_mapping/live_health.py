"""Low-overhead live sensor rates and odometry monitor; no point decoding."""
import json
import argparse
import math
import shutil
import time
from pathlib import Path
import rclpy
from livox_ros_driver2.msg import CustomMsg
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry
from std_srvs.srv import Trigger

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--manual", action="store_true", help="Record until finish-monitor is created")
parser.add_argument("--recorder-pid", type=int, help="Fail clearly if the recorder exits")
args = parser.parse_args()
rclpy.init()
node = rclpy.create_node("mapping_live_health")
counts = dict(lidar=0, imu=0, odometry=0)
poses = []

def count_lidar(data):
    counts["lidar"] += 1

def count_imu(data):
    counts["imu"] += 1

def odometry(msg):
    counts["odometry"] += 1
    p, q = msg.pose.pose.position, msg.pose.pose.orientation
    poses.append([msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                  p.x, p.y, p.z, q.x, q.y, q.z, q.w])

node.create_subscription(CustomMsg, "/livox/lidar", count_lidar, 20, raw=True)
node.create_subscription(Imu, "/livox/imu", count_imu, 1000, raw=True)
node.create_subscription(Odometry, "/Odometry", odometry, 100)
start = last_report = time.monotonic()
previous = counts.copy()
ready = None
while args.manual or time.monotonic() - start < 210:
    rclpy.spin_once(node, timeout_sec=.02)
    now = time.monotonic()
    if ready is None and all(counts.values()):
        ready = now
        print("READY: 点云、IMU、位姿均已收到。等待助手确认后开始移动。", flush=True)
        if args.manual:
            print("本轮手动结束：完成动作后回复助手；录制不会在三分钟后自动结束。", flush=True)
    if now - last_report >= 1:
        if args.recorder_pid:
            proc = Path(f"/proc/{args.recorder_pid}/stat")
            try:
                recorder_state = proc.read_text().rsplit(") ", 1)[1][0]
            except FileNotFoundError:
                raise RuntimeError("录制器已退出，请检查 record.log；不能继续视为正在录制")
            if recorder_state == "Z":
                raise RuntimeError("录制器已异常退出，请检查 record.log")
        dt = now - last_report
        rate = {key: round((counts[key] - previous[key]) / dt, 1) for key in counts}
        print(f"Hz {rate}  XYZ(m) {poses[-1][1:4] if poses else '等待建图'}", flush=True)
        previous, last_report = counts.copy(), now
        Path("live_health.json").write_text(json.dumps(dict(counts=counts, rates=rate, poses=poses)))
        if shutil.disk_usage(Path.cwd()).free < 5 * 1024**3:
            print("磁盘剩余不足 5 GiB，结束录制并尝试保存当前地图。", flush=True)
            break
    if ready is None and now - start >= 210:
        raise RuntimeError("210 秒内未等到完整建图输出，结束本次录制")
    if Path("finish-monitor").exists() or (not args.manual and ready is not None and now - ready >= 180):
        break
result = dict(counts=counts, poses=poses)
if poses:
    result["endpoint_displacement_m"] = math.dist(poses[-1][1:4], poses[0][1:4])
    result["max_displacement_m"] = max(math.dist(p[1:4], poses[0][1:4]) for p in poses)
Path("live_health.json").write_text(json.dumps(result))
if len(poses) < 20:
    raise RuntimeError("现场验证没有收到足够的位姿，不能判定通过")
save = node.create_client(Trigger, "/map_save")
if not save.wait_for_service(timeout_sec=5):
    raise RuntimeError("地图保存服务不可用")
future = save.call_async(Trigger.Request())
rclpy.spin_until_future_complete(node, future, timeout_sec=30)
if not future.done() or not future.result().success:
    raise RuntimeError("地图保存失败")
print("现场数据已保存；回程误差需要结合实际是否回到起点判断。", flush=True)
rclpy.shutdown()

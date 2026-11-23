"""Read a static rosbag and report timestamp gaps and point ranges."""
import sqlite3
import sys
from pathlib import Path
import numpy as np
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import Imu
from livox_ros_driver2.msg import CustomMsg

bag = Path(sys.argv[1])
with sqlite3.connect(f'file:{bag / "raw_0.db3"}?mode=ro', uri=True) as db:
    for topic, msg_type in [('/livox/imu', Imu), ('/livox/lidar', CustomMsg)]:
        rows = db.execute('SELECT data FROM messages WHERE topic_id=(SELECT id FROM topics WHERE name=?) ORDER BY timestamp', (topic,))
        stamps, values, durations = [], [], []
        for (data,) in rows:
            msg = deserialize_message(data, msg_type)
            stamps.append(msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9)
            if topic.endswith('imu'):
                a, g = msg.linear_acceleration, msg.angular_velocity
                values.append([a.x, a.y, a.z, g.x, g.y, g.z])
            else:
                durations.append(max((p.offset_time for p in msg.points), default=0) * 1e-9)
        delta = np.diff(stamps)
        print(topic, 'count', len(stamps), 'interval min/median/p99/max', np.quantile(delta, [0, .5, .99, 1]), 'backwards', int((delta < 0).sum()))
        if values:
            print('IMU mean', np.mean(values, axis=0), 'IMU std', np.std(values, axis=0))
        if durations:
            print('Scan duration min/median/max', np.quantile(durations, [0, .5, 1]))

trajectory = Path.home() / 'mid360s_lio/src/FAST_LIO_ROS2/Log/mat_pre.txt'
states = np.loadtxt(trajectory)
position = states[:, 4:7]
bad = np.flatnonzero(np.linalg.norm(position, axis=1) > 1)
if len(bad):
    first = bad[0]
    print('First position exceeding 1m; columns time, XYZ:')
    print(states[max(0, first-4):first+5][:, [0, 4, 5, 6]])
print('Largest scan time gaps', np.sort(np.diff(states[:, 0]))[-8:])

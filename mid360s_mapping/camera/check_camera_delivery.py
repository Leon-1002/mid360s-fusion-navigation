"""Bounded on-machine ROS raw/JPEG delivery acceptance; does not open the camera."""
import json
import time
from pathlib import Path

import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, CompressedImage

rclpy.init()
node = rclpy.create_node('camera_delivery_acceptance')
stats = {}
subscriptions = []
warmup_until = None


def receive(topic, message):
    global warmup_until
    now = time.monotonic()
    if warmup_until is None:
        warmup_until = now + 3
    if now < warmup_until:
        return
    stamp = message.header.stamp.sec * 10**9 + message.header.stamp.nanosec
    item = stats.setdefault(topic, dict(count=0, first=now, last=now,
                                       first_stamp_ns=stamp,
                                       nonincreasing_stamps=0, invalid_images=0,
                                       max_interval_s=0.0))
    if item['count']:
        item['nonincreasing_stamps'] += int(stamp <= item['last_stamp_ns'])
        item['max_interval_s'] = max(item['max_interval_s'], now - item['last'])
    if isinstance(message, Image):
        valid = (message.width == 3072 and message.height == 2048
                 and message.encoding == 'bayer_rggb8'
                 and message.step >= message.width
                 and len(message.data) == message.step * message.height)
        item['invalid_images'] += int(not valid)
        item.update(width=message.width, height=message.height,
                    encoding=message.encoding, bytes=len(message.data))
    else:
        item['invalid_images'] += int(not message.data)
    item.update(count=item['count'] + 1, last=now, last_stamp_ns=stamp)


for topic, cls in [('/camera/image_raw', Image),
                   ('/camera/image_raw/compressed', CompressedImage)]:
    subscriptions.append(node.create_subscription(
        cls, topic, lambda msg, t=topic: receive(t, msg), qos_profile_sensor_data))

deadline = time.monotonic() + 50
measurement_end = None
while rclpy.ok() and time.monotonic() < deadline:
    rclpy.spin_once(node, timeout_sec=0.2)
    if measurement_end is None and len(stats) == 2:
        measurement_end = time.monotonic() + 30
    if measurement_end is not None and time.monotonic() >= measurement_end:
        break

for item in stats.values():
    elapsed = item['last'] - item['first']
    item['received_hz'] = (item['count'] - 1) / elapsed if elapsed else 0
    item['duration_s'] = elapsed
passed = len(stats) == 2 and all(
    item['duration_s'] >= 29 and item['count'] >= 140
    and 4.8 <= item['received_hz'] <= 5.2
    and item['nonincreasing_stamps'] == 0 and item['invalid_images'] == 0
    for item in stats.values())
report = dict(result='RATE_PASS' if passed else 'FAIL', topics=stats,
              warmup_seconds=3, rate_acceptance_hz=[4.8, 5.2],
              lossless_delivery_verified=False,
              scope='Orin local raw+JPEG ROS delivery; host receive timestamps; no synchronization claim')
Path('camera-delivery.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2), flush=True)
node.destroy_node()
rclpy.shutdown()
raise SystemExit(0 if passed else 1)

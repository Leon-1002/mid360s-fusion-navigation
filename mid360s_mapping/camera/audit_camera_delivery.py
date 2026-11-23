"""Compare a ROS measurement against SDK frames in the same header-stamp range."""
import argparse
import csv
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('delivery_json', type=Path)
parser.add_argument('frames_csv', type=Path)
parser.add_argument('output_json', type=Path)
args = parser.parse_args()
delivery = json.loads(args.delivery_json.read_text(encoding='utf-8'))
with args.frames_csv.open(encoding='utf-8', newline='') as stream:
    frames = list(csv.DictReader(stream))
if not frames:
    raise SystemExit('No SDK frame evidence')
result = {}
for topic, item in delivery['topics'].items():
    first, last = item['first_stamp_ns'], item['last_stamp_ns']
    expected = sum(first <= int(frame['host_receive_ns']) <= last for frame in frames)
    result[topic] = dict(sdk_frames_in_stamp_range=expected,
                        received=item['count'], missing=expected - item['count'],
                        nonincreasing_stamps=item['nonincreasing_stamps'],
                        invalid_images=item['invalid_images'])
passed = len(result) == 2 and all(
    item['sdk_frames_in_stamp_range'] > 0 and item['missing'] == 0
    and item['nonincreasing_stamps'] == 0 and item['invalid_images'] == 0
    for item in result.values())
report = dict(result='COUNT_PASS' if passed else 'COUNT_FAIL', topics=result,
              delivery_json=str(args.delivery_json), frames_csv=str(args.frames_csv))
args.output_json.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
raise SystemExit(0 if passed else 1)

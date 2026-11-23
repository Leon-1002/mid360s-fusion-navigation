"""Check acquisition order (message id), never sort away clock reversals."""
import sqlite3
import struct
import sys
from pathlib import Path

bag = Path(sys.argv[1])
if not (bag.parent / "metadata.yaml").is_file():
    raise RuntimeError("Stop recording and finalize/reindex the bag before auditing; live SQLite reads can block the recorder")
with sqlite3.connect(f"file:{bag.resolve()}?mode=ro", uri=True) as db:
    topics = list(db.execute("SELECT id, name FROM topics WHERE name IN ('/livox/imu','/livox/lidar')"))
    for topic_id, name in topics:
        previous = None
        reversals = []
        min_header = min_record = float("inf")
        count = 0
        for row_id, received, header in db.execute("SELECT id,timestamp,substr(data,1,12) FROM messages WHERE topic_id=? ORDER BY id", (topic_id,)):
            if header[:2] != b"\x00\x01":
                raise ValueError(f"Unsupported CDR encoding: {header[:4]!r}")
            sec, nano = struct.unpack_from("<iI", header, 4)
            stamp = sec * 10**9 + nano
            if previous is not None:
                dh, dr = stamp - previous[0], received - previous[1]
                min_header, min_record = min(min_header, dh), min(min_record, dr)
                if dh < 0 or dr < 0:
                    reversals.append(dict(id=row_id, header_delta_s=dh/1e9, recorder_delta_s=dr/1e9))
            previous = stamp, received
            count += 1
        print(name, "messages", count, "minimum header/record dt (s)", min_header/1e9, min_record/1e9, "reversals", len(reversals))
        print(reversals[:8])

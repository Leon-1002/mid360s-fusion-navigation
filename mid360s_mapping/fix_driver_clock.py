"""Keep no-sync LiDAR/IMU timestamps and publication cadence monotonic."""
from pathlib import Path
import shutil

root = Path.home() / "mid360s_lio/src/livox_ros_driver2/src/comm"
backup = Path(__file__).resolve().parent / "driver-clock-backup-20261119"
backup.mkdir(exist_ok=True)
clock = '''// Anchor once to epoch time; subsequent wall-clock adjustments must not
// change the relative timing of unsynchronized LiDAR and IMU packets.
template <class WallClock = std::chrono::system_clock,
          class SteadyClock = std::chrono::steady_clock>
class MonotonicEpochClock {
 public:
  MonotonicEpochClock()
      : epoch_ns_(std::chrono::duration_cast<std::chrono::nanoseconds>(
            WallClock::now().time_since_epoch()).count()),
        start_(SteadyClock::now()) {}

  uint64_t Now() const {
    return epoch_ns_ + std::chrono::duration_cast<std::chrono::nanoseconds>(
                           SteadyClock::now() - start_).count();
  }

 private:
  const uint64_t epoch_ns_;
  const typename SteadyClock::time_point start_;
};

'''
changes = {
    "pub_handler.h": [
        ("#include <atomic>", "#include <atomic>\n#include <chrono>\n#include <cstdint>"),
        ("class LidarPubHandler {", clock + "class LidarPubHandler {"),
        ("using TimePoint = std::chrono::high_resolution_clock::time_point;", "using TimePoint = std::chrono::steady_clock::time_point;"),
    ],
    "pub_handler.cpp": [
        ("auto now_time = std::chrono::high_resolution_clock::now();", "auto now_time = std::chrono::steady_clock::now();"),
        ("return std::chrono::high_resolution_clock::now().time_since_epoch().count();", "static const MonotonicEpochClock<> clock;\n  return clock.Now();"),
    ],
}
prepared = []
for name, replacements in changes.items():
    path = root / name
    text = path.read_text()
    for old, new in replacements:
        if text.count(old) != 1:
            raise RuntimeError(f"Expected one original match in {name}: {old}")
        text = text.replace(old, new)
    if (backup / name).exists():
        raise RuntimeError("Refusing to overwrite original backup")
    prepared.append((path, text))
for path, text in prepared:
    shutil.copy2(path, backup / path.name)
    path.write_text(text)
    print("Updated", path)

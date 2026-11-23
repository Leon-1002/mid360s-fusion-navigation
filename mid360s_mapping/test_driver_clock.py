"""Test the actual driver clock with fake wall/steady clocks, without setting system time."""
from pathlib import Path
import subprocess
import tempfile

root = Path.home() / "mid360s_lio/src/livox_ros_driver2/src/comm"
header = (root / "pub_handler.h").read_text()
clock = header[header.index("template <class WallClock"):header.index("class LidarPubHandler {")]
harness = '''#include <chrono>
#include <cstdint>
#include <cassert>
#include <iostream>
''' + clock + '''
struct Wall {
  using time_point = std::chrono::time_point<Wall, std::chrono::nanoseconds>;
  static int64_t ns;
  static time_point now() { return time_point(std::chrono::nanoseconds(ns)); }
};
struct Steady {
  using time_point = std::chrono::time_point<Steady, std::chrono::nanoseconds>;
  static int64_t ns;
  static time_point now() { return time_point(std::chrono::nanoseconds(ns)); }
};
int64_t Wall::ns = 1795064800000000000LL;
int64_t Steady::ns = 1000000000LL;
int main() {
  MonotonicEpochClock<Wall, Steady> clock;
  const auto initial = clock.Now();
  assert(initial == static_cast<uint64_t>(Wall::ns));
  Wall::ns -= 416592059;
  Steady::ns += 5000000;
  assert(clock.Now() == initial + 5000000);
  Wall::ns -= 409351544;
  Steady::ns += 5000000;
  assert(clock.Now() == initial + 10000000);
  Wall::ns += 3600000000000LL;
  Steady::ns += 100000000;
  assert(clock.Now() == initial + 110000000);
  std::cout << "PASS: both observed backward jumps and 1-hour forward wall-clock jump leave packet time continuous\\n";
}
'''
cpp = (root / "pub_handler.cpp").read_text()
assert "auto now_time = std::chrono::steady_clock::now();" in cpp
assert "using TimePoint = std::chrono::steady_clock::time_point;" in header
assert "timestamp_type == kTimestampTypeGps) {\n    return time.stamp;" in cpp
with tempfile.TemporaryDirectory(prefix="livox-clock-test-") as temp:
    source, binary = Path(temp) / "clock.cpp", Path(temp) / "clock"
    source.write_text(harness)
    subprocess.run(["g++", "-std=c++14", "-Wall", "-Wextra", str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

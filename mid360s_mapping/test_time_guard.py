"""Exercise the actual C++ guard against observed startup and failure gaps."""
from pathlib import Path
import subprocess
import tempfile

source = (Path.home() / "mid360s_lio/src/FAST_LIO_ROS2/src/laserMapping.cpp").read_text()
function = source[source.index("bool sensor_time_fault = false;"):source.index("void standard_pcl_cbk(")]
harness = r'''
#include <cmath>
#include <cassert>
#include <iostream>
#define RCLCPP_ERROR(...) ((void)0)
struct { void *Root_Node = nullptr; } ikdtree;
''' + function + r'''
int main() {
    // Discovery startup has not established a map yet.
    assert(sensor_time_valid(101.4, 100., false, "LiDAR"));
    ikdtree.Root_Node = &ikdtree;
    // Observed startup cloud gap can be bridged by continuous IMU.
    assert(sensor_time_valid(101.4, 100., false, "LiDAR"));
    // The recorded 45-minute discontinuity must never be integrated.
    assert(!sensor_time_valid(2840.41, 100., false, "LiDAR"));
    assert(!sensor_time_valid(100.1, 100., false, "LiDAR"));
    sensor_time_fault = false;
    // A two-second injected IMU jump still latches immediately.
    assert(!sensor_time_valid(102.005, 100., false, "IMU"));
    sensor_time_fault = false;
    assert(!sensor_time_valid(99.9, 100., false, "IMU"));
    sensor_time_fault = false;
    assert(sensor_time_valid(100.005, 100., false, "IMU"));
    assert(sensor_time_valid(100.1, 100., false, "LiDAR"));
    std::cout << "PASS: startup gap, normal streams, long gap, clock reversal, and fault latch\n";
}
'''
with tempfile.TemporaryDirectory(prefix="mid360s-guard-test-") as temp:
    cpp, binary = Path(temp) / "guard.cpp", Path(temp) / "guard"
    cpp.write_text(harness)
    subprocess.run(["g++", "-std=c++14", "-Wall", "-Wextra", str(cpp), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

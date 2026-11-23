Jetson AGX Orin migration preparation — 2026-11-23

Confirmed live: NVIDIA Jetson AGX Orin Developer Kit, Ubuntu 22.04.5 LTS,
aarch64, door@192.168.2.127. SSH public-key authentication is now working.
JetPack 6.2.2 / L4T 36.5.0; 29 GiB RAM; approximately 73 GiB disk available at inspection.
Existing ROS Humble Desktop, colcon, Eigen, PCL and OpenCV were reused; no apt installation.

preflight.sh is a read-only inventory for the target.
build-lidar.sh builds a new isolated workspace located alongside it at workspace/.
Copy the validated source snapshot wsl/mid360s_lio into that directory first.
The target should be a new deployment directory, not an existing mapping workspace.
The camera CMake and sdk-env.sh now select validated native SDK paths for x86_64 and aarch64.
Both architectures built and passed SDK loader / ROS initialization checks.
Vendor ARM64 SDK V2.3.2.194984 is extracted inside the deployment camera/vendor directory.
Windows native camera capture and ST-LINK batch orchestration require Linux adaptation.

Actual isolated deployment: /home/door/mid360s_orin_20261123
Livox SDK2, livox_ros_driver2 and fast_lio all built natively on Orin; package executable
discovery passed. Upstream compiler warnings were retained. No sensor process was started.
Camera capture is now verified: two 40-second runs, 200 frames each, no SDK gaps/timeouts.
ROS raw delivery is approximately 4.926 Hz with 149/151 frames in a matched interval;
JPEG is approximately 4.993 Hz with 151/151 frames. Lossless raw delivery FAILED.
Hardware sync and mapping on Orin remain pending. See README.md for full reproduction steps.
Private SSH keys are stored outside the project and are never copied into the archive.

Keep the SSH/LAN connection on 192.168.2.127. Determine the actual lidar-facing
interface before assigning the separate lidar subnet 192.168.1.0/24; no network
configuration is applied by these scripts. Do not move USB/Ethernet until the
target software and interface plan are ready.

Current hardware baseline: joint 300 pulses / 300 camera frames at approximately
5 FPS; radar time checks passed after convergence. Synthetic time, no real UTC.
Point cloud CRC unavailable. Lossless ROS raw-image delivery and unified image header
timestamps remain outstanding. These limits also apply to the migration.

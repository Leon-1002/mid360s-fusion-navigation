#!/usr/bin/env bash
# Run only in the new Orin deployment copy, after dependencies are installed.
set -eo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/workspace" && pwd)
if [[ $(uname -m) != aarch64 ]]; then
    echo 'This deployment build requires native aarch64 Linux.' >&2; exit 2
fi
test -r /opt/ros/humble/setup.bash || { echo 'ROS 2 Humble is not installed.' >&2; exit 2; }
source /opt/ros/humble/setup.bash
cd "$root"
test -f sdk/CMakeLists.txt
test -f src/FAST_LIO_ROS2/include/ikd-Tree/ikd_Tree.cpp
driver=src/livox_ros_driver2
if [[ ! -e "$driver/package.xml" ]]; then cp "$driver/package_ROS2.xml" "$driver/package.xml"; fi
mkdir -p "$driver/launch"
for entry in "$driver"/launch_ROS2/*.py; do
    dest="$driver/launch/$(basename "$entry")"
    if [[ ! -e "$dest" ]]; then cp "$entry" "$dest"; fi
done
export CMAKE_BUILD_PARALLEL_LEVEL=2
export MAKEFLAGS=-j2
cmake -S sdk -B sdk-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$root/sdk-install"
cmake --build sdk-build -j2
sdk_so="$root/sdk-build/sdk_core/liblivox_lidar_sdk_shared.so"
test -f "$sdk_so"
colcon build --base-paths src --executor sequential --packages-select livox_ros_driver2 \
    --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble -DBUILD_TESTING=OFF \
    "-DLIVOX_LIDAR_SDK_LIBRARY=$sdk_so" "-DLIVOX_LIDAR_SDK_INCLUDE_DIR=$root/sdk/include"
source install/setup.bash
colcon build --base-paths src --executor sequential --packages-select fast_lio \
    --cmake-args -DBUILD_TESTING=OFF
source install/setup.bash
ros2 pkg executables livox_ros_driver2
ros2 pkg executables fast_lio
printf 'Build finished. No sensor process was started.\n'

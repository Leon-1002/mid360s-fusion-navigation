#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
cd "$HOME/mid360s_lio"
driver=src/livox_ros_driver2
cp "$driver/package_ROS2.xml" "$driver/package.xml"
mkdir -p "$driver/launch"
cp "$driver"/launch_ROS2/*.py "$driver/launch/"
sdk_so=$(find "$PWD/sdk-build" -name liblivox_lidar_sdk_shared.so -print -quit)
test -f "$sdk_so"
export CMAKE_BUILD_PARALLEL_LEVEL=2
export MAKEFLAGS=-j2
colcon build --base-paths src --packages-select livox_ros_driver2 --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble -DBUILD_TESTING=OFF "-DLIVOX_LIDAR_SDK_LIBRARY=$sdk_so" "-DLIVOX_LIDAR_SDK_INCLUDE_DIR=$PWD/sdk/include"
source install/setup.bash
colcon build --base-paths src --packages-select fast_lio --cmake-args -DBUILD_TESTING=OFF

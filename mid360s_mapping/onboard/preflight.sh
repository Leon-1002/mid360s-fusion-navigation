#!/usr/bin/env bash
# Read-only inventory. Does not configure networking, install packages or start sensors.
set -eu
printf '=== IDENTITY ===\n'
whoami
hostname
uname -a
cat /etc/os-release
if [ -r /proc/device-tree/model ]; then tr -d '\0' </proc/device-tree/model; printf '\n'; fi
if [ -r /etc/nv_tegra_release ]; then cat /etc/nv_tegra_release; fi
printf '=== RESOURCES ===\n'
df -h "$HOME" /tmp
free -h
printf '=== NETWORK ===\n'
ip -brief address
ip -4 route
printf '=== USB ===\n'
if command -v lsusb >/dev/null; then lsusb; lsusb -t; fi
printf '=== SERIAL ===\n'
if [ -d /dev/serial/by-id ]; then ls -l /dev/serial/by-id; fi
printf '=== PACKAGES ===\n'
for pkg in nvidia-l4t-core nvidia-jetpack ros-humble-ros-base ros-humble-desktop \
           python3-colcon-common-extensions libeigen3-dev libpcl-dev libopencv-dev; do
    dpkg-query -W -f='${binary:Package} ${Version} ${db:Status-Status}\n' "$pkg" 2>/dev/null || true
done
printf '=== EXISTING WORKSPACES ===\n'
for p in "$HOME/mid360s_lio" "$HOME/mid360s_orin_20261123" /opt/ros/humble /opt/MVS /opt/IMV /opt/MVviewer; do
    if [ -e "$p" ]; then ls -ld "$p"; fi
done
printf '=== EXISTING ACQUISITION PROCESSES ===\n'
pgrep -af '[f]astlio_mapping|[l]ivox_ros_driver2_node|[r]os2 bag record|[z]m_camera' || true

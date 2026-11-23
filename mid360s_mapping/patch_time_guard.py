"""Latch mapping on sensor clock discontinuity; keep the last map saveable."""
from pathlib import Path

path = Path.home() / "mid360s_lio/src/FAST_LIO_ROS2/src/laserMapping.cpp"
text = path.read_text()
helper = '''// A clock reset or a long sensor outage invalidates inertial propagation.
// Keep the existing map and save service alive, but require a fresh session.
bool sensor_time_fault = false;
bool sensor_time_valid(double current, double previous, bool first, const char *sensor)
{
    if (sensor_time_fault) return false;
    const double gap = current - previous;
    const double max_gap = sensor[0] == 'I' ? 0.5 : 2.0;
    if (!std::isfinite(current) || (!first && ikdtree.Root_Node != nullptr && (gap < 0.0 || gap > max_gap)))
    {
        sensor_time_fault = true;
        RCLCPP_ERROR(rclcpp::get_logger("laser_mapping"),
            "MAPPING PAUSED: %s timestamp discontinuity %.6f s. "
            "Last valid map is retained and can be saved. Restart mapping in a new session.",
            sensor, gap);
        return false;
    }
    return true;
}

'''
replacements = [
    ("void standard_pcl_cbk(", helper + "void standard_pcl_cbk("),
    ("    mtx_buffer.lock();\n    scan_count ++;\n    double cur_time = get_time_sec(msg->header.stamp);",
     "    double cur_time = get_time_sec(msg->header.stamp);\n    if (!sensor_time_valid(cur_time, last_timestamp_lidar, is_first_lidar, \"LiDAR\")) return;\n    mtx_buffer.lock();\n    scan_count ++;"),
    ("    mtx_buffer.lock();\n    double cur_time = get_time_sec(msg->header.stamp);",
     "    double cur_time = get_time_sec(msg->header.stamp);\n    if (!sensor_time_valid(cur_time, last_timestamp_lidar, is_first_lidar, \"LiDAR\")) return;\n    mtx_buffer.lock();"),
    ("    double timestamp = get_time_sec(msg->header.stamp);",
     "    double timestamp = get_time_sec(msg->header.stamp);\n    if (!sensor_time_valid(timestamp, last_timestamp_imu, last_timestamp_imu < 0.0, \"IMU\")) return;"),
    ("    void timer_callback()\n    {", "    void timer_callback()\n    {\n        if (sensor_time_fault) return;"),
]
for old, new in replacements:
    if text.count(old) != 1:
        raise RuntimeError(f"Expected unique original match: {old}")
    text = text.replace(old, new)
path.write_text(text)
print("Added timestamp discontinuity latch; original source is in source-backup-20261118")

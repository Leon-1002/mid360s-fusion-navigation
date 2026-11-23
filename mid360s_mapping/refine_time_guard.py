from pathlib import Path
path = Path.home() / "mid360s_lio/src/FAST_LIO_ROS2/src/laserMapping.cpp"
text = path.read_text()
old = "    const double gap = current - previous;\n    if (!std::isfinite(current) || (!first && ikdtree.Root_Node != nullptr && (gap < 0.0 || gap > 0.5)))"
new = """    const double gap = current - previous;
    // IMU must remain continuous; a short LiDAR outage can be bridged by IMU.
    // Two seconds is within the five-second IMU subscription queue capacity.
    const double max_gap = sensor[0] == 'I' ? 0.5 : 2.0;
    if (!std::isfinite(current) || (!first && ikdtree.Root_Node != nullptr && (gap < 0.0 || gap > max_gap)))"""
if text.count(old) != 1:
    raise RuntimeError("Expected unique old guard")
path.write_text(text.replace(old, new))

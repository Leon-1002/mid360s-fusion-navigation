from pathlib import Path
path = Path.home() / "mid360s_lio/src/FAST_LIO_ROS2/src/laserMapping.cpp"
text = path.read_text()
old = "if (!std::isfinite(current) || (!first && (gap < 0.0 || gap > 0.5)))"
new = "if (!std::isfinite(current) || (!first && ikdtree.Root_Node != nullptr && (gap < 0.0 || gap > 0.5)))"
if text.count(old) != 1:
    raise RuntimeError("Expected unique old timestamp guard")
path.write_text(text.replace(old, new))

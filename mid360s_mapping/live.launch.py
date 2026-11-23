from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    lio = Path(get_package_share_directory("fast_lio"))
    config = str(Path(__file__).with_name("MID360s_config.json"))
    return LaunchDescription([
        DeclareLaunchArgument("driver", default_value="true"),
        DeclareLaunchArgument("rviz", default_value="true"),
        DeclareLaunchArgument("voxel_size", default_value="0.15"),
        Node(package="livox_ros_driver2", executable="livox_ros_driver2_node",
             name="livox_driver", output="screen",
             condition=IfCondition(LaunchConfiguration("driver")),
             parameters=[dict(user_config_path=config, xfer_format=1, multi_topic=0,
                              data_src=0, publish_freq=10.0, output_data_type=0,
                              frame_id="livox_frame")]),
        Node(package="fast_lio", executable="fastlio_mapping", output="screen",
             parameters=[str(lio / "config/mid360.yaml"),
                         {"mapping.extrinsic_est_en": False,
                          "filter_size_surf": ParameterValue(LaunchConfiguration("voxel_size"), value_type=float),
                          "filter_size_map": ParameterValue(LaunchConfiguration("voxel_size"), value_type=float),
                          "pcd_save.pcd_save_en": True,
                          "map_file_path": str(Path.cwd() / "map.pcd")}]),
        Node(package="rviz2", executable="rviz2",
             arguments=["-d", str(lio / "rviz/fastlio.rviz")],
             condition=IfCondition(LaunchConfiguration("rviz"))),
    ])

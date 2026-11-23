"""Load the static map with the Nav2 map_server plugin."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    default_map_yaml = os.path.join(
        get_package_share_directory("testbed_bringup"),
        "maps",
        "testbed_world.yaml",
    )

    use_sim_time = LaunchConfiguration("use_sim_time")
    map_yaml = LaunchConfiguration("map")

    params = {
        "use_sim_time": use_sim_time,
        "yaml_filename": map_yaml,
        "topic_name": "map",
        "frame_id": "map",
        "save_map_timeout": 5.0,
    }

    map_server = Node(
        package="nav2_map_server",
        executable="map_server",
        name="map_server",
        output="screen",
        parameters=[params],
    )

    map_lifecycle = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="map_lifecycle_manager",
        output="screen",
        parameters=[
            {
                "use_sim_time": use_sim_time,
                "autostart": True,
                "bond_timeout": 0.0,
                "node_names": ["map_server"],
            }
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_sim_time", default_value="true",
                description="Use the Gazebo clock instead of wall time",
            ),
            DeclareLaunchArgument(
                "map", default_value=default_map_yaml,
                description="Absolute path to the map YAML file",
            ),
            map_server,
            map_lifecycle,
        ]
    )

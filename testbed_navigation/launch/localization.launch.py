"""Start the Nav2 AMCL localization node for the testbed robot."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    amcl_config = os.path.join(
        get_package_share_directory("testbed_navigation"),
        "config",
        "amcl_params.yaml",
    )

    use_sim_time = LaunchConfiguration("use_sim_time")

    amcl_node = Node(
        package="nav2_amcl",
        executable="amcl",
        name="amcl",
        output="screen",
        parameters=[amcl_config, {"use_sim_time": use_sim_time}],
        remappings=[("scan", "scan")],
    )

    localization_lifecycle = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="localization_lifecycle_manager",
        output="screen",
        parameters=[
            {
                "use_sim_time": use_sim_time,
                "autostart": True,
                "bond_timeout": 0.0,
                "node_names": ["amcl"],
            }
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_sim_time", default_value="true",
                description="Use the Gazebo clock instead of wall time",
            ),
            amcl_node,
            TimerAction(period=2.0, actions=[localization_lifecycle]),
        ]
    )

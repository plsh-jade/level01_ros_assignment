"""Bring up the Nav2 planning, control, recovery and behaviour-tree servers."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    nav2_config = os.path.join(
        get_package_share_directory("testbed_navigation"),
        "config",
        "nav2_params.yaml",
    )

    use_sim_time = LaunchConfiguration("use_sim_time")
    shared_parameters = [nav2_config, {"use_sim_time": use_sim_time}]

    def nav2_node(package, executable, name):
        return Node(
            package=package,
            executable=executable,
            name=name,
            output="screen",
            parameters=shared_parameters,
        )

    planner = nav2_node("nav2_planner", "planner_server", "planner_server")
    controller = nav2_node("nav2_controller", "controller_server", "controller_server")
    behavior = nav2_node("nav2_behaviors", "behavior_server", "behavior_server")
    bt_navigator = nav2_node("nav2_bt_navigator", "bt_navigator", "bt_navigator")

    navigation_lifecycle = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="navigation_lifecycle_manager",
        output="screen",
        parameters=[
            {
                "use_sim_time": use_sim_time,
                "autostart": True,
                "bond_timeout": 0.0,
                "node_names": [
                    "planner_server",
                    "controller_server",
                    "behavior_server",
                    "bt_navigator",
                ],
            }
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_sim_time", default_value="true",
                description="Use the Gazebo clock instead of wall time",
            ),
            planner,
            controller,
            behavior,
            bt_navigator,
            TimerAction(period=3.0, actions=[navigation_lifecycle]),
        ]
    )

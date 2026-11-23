#!/usr/bin/python3
import os

import launch
import launch_ros
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _include(package, launch_file):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(package), "launch", launch_file)
        )
    )


def generate_launch_description():
    show_rviz = LaunchConfiguration("use_rviz")

    rviz_config_dir = os.path.join(
        get_package_share_directory("testbed_description"),
        "rviz",
        "full_bringup.rviz",
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz_node",
        parameters=[{"use_sim_time": True}],
        arguments=["-d", LaunchConfiguration("rvizconfig")],
        condition=IfCondition(show_rviz),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                name="rvizconfig",
                default_value=rviz_config_dir,
                description="Absolute path to the RViz configuration file",
            ),
            DeclareLaunchArgument(
                name="use_rviz",
                default_value="true",
                description="Launch RViz together with the simulation",
            ),
            _include("testbed_description", "robot_description.launch.py"),
            _include("testbed_gazebo", "spawn_playground.launch.py"),
            _include("testbed_gazebo", "spawn_testbed.launch.py"),
            rviz_node,
        ]
    )

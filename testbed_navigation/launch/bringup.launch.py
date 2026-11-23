"""Single-command bringup: simulation + map + AMCL + Nav2 servers."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _include(package, launch_file, launch_arguments=None):
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(package), "launch", launch_file)
        ),
        launch_arguments=(launch_arguments or {}).items(),
    )


def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")
    use_rviz = LaunchConfiguration("use_rviz")
    show_nav_rviz = LaunchConfiguration("nav_rviz")
    map_yaml = LaunchConfiguration("map")

    clock = {"use_sim_time": use_sim_time}

    simulation = _include(
        "testbed_bringup",
        "testbed_full_bringup.launch.py",
        {
            "use_rviz": use_rviz,
            "gui": LaunchConfiguration("gui"),
        },
    )

    map_loader = TimerAction(
        period=10.0,
        actions=[_include("testbed_navigation", "map_loader.launch.py", {"map": map_yaml})],
    )

    localization = TimerAction(
        period=13.0,
        actions=[_include("testbed_navigation", "localization.launch.py")],
    )

    navigation = TimerAction(
        period=18.0,
        actions=[_include("testbed_navigation", "navigation.launch.py")],
    )

    nav_rviz = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz_navigation",
        output="screen",
        parameters=[clock],
        arguments=[
            "-d",
            os.path.join(
                get_package_share_directory("testbed_description"),
                "rviz",
                "full_bringup.rviz",
            ),
        ],
        condition=IfCondition(show_nav_rviz),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_sim_time", default_value="true",
                description="Use the Gazebo clock instead of wall time",
            ),
            DeclareLaunchArgument(
                "use_rviz", default_value="true",
                description="Start RViz with the simulation",
            ),
            DeclareLaunchArgument(
                "nav_rviz", default_value="false",
                description="Start an additional RViz window for navigation",
            ),
            DeclareLaunchArgument(
                "gui", default_value="true",
                description="Start the Gazebo client GUI",
            ),
            DeclareLaunchArgument(
                "map", default_value=os.path.join(
                    get_package_share_directory("testbed_bringup"),
                    "maps",
                    "testbed_world.yaml",
                ),
                description="Absolute path to the map YAML file",
            ),
            simulation,
            map_loader,
            localization,
            navigation,
            nav_rviz,
        ]
    )

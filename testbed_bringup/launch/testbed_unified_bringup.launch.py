#!/usr/bin/env python3
"""
Unified single-command bringup: simulation + map + AMCL localization + Nav2 servers.

This replaces the need to launch multiple separate launch files.  Everything is
inlined in one file so a single ``ros2 launch`` command brings up the full stack:

    ros2 launch testbed_bringup testbed_unified_bringup.launch.py

Launch arguments mirror the arguments of the original individual launch files so
that existing workflows continue to work unchanged.
"""

import os

from ament_index_python.packages import get_package_share_directory, get_package_prefix
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # ------------------------------------------------------------------
    # Launch configurations
    # ------------------------------------------------------------------
    use_sim_time = LaunchConfiguration("use_sim_time")
    use_rviz = LaunchConfiguration("use_rviz")
    nav_rviz = LaunchConfiguration("nav_rviz")
    gui = LaunchConfiguration("gui")
    map_yaml = LaunchConfiguration("map")
    world = LaunchConfiguration("world")

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    pkg_testbed_bringup = get_package_share_directory("testbed_bringup")
    pkg_testbed_description = get_package_share_directory("testbed_description")
    pkg_testbed_gazebo = get_package_share_directory("testbed_gazebo")
    pkg_testbed_navigation = get_package_share_directory("testbed_navigation")
    pkg_gazebo_ros = get_package_share_directory("gazebo_ros")

    default_map_yaml = os.path.join(pkg_testbed_bringup, "maps", "testbed_world.yaml")
    default_world = os.path.join(
        pkg_testbed_gazebo, "worlds", "testbed_playground.world"
    )
    rviz_config_dir = os.path.join(
        pkg_testbed_description, "rviz", "full_bringup.rviz"
    )

    # Gazebo environment setup (mirrors spawn_playground.launch.py)
    description_package_name = "testbed_description"
    install_dir = get_package_prefix(description_package_name)
    gazebo_models_path = os.path.join(pkg_testbed_gazebo, "models")

    if "GAZEBO_MODEL_PATH" in os.environ:
        os.environ["GAZEBO_MODEL_PATH"] = (
            os.environ["GAZEBO_MODEL_PATH"]
            + ":"
            + install_dir
            + "/share"
            + ":"
            + gazebo_models_path
        )
    else:
        os.environ["GAZEBO_MODEL_PATH"] = (
            install_dir + "/share" + ":" + gazebo_models_path
        )

    if "GAZEBO_PLUGIN_PATH" in os.environ:
        os.environ["GAZEBO_PLUGIN_PATH"] = (
            os.environ["GAZEBO_PLUGIN_PATH"] + ":" + install_dir + "/lib"
        )
    else:
        os.environ["GAZEBO_PLUGIN_PATH"] = install_dir + "/lib"

    # ------------------------------------------------------------------
    # Robot description (robot_state_publisher)
    # ------------------------------------------------------------------
    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            PathJoinSubstitution(
                [
                    FindPackageShare("testbed_description"),
                    "urdf",
                    "testbed.xacro",
                ]
            ),
        ]
    )
    robot_description = {"robot_description": robot_description_content}

    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[robot_description, {"use_sim_time": True}],
    )

    # ------------------------------------------------------------------
    # Gazebo (server + client)
    # ------------------------------------------------------------------
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, "launch", "gazebo.launch.py"),
        ),
        launch_arguments={
            "world": world,
            "gui": gui,
            "verbose": "false",
        }.items(),
    )

    # ------------------------------------------------------------------
    # Spawn robot into Gazebo
    # ------------------------------------------------------------------
    spawn_robot = Node(
        package="gazebo_ros",
        executable="spawn_entity.py",
        name="spawn_entity",
        output="screen",
        arguments=[
            "-entity",
            "testbed",
            "-x", "0.0",
            "-y", "5.0",
            "-z", "0.0",
            "-R", "0.0",
            "-P", "0.0",
            "-Y", "0.0",
            "-topic", "/robot_description",
        ],
    )

    # ------------------------------------------------------------------
    # RViz (simulation view)
    # ------------------------------------------------------------------
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz_node",
        parameters=[{"use_sim_time": True}],
        arguments=["-d", LaunchConfiguration("rvizconfig")],
        condition=IfCondition(use_rviz),
    )

    # ------------------------------------------------------------------
    # Map server + lifecycle manager
    # ------------------------------------------------------------------
    map_server_params = {
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
        parameters=[map_server_params],
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

    # ------------------------------------------------------------------
    # AMCL localization + lifecycle manager
    # ------------------------------------------------------------------
    amcl_config = os.path.join(
        pkg_testbed_navigation, "config", "amcl_params.yaml"
    )

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

    # ------------------------------------------------------------------
    # Nav2 servers (planner, controller, behavior, bt_navigator) + lifecycle
    # ------------------------------------------------------------------
    nav2_config = os.path.join(
        pkg_testbed_navigation, "config", "nav2_params.yaml"
    )
    shared_parameters = [nav2_config, {"use_sim_time": use_sim_time}]

    def nav2_node(package, executable, name):
        return Node(
            package=package,
            executable=executable,
            name=name,
            output="screen",
            parameters=shared_parameters,
        )

    planner_server = nav2_node(
        "nav2_planner", "planner_server", "planner_server"
    )
    controller_server = nav2_node(
        "nav2_controller", "controller_server", "controller_server"
    )
    behavior_server = nav2_node(
        "nav2_behaviors", "behavior_server", "behavior_server"
    )
    bt_navigator = nav2_node(
        "nav2_bt_navigator", "bt_navigator", "bt_navigator"
    )

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

    # ------------------------------------------------------------------
    # Navigation RViz (separate window)
    # ------------------------------------------------------------------
    nav_rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz_navigation",
        output="screen",
        parameters=[{"use_sim_time": True}],
        arguments=["-d", rviz_config_dir],
        condition=IfCondition(nav_rviz),
    )

    # ------------------------------------------------------------------
    # Launch description with staged startup (TimerAction)
    # ------------------------------------------------------------------
    return LaunchDescription(
        [
            # ---- Launch arguments ----
            DeclareLaunchArgument(
                "use_sim_time",
                default_value="true",
                description="Use the Gazebo clock instead of wall time",
            ),
            DeclareLaunchArgument(
                "use_rviz",
                default_value="true",
                description="Launch RViz together with the simulation",
            ),
            DeclareLaunchArgument(
                "nav_rviz",
                default_value="false",
                description="Start an additional RViz window for navigation",
            ),
            DeclareLaunchArgument(
                "gui",
                default_value="true",
                description="Start the Gazebo client GUI",
            ),
            DeclareLaunchArgument(
                "map",
                default_value=default_map_yaml,
                description="Absolute path to the map YAML file",
            ),
            DeclareLaunchArgument(
                "world",
                default_value=default_world,
                description="SDF world file",
            ),
            DeclareLaunchArgument(
                "rvizconfig",
                default_value=rviz_config_dir,
                description="Absolute path to the RViz configuration file",
            ),
            # ---- Simulation (gazebo + robot description + spawn) ----
            robot_state_publisher_node,
            gazebo,
            TimerAction(
                period=3.0,
                actions=[spawn_robot],
            ),
            # ---- RViz (simulation view) ----
            rviz_node,
            # ---- Map (map_server + lifecycle manager) ----
            TimerAction(
                period=8.0,
                actions=[map_server, map_lifecycle],
            ),
            # ---- Localization (AMCL + lifecycle manager) ----
            TimerAction(
                period=11.0,
                actions=[amcl_node, TimerAction(period=2.0, actions=[localization_lifecycle])],
            ),
            # ---- Navigation servers + lifecycle manager ----
            TimerAction(
                period=15.0,
                actions=[
                    planner_server,
                    controller_server,
                    behavior_server,
                    bt_navigator,
                    TimerAction(period=3.0, actions=[navigation_lifecycle]),
                ],
            ),
            # ---- Navigation RViz ----
            nav_rviz_node,
        ]
    )

# testbed_navigation

Manual Nav2 navigation stack for the **Testbed-T1.0.0** platform. Instead of
using `nav2_bringup`, every stage of the navigation workflow is started from its
own launch file so each part can be debugged on its own.

## Unified bringup

For convenience, `testbed_bringup/launch/testbed_unified_bringup.launch.py`
starts all stages (simulation + map + localization + Nav2 servers) from a
single command:

```bash
ros2 launch testbed_bringup testbed_unified_bringup.launch.py
```

Stages are staggered with `TimerAction` so each one is ready before the next
starts:
- t=0s: robot_state_publisher + Gazebo
- t=3s: robot spawn into Gazebo + RViz
- t=8s: map_server + lifecycle manager
- t=11s: AMCL + localization lifecycle manager
- t=15s: Nav2 servers + navigation lifecycle manager

## Approach

The workflow is split into three independent stages:

| Stage | Launch file | Nav2 components |
|-------|-------------|-----------------|
| Map loading | `launch/map_loader.launch.py` | `nav2_map_server` + lifecycle manager |
| Localization | `launch/localization.launch.py` | `nav2_amcl` + lifecycle manager |
| Navigation | `launch/navigation.launch.py` | planner, controller, behaviors and BT navigator + lifecycle manager |

Each stage has its own lifecycle manager (`map_lifecycle_manager`,
`localization_lifecycle_manager`, `navigation_lifecycle_manager`) with
`autostart: true` and `bond_timeout: 0.0`. Bonds are disabled because lifecycle
bonds are unreliable under a loaded simulation clock; autostart plus a short
`TimerAction` delay is enough to bring each stage up in order.

`launch/rviz.launch.py` reuses the RViz layout from `testbed_description` for
visualisation only; it is not required by the navigation stack.

## Files

```
testbed_navigation/
├── config/
│   ├── amcl_params.yaml     # AMCL particle filter, motion and laser models
│   └── nav2_params.yaml     # planner, controller, costmaps, behaviors, BT
├── launch/
│   ├── map_loader.launch.py
│   ├── localization.launch.py
│   ├── navigation.launch.py
│   └── rviz.launch.py
├── CMakeLists.txt
├── package.xml
└── README.md
```

## Plugins used

- **Map server** – `nav2_map_server`, loading `testbed_bringup/maps/testbed_world.yaml`
  (the `map` argument can override the path).
- **Localization** – `nav2_amcl` with
  `nav2_amcl::DifferentialMotionModel` and the `likelihood_field` beam model.
  The initial pose is seeded at the Gazebo spawn pose `(0.0, 5.0, 0.0)`.
  `always_reset_initial_pose: true` so that RViz pose estimates keep being
  accepted after the first rejection.
- **Global planner** – `nav2_navfn_planner/NavfnPlanner` (A*, unknown space
  allowed).
- **Local controller** – `dwb_core::DWBLocalPlanner` with the BaseObstacle,
  Oscillation, GoalAlign, PathAlign, GoalDist, PathDist and RotateToGoal
  critics.
- **Recovery behaviors** – `nav2_behaviors` spin/backup/drive-on-heading/wait.
- **Task orchestration** – `nav2_bt_navigator` with `NavigateToPose` and
  `NavigateThroughPoses`.
- **Costmaps** – `nav2_costmap_2d::StaticLayer`, `ObstacleLayer` and
  `InflationLayer`; the local costmap is a rolling window, the global one is
  map-aligned.

### Transform tolerance

`transform_tolerance` was raised to **2.0 s** on the local costmap, global
costmap, DWB controller and behavior server to survive Gazebo TF publication
gaps. `bt_navigator` uses **1.0 s**. This prevents
`Lookup would require extrapolation into the future` errors that otherwise
abort goal execution.

### Footprint

`base_footprint` is not at the geometric centre of the chassis (the body spans
roughly `x ∈ [-0.24, 0.14]`, `y ∈ [-0.26, 0.18]`), so a centred circle would
leave part of the robot uncovered. Both costmaps therefore use an offset
rectangular polygon:

```
[[0.14, 0.18], [0.14, -0.26], [-0.24, -0.26], [-0.24, 0.18]]
```

## Running

Source the workspace first, then start each stage in order (separate terminals
are convenient):

```bash
source /opt/ros/humble/setup.bash
source ~/assignment_ws/install/setup.bash

# 1. Simulation (Gazebo + robot state publisher); add use_rviz:=false to skip RViz
ros2 launch testbed_bringup testbed_full_bringup.launch.py

# 2. Static map
ros2 launch testbed_navigation map_loader.launch.py

# 3. AMCL
ros2 launch testbed_navigation localization.launch.py

# 4. Navigation servers
ros2 launch testbed_navigation navigation.launch.py
```

Or run everything from one file:

```bash
ros2 launch testbed_bringup testbed_unified_bringup.launch.py
```

Optional RViz (if not started with the bringup):

```bash
ros2 launch testbed_navigation rviz.launch.py
```

Send a navigation goal either from RViz (`2D Goal Pose`) or from the CLI:

```bash
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: map}, pose: {position: {x: 2.0, y: 5.0}}}}"
```

**Important:** When using RViz's `2D Pose Estimate` tool, set RViz's
**Fixed Frame to `map`**. AMCL only accepts initial poses in the global
`map` frame; poses in `odom` are ignored.

## Testing each component

```bash
# Map loaded?
ros2 lifecycle get /map_server
ros2 topic echo /map --once

# Localized?
ros2 run tf2_ros tf2_echo map base_footprint
ros2 topic echo /amcl_pose --once

# Navigation servers active?
ros2 lifecycle get /planner_server
ros2 lifecycle get /controller_server
ros2 lifecycle get /bt_navigator
```

## Runtime validation (Gazebo Classic 11, headless)

Environment: `ROS_DOMAIN_ID=73`, `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`,
Gazebo server without the client, ground truth read with `gz model -m testbed -p`.

- **Map loading** – `map_server` reached `active`; `/map` was published as
  `405 x 400` cells at `0.05 m`, frame `map`. No errors in the map log.
- **Localization** – `amcl` reached `active`; `map -> base_footprint` matched
  Gazebo ground truth to **~0.05 m** at the spawn pose and **~0.07 m** after
  driving through the room.
- **Navigation** – goals were sent with
  `ros2 action send_goal /navigate_to_pose ...` from a clean stack:

| Goal (map frame) | Result | Gazebo ground truth | Error |
|------------------|--------|---------------------|-------|
| (2.0, 5.0) | SUCCEEDED | approx. (1.80, 4.99) | ~0.20 m |
| (6.0, 7.0) | SUCCEEDED | (5.86, 6.85) | ~0.20 m |
| (3.6, -2.0) through doorway | SUCCEEDED | (3.68, -2.09) | ~0.12 m |
| (0.0, 5.0) after nav-stack restart | SUCCEEDED | (0.18, 4.98) | ~0.18 m |

All four goals were reached. One earlier attempt at the home goal, made after
several minutes of continuous operation without restarting the Nav2 servers,
aborted with `Received plan with zero length` (the DWB global plan had been
pruned away). Restarting `navigation.launch.py` and resending the same goal
succeeded, which matches the known long-run TF/path-staleness behaviour of this
simulation.

## Challenges

- **Lidar range vs. room size** – with the original 1.5 m maximum range AMCL
  never saw a wall from most of the room, so particles could not collapse and
  the costmaps had no obstacles. Raising the range to 10 m fixed both.
- **Wheel separation** – the starter value (0.35 m) did not match the physical
  track (0.376 m). The robot reached goals but overshot/undershot turns, so
  odometry was corrected first.
- **/tf bandwidth** – publishing odometry and wheel transforms at 100 Hz
  starved the controller's TF listener and caused `transform data too old`
  errors. Dropping the diff-drive update rate to 30 Hz keeps TF well below the
  previous load (~116 msg/s instead of ~300 msg/s).
- **Startup ordering** – AMCL and the Nav2 servers must be configured before
  the lifecycle manager activates them; a short delay before each lifecycle
  manager avoids "node not found" / configure timeouts.
- **Footprint centring** – because the robot frame is offset from the chassis,
  a rectangular footprint is required for the costmap inflation to protect the
  whole body.
- **AMCL initial pose rejection** – AMCL ignored `2D Pose Estimate` clicks
  because they were in `odom` frame rather than `map`. Setting RViz's Fixed
  Frame to `map` (and `always_reset_initial_pose: true`) resolved this.

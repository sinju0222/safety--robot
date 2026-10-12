#!/usr/bin/env bash
# Ubuntu ROS machine. Hardware drivers, SLAM/localization, Nav2 must ALREADY be running.
set -euo pipefail
: "${SAFETY_BACKEND_URL:?Set SAFETY_BACKEND_URL=http://WINDOWS_IP:8000}"
: "${SAFETY_WORKPLACE_ID:?Set SAFETY_WORKPLACE_ID to actual workplace id}"
: "${SAFETY_PATROL_TOKEN:?Set a shared SAFETY_PATROL_TOKEN on BOTH PCs}"
source /opt/ros/jazzy/setup.bash
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="${SAFETY_ROS_WORKSPACE:-$HOME/ros2_ws}"
source "$WORKSPACE/install/setup.bash"
mkdir -p "$HOME/robot_change_output"
if ! ros2 topic list | grep -qx '/map'; then
  echo 'ERROR: /map not available. Start Nav2 map_server/SLAM first.' >&2; exit 1
fi
if ! ros2 topic list | grep -qx '/scan'; then
  echo 'ERROR: /scan not available. Start LiDAR driver first.' >&2; exit 1
fi
if ! ros2 topic list | grep -qx '/camera/camera/color/image_raw'; then
  echo 'WARNING: RealSense RGB missing; events/photos will not be produced.' >&2
fi
if ! ros2 pkg executables robot_change_detector | grep -q 'robot_change_detector'; then
  echo 'ERROR: package not built. Run colcon build --symlink-install --packages-select robot_change_detector.' >&2; exit 1
fi
ros2 run robot_change_detector robot_change_detector &
DETECTOR=$!
ros2 run robot_change_detector patrol_controller &
CONTROLLER=$!
cleanup() {
  kill "$DETECTOR" "$CONTROLLER" 2>/dev/null || true
  wait "$DETECTOR" "$CONTROLLER" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
wait -n "$DETECTOR" "$CONTROLLER"
echo 'One ROS2 process exited; stopping other process.' >&2

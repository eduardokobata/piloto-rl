#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -d "/ros2_ws" ]; then
    CONFIG_DIR="/ros2_ws/src/first_slam/first_slam/config"
else
    CONFIG_DIR="/home/ekm/Documents/piloto_rl/SLAM/src/first_slam/first_slam/config"
fi

echo "=== Iniciando Cartographer ==="
ros2 run cartographer_ros cartographer_node \
    --configuration_directory "$CONFIG_DIR" \
    --configuration_basename fsds_cartographer.lua \
    --ros-args \
    --remap odom:=fsdsOdometry \
    --remap points2:=fsdsLidar3D \
    --remap imu:=fsdsImu \
    --remap landmarks:=fsdsLandmarks &
CARTO_PID=$!

echo "=== Iniciando viz_node ==="
python3 "$SCRIPT_DIR/viz_node.py" &
VIZ_PID=$!

echo "=== Iniciando map_viewer (matplotlib) ==="
python3 "$SCRIPT_DIR/map_viewer.py"

echo "Viewer fechado. Encerrando tudo..."
kill $CARTO_PID $VIZ_PID 2>/dev/null
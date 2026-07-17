#!/bin/bash
set -e

IMAGE_NAME="fsd-ros2-slam"

echo "=== Construindo imagem do SLAM ==="
docker build -t $IMAGE_NAME .

echo "=== Iniciando Cartographer (Core SLAM) ==="
xhost +local:docker > /dev/null

# Adicione a flag --name e force o container a não fechar com /bin/bash no final
docker run --rm -it \
    --name slam_container \
    --network host \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
    --device /dev/dri:/dev/dri \
    -v "$(pwd):/app" \
    $IMAGE_NAME \
    /bin/bash -c "source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash && ros2 run cartographer_ros cartographer_node --configuration_directory /ros2_ws/src/first_slam/first_slam/config --configuration_basename fsds_cartographer.lua --ros-args --remap odom:=fsdsOdometry --remap points2:=fsdsLidar3D --remap imu:=fsdsImu --remap landmarks:=fsdsLandmarks || /bin/bash"
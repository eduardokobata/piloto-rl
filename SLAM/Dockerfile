FROM ros:humble-ros-base-jammy

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-cartographer-ros \
    ros-humble-nav-msgs \
    ros-humble-sensor-msgs \
    ros-humble-rviz2 \
    ros-humble-tf2-tools \
    python3-colcon-common-extensions \
    python3-matplotlib \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws

COPY ./src ./src

RUN source /opt/ros/humble/setup.bash && colcon build --symlink-install

RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc \
    && echo "source /ros2_ws/install/setup.bash" >> ~/.bashrc

ENV ROS_DOMAIN_ID=0

CMD ["/bin/bash", "-c", "source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash && ros2 run cartographer_ros cartographer_node --configuration_directory /ros2_ws/src/first_slam/first_slam/config --configuration_basename fsds_cartographer.lua --ros-args --remap odom:=fsdsOdometry --remap points2:=fsdsLidar3D --remap imu:=fsdsImu --remap landmarks:=fsdsLandmarks"]
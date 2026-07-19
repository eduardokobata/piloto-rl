from fileinput import filename

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry
import math
import sys
import os
import shutil
import csv

print("--- INS.PY INICIADO (GERADOR DE CSV) ---")
sys.stdout.flush()

class InsBridgeNode(Node):
    def __init__(self):
        super().__init__('ins_bridge_node')
        self.get_logger().info('Iniciando InsBridgeNode...')
        
        self.lap_counter = 0
        self.em_volta = False
        
        # Buffer para armazenar a trajetória da volta atual[cite: 1]
        self.trajetoria_buffer = []
        
        self.imu_pub = self.create_publisher(Imu, 'fsdsImu', 10)
        self.odom_pub = self.create_publisher(Odometry, 'fsdsOdometry', 10)
        
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.last_time = self.get_clock().now()
        
        self.timer = self.create_timer(0.1, self.timer_callback)
        self.get_logger().info('Timer iniciado.')

    def timer_callback(self):
        try:
            current_time = self.get_clock().now()
            dt = (current_time - self.last_time).nanoseconds / 1e9
            self.last_time = current_time

            accel_x, yaw_rate, accel_y, speed_x = 0.1, 0.05, 0.0, 5.0
            accel_z, speed_y = 9.8, 0.0
            
            self.theta += yaw_rate * dt
            self.x += (speed_x * math.cos(self.theta) - speed_y * math.sin(self.theta)) * dt
            self.y += (speed_x * math.sin(self.theta) + speed_y * math.cos(self.theta)) * dt

            self.trajetoria_buffer.append((self.x, self.y))

            imu_msg = Imu()
            imu_msg.header.stamp = current_time.to_msg()
            imu_msg.header.frame_id = 'imu_link'
            imu_msg.linear_acceleration.x = accel_x
            imu_msg.linear_acceleration.y = accel_y
            imu_msg.linear_acceleration.z = accel_z
            imu_msg.angular_velocity.z = yaw_rate

            odom_msg = Odometry()
            odom_msg.header.stamp = current_time.to_msg()
            odom_msg.header.frame_id = 'odom'
            odom_msg.child_frame_id = 'base_link'
            odom_msg.pose.pose.position.x = self.x
            odom_msg.pose.pose.position.y = self.y

            dist_origem = math.sqrt(self.x**2 + self.y**2)
        
            # Lógica de detecção de volta
            if dist_origem > 5.0:
                self.em_volta = True
                
            if self.em_volta and dist_origem < 0.5:
                self.lap_counter += 1
                self.get_logger().info(f"VOLTA {self.lap_counter} COMPLETADA!")
                self.salvar_trajetoria_csv()
                self.em_volta = False 

            self.imu_pub.publish(imu_msg)
            self.odom_pub.publish(odom_msg)
            
        except Exception as e:
            self.get_logger().error(f'Erro no callback: {e}')

    def salvar_trajetoria_csv(self):
        filename = f'/app/trajetoria_volta_{self.lap_counter}.csv'
        latest_filename = '/app/pista_slam.csv'
        
        try:
            with open(filename, 'w') as f:
                f.write("X,Y\n")
                for ponto in self.trajetoria_buffer:
                    f.write(f"{ponto[0]},{ponto[1]}\n")
            
            os.system(f"chmod 666 {filename}")
            self.get_logger().info(f"Trajetória salva: {filename} com {len(self.trajetoria_buffer)} pontos.")
            
            # Copy to latest
            shutil.copy(filename, latest_filename)
            os.system(f"chmod 666 {latest_filename}")
            self.get_logger().info(f"Cópia da trajetória mais recente salva em: {latest_filename}")
            
            self.trajetoria_buffer = []
            
        except Exception as e:
            self.get_logger().error(f"Erro ao salvar CSV: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = InsBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
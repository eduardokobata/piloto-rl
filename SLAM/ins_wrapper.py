import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
import math
import sys
import os
import shutil

sys.stdout.flush()

 

class InsTrajectoryRecorderNode(Node):
    '''
    Subscriber que recebe as informações das ROS2 nodes do ins e da odometria, e cria arquivos .csv
    da trajetória 
    '''
    def __init__(self):
        super().__init__('ins_trajectory_recorder_node')
        self.get_logger().info('iniciando wrapper do ins')
        
        self.lap_counter = 0
        self.em_volta = False
        self.trajetoria_buffer = []
        
        self.odom_sub = self.create_subscription(
            Odometry, 
            'fsdsOdometry', 
            self.odom_callback, 
            10
        )
        

    def odom_callback(self, msg):
        try:
            x = msg.pose.pose.position.x
            y = msg.pose.pose.position.y

            self.trajetoria_buffer.append((x, y))

            dist_origem = math.sqrt(x**2 + y**2)
        
            if dist_origem > 5.0:
                self.em_volta = True
                
            if self.em_volta and dist_origem < 0.5:
                self.lap_counter += 1
                self.get_logger().info(f"VOLTA {self.lap_counter} COMPLETADA!")
                self.salvar_trajetoria_csv()
                self.em_volta = False
            
        except Exception as e:
            self.get_logger().error(f'Erro no processamento da odometria: {e}')

    def salvar_trajetoria_csv(self):
        filename = f'/app/output/trajetoria_volta_{self.lap_counter}.csv'
        latest_filename = '/app/output/pista_slam.csv'
        
        try:
            with open(filename, 'w') as f:
                f.write("X,Y\n")
                for ponto in self.trajetoria_buffer:
                    f.write(f"{ponto[0]},{ponto[1]}\n")
            
            os.system(f"chmod 666 {filename}")
            
            shutil.copy(filename, latest_filename)
            os.system(f"chmod 666 {latest_filename}")
            
            self.trajetoria_buffer = []
            
        except Exception as e:
            self.get_logger().error(f"Erro ao salvar CSV: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = InsTrajectoryRecorderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
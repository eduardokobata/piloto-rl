import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Quaternion
import math
import sys

from cartographer_ros_msgs.srv import WriteState
from std_srvs.srv import Empty 



print("--- INS.PY INICIADO ---")
sys.stdout.flush()



class InsBridgeNode(Node):
    def __init__(self):
        super().__init__('ins_bridge_node')
        self.get_logger().info('Iniciando InsBridgeNode...')
        
        #Variaveis p/ salvar mapa
        self.client_save_map = self.create_client(WriteState, '/write_state')        
        self.lap_counter = 0
        self.em_volta = False
        
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
            
            imu_msg = Imu()
            imu_msg.header.stamp = current_time.to_msg()
            imu_msg.header.frame_id = 'imu_link'
            imu_msg.linear_acceleration.x = accel_x
            imu_msg.linear_acceleration.y = accel_y
            imu_msg.linear_acceleration.z = accel_z
            imu_msg.angular_velocity.z = yaw_rate

         
            self.theta += yaw_rate * dt
            self.x += (speed_x * math.cos(self.theta) - speed_y * math.sin(self.theta)) * dt
            self.y += (speed_x * math.sin(self.theta) + speed_y * math.cos(self.theta)) * dt

            odom_msg = Odometry()
            odom_msg.header.stamp = current_time.to_msg()
            odom_msg.header.frame_id = 'odom'
            odom_msg.child_frame_id = 'base_link'
            odom_msg.pose.pose.position.x = self.x
            odom_msg.pose.pose.position.y = self.y


            dist_origem = math.sqrt(self.x**2 + self.y**2)
        

            if dist_origem > 5.0:
                self.em_volta = True
                
            if self.em_volta and dist_origem < 0.5:
                self.lap_counter += 1
                self.get_logger().info(f"VOLTA {self.lap_counter} COMPLETADA!")
                
                self.salvar_mapa_automatizado()
                
                self.em_volta = False


           
            self.imu_pub.publish(imu_msg)
            self.odom_pub.publish(odom_msg)
            
            
        except Exception as e:
            self.get_logger().error(f'Erro no callback: {e}')

    def salvar_mapa_automatizado(self):
        if not self.client_save_map.service_is_ready():
            self.get_logger().warn('Serviço de salvar mapa não está pronto ainda.')
            return

        request = WriteState.Request()
        request.filename = f'/app/mapa_volta_{self.lap_counter}.pbstream'
        request.include_unfinished_submaps = True
        
        future = self.client_save_map.call_async(request)
        self.get_logger().info(f"Pedido de salvamento enviado para a volta {self.lap_counter}!")
        os.system(f"chmod 666 {filename}")


def main(args=None):
    print("--- ENTRANDO NO MAIN ---")
    sys.stdout.flush()
    try:
        rclpy.init(args=args)
        print("--- RCLPY INICIALIZADO ---")
        sys.stdout.flush()
        node = InsBridgeNode()
        print("--- NODE CRIADO ---")
        sys.stdout.flush()
        rclpy.spin(node)
    except Exception as e:
        print(f"--- ERRO CRÍTICO NO MAIN: {e} ---")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
    finally:
        print("--- FINALIZANDO ---")
        sys.stdout.flush()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

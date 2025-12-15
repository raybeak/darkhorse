import rclpy
from rclpy.node import Node
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
from std_msgs.msg import String, Bool

class Nav2SpeedManager(Node):
    def __init__(self):
        super().__init__('nav2_speed_manager')

        # [설정 1] Nav2 컨트롤러 연결
        self.cli = self.create_client(SetParameters, '/controller_server/set_parameters')
        
        # [설정 2] Nav2가 켜져있는지 확인 (1초 대기)
        if not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn('Warning: Nav2 is not ready yet. Make sure to launch Nav2 first!')

        # [설정 3] Foxglove UI 버튼 명령 받기
        self.sub_ui = self.create_subscription(String, '/ui_command', self.ui_callback, 10)
        
        # [설정 4] 비상정지 신호 보내기 (BT 연동용)
        self.pub_emergency = self.create_publisher(Bool, '/emergency_stop', 10)

        # 초기 속도
        self.current_max_speed = 0.5
        
        # ★ Limo 사용자 필독 ★
        # Limo는 보통 'DWBLocalPlanner'를 사용합니다.
        # 만약 작동 안 하면 'FollowPath'로 바꿔야 합니다.
        self.plugin_name = 'DWBLocalPlanner' 
        
        self.get_logger().info(f"Limo Speed Manager Started. Plugin: {self.plugin_name}")

    def ui_callback(self, msg):
        cmd = msg.data
        if cmd == "speed_up":
            self.change_speed(0.1)
        elif cmd == "speed_down":
            self.change_speed(-0.1)
        elif cmd == "emergency":
            self.trigger_emergency()

    def change_speed(self, delta):
        # 부동소수점 오차 제거
        new_speed = round(self.current_max_speed + delta, 2)
        
        # Limo 안전 속도 범위 (0.0 ~ 0.8 m/s)
        new_speed = max(0.0, min(new_speed, 0.8))
        
        self.current_max_speed = new_speed
        
        # Nav2에 속도 변경 요청
        req = SetParameters.Request()
        req.parameters = [
            Parameter(
                name=f'{self.plugin_name}.max_vel_x', 
                value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=new_speed)
            )
        ]
        
        self.cli.call_async(req)
        self.get_logger().info(f"🚀 Speed set to: {new_speed} m/s")

    def trigger_emergency(self):
        self.get_logger().error("🚨 EMERGENCY STOP! 🚨")
        
        # 1. BT로 정지 신호 전송
        msg = Bool()
        msg.data = True
        self.pub_emergency.publish(msg)
        
        # 2. 즉시 속도 0으로 설정
        self.current_max_speed = 0.0
        self.change_speed(0.0)

def main(args=None):
    rclpy.init(args=args)
    node = Nav2SpeedManager()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
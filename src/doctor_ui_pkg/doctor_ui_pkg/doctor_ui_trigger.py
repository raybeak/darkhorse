import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import subprocess
import os

# 감시할 진료과 이름 (이 PC가 '내과'라고 가정)
TARGET_DEPARTMENT = "내과"
# 실행할 앱 파일 이름
APP_FILENAME = "doctor_app.py"

class DoctorUITrigger(Node):
    def __init__(self):
        super().__init__('doctor_ui_trigger')
        
        # 1. 도착 신호 수신 (Subscriber)
        self.subscription = self.create_subscription(
            String,
            '/hospital/arrival_status',
            self.listener_callback,
            10
        )
        self.is_app_running = False
        self.get_logger().info(f"✅ [UI Trigger] '{TARGET_DEPARTMENT}' 도착 대기 중... (패키지: doctor_ui_pkg)")

    def listener_callback(self, msg):
        arrived_location = msg.data
        
        # 2. 내 진료과에 도착했는지 확인
        if arrived_location == TARGET_DEPARTMENT:
            self.get_logger().info(f"📩 신호 수신: {arrived_location} 도착!")
            
            if not self.is_app_running:
                self.trigger_app()
            else:
                self.get_logger().warn("⚠️ 앱이 이미 실행 중입니다.")

    def trigger_app(self):
        """Streamlit 앱 실행"""
        try:
            # 현재 파일 위치를 기준으로 앱 경로 찾기 (절대 경로)
            current_dir = os.path.dirname(os.path.realpath(__file__))
            app_path = os.path.join(current_dir, APP_FILENAME)

            self.get_logger().info(f"🚀 UI 실행 중: {app_path}")
            
            # 터미널 명령 실행: streamlit run doctor_app.py
            subprocess.Popen(["streamlit", "run", app_path])
            
            self.is_app_running = True
            
        except Exception as e:
            self.get_logger().error(f"❌ 실행 실패: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = DoctorUITrigger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

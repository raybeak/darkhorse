import sys
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QFrame, QScrollArea
from PyQt5.QtCore import QTimer, Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

# ROS 스레드에서 GUI 스레드로 신호를 보내기 위한 시그널 클래스
class GuiSignal(QObject):
    update_signal = pyqtSignal(dict)

class PatientGUI(QWidget):
    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node
        self.medical_history = [] # 진료 기록을 저장할 리스트
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('KAU Hospital - 환자용 안내 시스템')
        self.setGeometry(100, 100, 400, 500)
        self.setStyleSheet("background-color: #F0F2F5;")

        layout = QVBoxLayout()
        
        # [상단] 타이틀
        self.lbl_title = QLabel('KAU HOSPITAL')
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.lbl_title.setFont(QFont('Arial', 24, QFont.Bold))
        self.lbl_title.setStyleSheet("color: #003366;")
        layout.addWidget(self.lbl_title)

        # [중단] 현재 상태 (의사가 입력하면 바뀜)
        self.lbl_status = QLabel('현재 상태: 대기 중')
        self.lbl_status.setStyleSheet("font-size: 18px; padding: 15px; background-color: white; border-radius: 10px; border: 2px solid #007BFF;")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

        layout.addStretch(1)

        # [하단] 귀가 버튼
        self.btn_home = QPushButton('Return Home (귀가 및 결과 확인)')
        self.btn_home.setFont(QFont('Arial', 14, QFont.Bold))
        self.btn_home.setStyleSheet("background-color: #FF5733; color: white; border-radius: 15px; padding: 15px;")
        self.btn_home.clicked.connect(self.show_final_diagnosis)
        layout.addWidget(self.btn_home)

        self.setLayout(layout)

    def receive_data(self, data):
        """의사가 보낸 데이터를 받아서 처리"""
        self.medical_history.append(data) # 기록 저장
        
        # 화면 갱신
        next_wp = data.get('next_waypoint', '알 수 없음')
        dept = data.get('department', '진료과')
        self.lbl_status.setText(f"[{dept}] 진료 완료.\n\n다음 이동 장소:\n{next_wp}")

    def show_final_diagnosis(self):
        """저장된 모든 진료 기록을 팝업으로 출력"""
        if not self.medical_history:
            QMessageBox.information(self, "안내", "아직 진행된 진료 내역이 없습니다.")
            return

        report_text = "====== [KAU HOSPITAL 최종 진단서] ======\n\n"
        
        for idx, record in enumerate(self.medical_history, 1):
            report_text += f"{idx}. {record['department']}\n"
            report_text += f"   - 진단: {record['diagnosis']}\n"
            report_text += f"   - 소견: {record['note']}\n"
            report_text += "----------------------------------------\n"
        
        report_text += "\n위와 같이 진단하였음.\n안녕히 가십시오."

        msg = QMessageBox()
        msg.setWindowTitle("최종 진단 리포트")
        msg.setText(report_text)
        msg.exec_()
        
        self.ros_node.get_logger().info("최종 리포트 출력 완료. 로봇 복귀 명령 전송.")


class PatientGuiNode(Node):
    def __init__(self):
        super().__init__('patient_gui_node')
        self.gui_signal = GuiSignal()
        self.gui = None

        # 의사 노드가 보내는 'medical_record' 토픽 구독
        self.subscription = self.create_subscription(
            String,
            'medical_record',
            self.listener_callback,
            10)

    def set_gui(self, gui):
        self.gui = gui
        # 시그널 연결 (ROS 스레드 -> GUI 스레드 안전한 통신)
        self.gui_signal.update_signal.connect(self.gui.receive_data)

    def listener_callback(self, msg):
        try:
            # JSON 문자열을 딕셔너리로 변환
            data = json.loads(msg.data)
            self.get_logger().info(f'Received Diagnosis: {data}')
            # GUI 업데이트 요청
            self.gui_signal.update_signal.emit(data)
        except json.JSONDecodeError:
            self.get_logger().error('Failed to decode JSON')

def main(args=None):
    rclpy.init(args=args)
    node = PatientGuiNode()
    
    app = QApplication(sys.argv)
    gui = PatientGUI(node)
    node.set_gui(gui)
    gui.show()

    # ROS 루프 통합
    timer = QTimer()
    timer.timeout.connect(lambda: rclpy.spin_once(node, timeout_sec=0))
    timer.start(10)

    app.exec_()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
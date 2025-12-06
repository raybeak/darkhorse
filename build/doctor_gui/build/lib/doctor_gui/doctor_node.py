import sys
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QLineEdit, QComboBox, QMessageBox
from PyQt5.QtCore import Qt

class DoctorGUI(QWidget):
    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('KAU Hospital - 의료진용 차트')
        self.setGeometry(600, 100, 400, 500) # 환자용 GUI와 겹치지 않게 위치 조정

        layout = QVBoxLayout()

        # 1. 진료과 선택
        layout.addWidget(QLabel("진료 부서:"))
        self.combo_dept = QComboBox()
        self.combo_dept.addItems(["내과", "정형외과", "이비인후과", "약국"])
        layout.addWidget(self.combo_dept)

        # 2. 진단명 입력
        layout.addWidget(QLabel("진단명 (Diagnosis):"))
        self.input_diagnosis = QLineEdit()
        layout.addWidget(self.input_diagnosis)

        # 3. 의사 소견 입력
        layout.addWidget(QLabel("의사 소견 (Doctor's Note):"))
        self.input_note = QTextEdit()
        layout.addWidget(self.input_note)

        # 4. 다음 이동 장소
        layout.addWidget(QLabel("다음 이동 장소 (Next Waypoint):"))
        self.input_next_wp = QLineEdit()
        self.input_next_wp.setPlaceholderText("예: 약국, 로비, 귀가")
        layout.addWidget(self.input_next_wp)

        # 5. 전송 버튼
        self.btn_send = QPushButton("진료 완료 및 다음 장소 이동")
        self.btn_send.setStyleSheet("background-color: #007BFF; color: white; font-weight: bold; padding: 10px;")
        self.btn_send.clicked.connect(self.send_report)
        layout.addWidget(self.btn_send)

        self.setLayout(layout)

    def send_report(self):
        dept = self.combo_dept.currentText()
        diag = self.input_diagnosis.text()
        note = self.input_note.toPlainText()
        next_wp = self.input_next_wp.text()

        if not diag or not next_wp:
            QMessageBox.warning(self, "경고", "진단명과 다음 이동 장소를 입력해주세요.")
            return

        # 데이터를 딕셔너리로 만듦
        report_data = {
            "department": dept,
            "diagnosis": diag,
            "note": note,
            "next_waypoint": next_wp
        }

        # ROS 노드를 통해 데이터 전송
        self.ros_node.publish_report(report_data)
        
        QMessageBox.information(self, "성공", f"{dept} 진료 기록 저장 완료.\n{next_wp}(으)로 이동 명령을 전송합니다.")
        
        # 입력창 초기화
        self.input_diagnosis.clear()
        self.input_note.clear()
        self.input_next_wp.clear()

class DoctorNode(Node):
    def __init__(self):
        super().__init__('doctor_node')
        # 진료 기록을 퍼블리시하는 퍼블리셔 (JSON 문자열로 보냄)
        self.publisher_ = self.create_publisher(String, 'medical_record', 10)

    def publish_report(self, data_dict):
        msg = String()
        msg.data = json.dumps(data_dict, ensure_ascii=False) # 한글 깨짐 방지
        self.publisher_.publish(msg)
        self.get_logger().info(f'Sent Report: {msg.data}')

def main(args=None):
    rclpy.init(args=args)
    node = DoctorNode()
    app = QApplication(sys.argv)
    gui = DoctorGUI(node)
    gui.show()
    app.exec_()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
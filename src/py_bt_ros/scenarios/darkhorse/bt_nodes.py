import math
import json
import random
from modules.base_bt_nodes import (
    BTNodeList, Status, SyncAction, Node, 
    Sequence, Fallback, ReactiveSequence, ReactiveFallback, Parallel,
)
from modules.base_bt_nodes_ros import ActionWithROSAction, ConditionWithROSTopics
# ROS 2 Messages
from limo_interfaces.action import Speak as speakActionMsg
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String, Bool
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus
from nav_msgs.msg import Odometry
import ast

# bb = blackboard 
# ---------------------------------------------------------
# 병원 진료과 좌표 매핑 (예시 - 실제 맵 좌표에 맞게 수정 필요)
# ---------------------------------------------------------
DEPARTMENT_COORDINATES = {
    "진단검사의학과": {"x": 0.48, "y": 0.27, "w": 1.0},
    "영상의학과":    {"x": 6.57, "y": 2.62, "w": 1.0},
    "내과":          {"x": 7.44, "y": 0.51, "w": 1.0},
    "정형외과":      {"x": 0.75, "y": -2.64, "w": 1.0},
    "신경과":        {"x": 2.83, "y": 1.17, "w": 1.0},
    "안내데스크":    {"x": 0.48, "y": 0.27, "w": 1.0}
}

DEFAULT_DEPARTMENTS = ["진단검사의학과", "영상의학과", "내과", "정형외과", "신경과"]

#emergency 비상데스크 이동

class GoToInfoDesk(ActionWithROSAction):
    def __init__(self, name, agent):
        super().__init__(name, agent, (NavigateToPose, '/navigate_to_pose'))

    def _build_goal(self, agent, bb):
        coords = DEPARTMENT_COORDINATES.get("안내데스크") # 좌표 가져오기
        if not coords: return None

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.ros.node.get_clock().now().to_msg()
        goal.pose.pose.position.x = float(coords['x'])
        goal.pose.pose.position.y = float(coords['y'])
        goal.pose.pose.orientation.w = float(coords['w'])
        
        print(f"[GoToInfoDesk] 🚨 비상 상황! 안내데스크({coords})로 이동합니다.")
        return goal

    def _interpret_result(self, result, agent, bb, status_code=None):
        if status_code == GoalStatus.STATUS_SUCCEEDED:
            print("[GoToInfoDesk] 안내데스크 도착 완료.")
            return Status.SUCCESS
        return Status.FAILURE # <--- [수정] 이 부분이 잘려있었음. 추가 필요!

# ---------------------------------------------------------
# 1. WaitForStart: QR 데이터 수신 -> blackboard 저장 -> 다음으로 진행
# ---------------------------------------------------------
class WaitForQR(SyncAction):
    def __init__(self, name, agent):
        super().__init__(name, self._tick)
        self.agent = agent
        self.received_msg = None
        self.done = False

        self.sub = agent.ros_bridge.node.create_subscription(
            String, "/hospital/qr_login", self._callback, 10
        )
        self.home_saved = False

    def _callback(self, msg):
        self.received_msg = msg
        print("[WaitForQR] QR 데이터 수신됨!")

    def _tick(self, agent, bb):
        if self.done:
            return Status.SUCCESS

        if not self.home_saved:
            if hasattr(agent, 'robot_pose') and agent.robot_pose is not None:
                bb['home_pose'] = agent.robot_pose
                self.home_saved = True

        if self.received_msg is None:
            return Status.RUNNING

        try:
            data = json.loads(self.received_msg.data)

            bb['patient_id'] = data.get("patient_id", "Unknown")

            # ✅ QR에 departments가 없으면 default 사용
            raw_depts = data.get("departments", None)
            if not raw_depts:  # None or [] or ""
                raw_depts = DEFAULT_DEPARTMENTS

            # ✅ 유효한 과만 남김
            depts = [d for d in raw_depts if d in DEPARTMENT_COORDINATES]

            bb['department_queue'] = list(depts) 
            bb['remaining_depts']  = list(depts)

            # 말하기
            bb['speak_text'] = "접수가 완료되었습니다. 이동을 시작할게요."

            print(f"[WaitForQR] 환자: {bb['patient_id']}")
            print(f"[WaitForQR] 기본/QR 과 목록: {raw_depts}")
            print(f"[WaitForQR] 유효 과 목록: {bb['remaining_depts']}")

            self.received_msg = None
            self.done = True
            return Status.SUCCESS

        except Exception as e:
            print("[WaitForQR] parse fail:", e)
            self.received_msg = None
            return Status.RUNNING



        
# ---------------------------------------------------------
# [추가] Condition Nodes: 상태 체크용 노드
# ---------------------------------------------------------
class IsEmergencyPressed(ConditionWithROSTopics):
    # def __init__(self, name, agent, **kwargs):
    #     super().__init__(name, agent, [(Bool, "/emergency_stop", "emergency_flag")], **kwargs)

    # async def run(self, agent, bb):
    #     # 메시지 없으면 "안 눌림"으로 처리 → FAILURE
    #     if "emergency_flag" not in self._cache:
    #         self.status = Status.FAILURE
    #         return self.status

    #     is_pressed = self._cache["emergency_flag"].data
    #     self.status = Status.SUCCESS if is_pressed else Status.FAILURE
    #     # 눌림은 계속 유지될 수 있으니 clear는 선택 (원하면 clear 해도 됨)
    #     return self.status

        
    #    return False # 비상 상황 아님
    def __init__(self, name, agent, **kwargs):
        # [수정] 토픽 이름을 '/emergency_stop' -> '/emergency_trigger'로 변경
        super().__init__(name, agent, [(Bool, "/emergency_trigger", "emergency_flag")], **kwargs)

    async def run(self, agent, bb):
        if "emergency_flag" not in self._cache:
            self.status = Status.FAILURE
            return self.status

        is_pressed = self._cache["emergency_flag"].data
        # 눌렸으면 SUCCESS (ReactiveFallback이 감지)
        self.status = Status.SUCCESS if is_pressed else Status.FAILURE
        return self.status

class IsBatteryLow(ConditionWithROSTopics):
    """
    배터리가 부족한지 확인하는 노드
    토픽: /battery_status (가정, 로봇에 맞게 수정 필요)
    여기서는 테스트를 위해 /battery_low (Bool) 토픽을 구독한다고 가정
    """
    def __init__(self, name, agent):
        super().__init__(name, agent, [
            (Bool, "/battery_low", "battery_flag")
        ])

    def _predicate(self, agent, bb):
        if "battery_flag" in self._cache:
            is_low = self._cache["battery_flag"].data
            if is_low:
                print("[Battery] 배터리 부족 감지!")
                return True
        return False
# ---------------------------------------------------------
# 2. Think: 다음 목적지 결정 (Iterator 역할)
# ---------------------------------------------------------
class Think(SyncAction):
    def __init__(self, name, agent):
        super().__init__(name, self._tick)
        self.wait_min = 0
        self.wait_max = 20

    def _tick(self, agent, bb):
        remaining = bb.get('remaining_depts', [])
        if remaining is None:
            remaining = []

        print("[Think DEBUG] remaining_depts =", remaining)

        # 더 이상 갈 과가 없으면 루프 종료
        if len(remaining) == 0:
            print("[Think] 모든 진료과 방문 완료.")
            return Status.FAILURE

        # ✅ 출발할 때마다 대기인원 랜덤 생성
        waiting_counts = {d: random.randint(self.wait_min, self.wait_max) for d in remaining}

        # ✅ 최소 대기인원 과 선택 (동점이면 랜덤)
        min_wait = min(waiting_counts.values())
        candidates = [d for d, w in waiting_counts.items() if w == min_wait]
        next_dept = random.choice(candidates)

        coords = DEPARTMENT_COORDINATES.get(next_dept)
        if not coords:
            print(f"[Think] 좌표 없음: {next_dept}")
            # 좌표 없는 항목 제거하고 다음 tick에 다시 고르게
            remaining.remove(next_dept)
            bb['remaining_depts'] = remaining
            return Status.RUNNING

        # ✅ 목표 세팅
        bb['current_target_name'] = next_dept
        bb['current_target_coords'] = coords

        # ✅ 방문 처리(다음 선택에서 제외)
        remaining.remove(next_dept)
        bb['remaining_depts'] = remaining

        # ✅ Think 다음 SpeakAction이 말할 멘트 세팅
        bb['speak_text'] = f"{next_dept}로 이동할게요. 대기인원 {waiting_counts[next_dept]}명."

        print(f"[Think] 후보 대기: {waiting_counts}")
        print(f"[Think] 선택: {next_dept} (wait={waiting_counts[next_dept]})")
        return Status.SUCCESS



# ---------------------------------------------------------
# 3. Move: Nav2 Action을 이용한 이동
# ---------------------------------------------------------
class Move(ActionWithROSAction):
    """
    blackboard['current_target_coords']로 이동 (Nav2 NavigateToPose)
    """
    
    def __init__(self, name, agent):
        ns = agent.ros_namespace or ""
        # Nav2의 기본 액션 토픽: /navigate_to_pose
        super().__init__(name, agent, (NavigateToPose, '/navigate_to_pose'))


    def _build_goal(self, agent, bb):
        coords = bb.get('current_target_coords')
        if not coords:
            return None # 목표가 없으면 실행 안 함

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.ros.node.get_clock().now().to_msg()
        
        goal.pose.pose.position.x = float(coords['x'])
        goal.pose.pose.position.y = float(coords['y'])
        goal.pose.pose.orientation.w = 1.0 # 회전은 일단 정면 보기
        
        print(f"[Move] {bb.get('current_target_name')}로 이동 시작...")
        return goal

    def _interpret_result(self, result, agent, bb, status_code=None):
        if status_code == GoalStatus.STATUS_SUCCEEDED:
            print("[Move] 목적지 도착 완료.")
            bb['speak_text'] = f"{bb.get('current_target_name', '목적지')}에 도착했습니다."
            return Status.SUCCESS
        else:
            print(f"[Move] 이동 실패 또는 취소됨 (Status: {status_code})")
            bb['speak_text'] = f"{bb.get('current_target_name', '목적지')}로 이동에 실패 또는 취소됬습니다."
            return Status.FAILURE

# ---------------------------------------------------------
# 4. Doctor: 의료진 대시보드 입력 대기
# ---------------------------------------------------------
class WaitDoctorDone(SyncAction):
    def __init__(self, name, agent):
        super().__init__(name, self._tick)
        self._done = False
        self.sub = agent.ros_bridge.node.create_subscription(
            Bool, "/hospital/doctor_input", self._cb, 10
        )

    def _cb(self, msg: Bool):
        if msg.data is True:
            self._done = True

    def _tick(self, agent, bb):
        if not self._done:
            return Status.RUNNING

        self._done = False  # 다음 과를 위해 리셋
        bb['speak_text'] = "다음 진료과로 이동할게요."
        return Status.SUCCESS


# ---------------------------------------------------------
# 5. Return: 초기 위치로 복귀
# ---------------------------------------------------------
class ReturnHome(ActionWithROSAction):
    """
    블랙보드['home_pose']로 이동
    bb['home_pose']로 이동
    """
    def __init__(self, name, agent):
        super().__init__(name, agent, (NavigateToPose, 'navigate_to_pose'))

    def _build_goal(self, agent, bb):
        home_pose = bb.get('home_pose')
        if not home_pose:
            # 홈 위치가 없으면 (0,0)으로
            home_pose = PoseStamped()
            home_pose.pose.position.x = 0.0
            home_pose.pose.position.y = 0.0
            home_pose.pose.orientation.w = 1.0
        
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.ros.node.get_clock().now().to_msg()
        # 저장된 home_pose가 Pose 객체일 수 있으므로 상황에 맞게 매핑
        goal.pose.pose = home_pose if hasattr(home_pose, 'position') else home_pose.pose

        print("[Return] 모든 일정을 마치고 초기 위치로 복귀합니다.")
        return goal

    def _interpret_result(self, result, agent, bb, status_code=None):
        if status_code == GoalStatus.STATUS_SUCCEEDED:
            return Status.SUCCESS
        return Status.FAILURE


class KeepRunningUntilFailure(Node):
    def __init__(self, name, children=None):
        super().__init__(name)
        self.children = children if children is not None else []

    # 중요: 비동기(async) 실행 함수로 만들어야 함
    async def run(self, agent, bb):
        if not self.children:
            return Status.FAILURE
            
        # 자식 노드의 run 함수를 비동기로 기다림 (await)
        status = await self.children[0].run(agent, bb)
        
        # 자식이 실패하면 -> 루프 종료 (나도 실패 반환)
        if status == Status.FAILURE:
            return Status.FAILURE
            
        # 자식이 성공했거나 실행 중이면 -> 나는 계속 실행 중(RUNNING) -> 다시 실행됨
        return Status.RUNNING

# ---------------------------------------------------------
# 6. SpeakAction: TTS 액션 노드
# ---------------------------------------------------------
class SpeakAction(ActionWithROSAction):
    def __init__(self, name, agent):
        super().__init__(name, agent, (speakActionMsg, 'speak_text'))

    def _build_goal(self, agent, bb):
        text_to_speak = bb.pop('speak_text', None)

        # ✅ 말할 내용 없으면 goal을 만들지 않음 (베이스에서 SUCCESS로 처리하게 해둠)
        if not text_to_speak:
            return None

        goal = speakActionMsg.Goal()
        goal.text = text_to_speak
        print(f"[Speak] TTS 요청: {text_to_speak}")
        return goal

   



# ---------------------------------------------------------
# 7. MonitorSpeed: 로봇 속도 모니터링 조건 노드
# ---------------------------------------------------------
class WaitSpeedOK(SyncAction):
    def __init__(self, name, agent):
        super().__init__(name, self._tick)
        self.limit = 0.8
        self._odom = None
        self._warned = False
        self.sub = agent.ros_bridge.node.create_subscription(
            Odometry, "/odom", self._cb, 10
        )

    def _cb(self, msg: Odometry):
        self._odom = msg

    def _tick(self, agent, bb):
        if self._odom is None:
            return Status.SUCCESS

        v = abs(self._odom.twist.twist.linear.x)
        if v > self.limit:
            if not self._warned:
                bb['speak_text'] = f"속도가 빨라요. {self.limit} 이하로 부탁해."
                self._warned = True
            return Status.SUCCESS   # ✅ Move 막지 않음

        self._warned = False
        return Status.SUCCESS



class SetAbort(SyncAction):
    def __init__(self, name, agent):
        super().__init__(name, self._tick)

    def _tick(self, agent, bb):
        bb['abort'] = True
        bb['speak_text'] = "비상 호출이 감지됐어. 지금 복귀할게."
        return Status.SUCCESS


class CheckAbort(SyncAction):
    def __init__(self, name, agent):
        super().__init__(name, self._tick)

    def _tick(self, agent, bb):
        if bb.get('abort', False):
            # 루프 깨기용 FAILURE
            return Status.FAILURE
        return Status.SUCCESS


class SendDiagnosisEmail(SyncAction):
    """
    BT에서 '메일 보내라' 요청을 publish만 하는 노드
    - topic: /hospital/send_diagnosis_email (String JSON)
    """
    def __init__(self, name, agent, topic="/hospital/send_diagnosis_email", **kwargs):
        super().__init__(name, self._tick, **kwargs)
        self.ros = agent.ros_bridge
        self.pub = self.ros.node.create_publisher(String, topic, 10)
        self.topic = topic

    def _tick(self, agent, bb):
        payload = {
            "patient_id": bb.get("patient_id", "Unknown"),
            "email": bb.get("patient_email") or bb.get("email"),
            "request": "send_diagnosis_email"
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.pub.publish(msg)

        print(f"[SendDiagnosisEmail] published -> {self.topic}: {msg.data}")
        return Status.SUCCESS

# ---------------------------------------------------------
# 노드 등록 (수정본)
# ---------------------------------------------------------

CUSTOM_ACTION_NODES = [
    'WaitForQR',
    'SpeakAction',
    'Think',
    'WaitSpeedOK',
    'Move',
    'WaitDoctorDone',
    'ReturnHome',
    'GoToInfoDesk',
    'SendDiagnosisEmail',
    'SetAbort',
    'CheckAbort',
]

CUSTOM_CONDITION_NODES = [
    'IsEmergencyPressed',
    'IsBatteryLow',
]

BTNodeList.ACTION_NODES.extend(CUSTOM_ACTION_NODES)
BTNodeList.CONDITION_NODES.extend(CUSTOM_CONDITION_NODES)
BTNodeList.CONTROL_NODES.append('KeepRunningUntilFailure')
# ReactiveFallback/ReactiveSequence는 이미 base에 있으면 추가 불필요


print(f"Registered Actions: {BTNodeList.ACTION_NODES}")
print(f"Registered Conditions: {BTNodeList.CONDITION_NODES}")
import time
import json
import random
import threading

import streamlit as st

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

TOPIC_NAME = "/hospital/waiting_board"
REFRESH_SEC = 5  # ✅ 5초마다 갱신

# ✅ 너희 학과 사람들 이름
MAJOR_NAMES = [
    "김원경", "깅미주", "권오준", "김민석", "박성현", "박찬서", "백승훈", "변민석", "성민재", "손민근",
    "손민주", "심소진", "안진우", "유종민", "유동오", "윤여원", "이재우", "장동민", "장호진", "정재민",
    "천재용", "최길웅", "최승준", "편승현", "한준태", "황민"
]

# ✅ 전광판에 표시할 진료과(로봇 DEPARTMENT_COORDINATES 키와 동일)
DEPTS = ["진단검사의학과", "영상의학과", "내과", "정형외과", "신경과"]


class WaitingBoardPub(Node):
    def __init__(self):
        super().__init__("waiting_board_ui_pub")
        self.pub = self.create_publisher(String, TOPIC_NAME, 10)

    def publish_board(self, dept_wait: dict, dept_queue: dict):
        payload = {
            "ts": int(time.time()),
            "dept_wait": dept_wait,
            "dept_queue": dept_queue,
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.pub.publish(msg)


@st.cache_resource
def init_ros_node():
    # ✅ Streamlit rerun이 반복돼도 ROS init 1회만 되게 cache_resource 사용
    rclpy.init(args=None)
    node = WaitingBoardPub()

    # ✅ Streamlit 멈추지 않도록 spin은 별도 스레드
    def spin():
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)

    threading.Thread(target=spin, daemon=True).start()
    return node


def make_random_board(names, depts, max_wait=12):
    # 과별 대기인원 랜덤 생성
    dept_wait = {d: random.randint(0, max_wait) for d in depts}

    # 이름 랜덤 배치
    pool = names[:]
    random.shuffle(pool)

    dept_queue = {}
    idx = 0
    for d in depts:
        n = dept_wait[d]
        dept_queue[d] = pool[idx:idx+n]
        idx += n

        # 이름 부족하면 다시 채우기(데모용)
        if idx + max_wait >= len(pool):
            pool = names[:]
            random.shuffle(pool)
            idx = 0

    return dept_wait, dept_queue


# ---------------- UI ----------------
st.set_page_config(page_title="병원 대기 현황", layout="wide")
st.title("🏥 실시간 진료 대기 현황 (데모 전광판)")

node = init_ros_node()

left, right = st.columns([1, 2])

with left:
    st.subheader("설정")
    max_wait = st.slider("최대 대기인원", 5, 30, 12)
    st.write(f"⏱️ {REFRESH_SEC}초마다 자동으로 인원수/이름 재배치 + ROS 토픽 발행")
    st.caption(f"ROS Topic: `{TOPIC_NAME}`")

    # ✅ Streamlit 자동 새로고침(가능한 경우)
    try:
        st.autorefresh(interval=REFRESH_SEC * 1000, key="waiting_refresh")
    except Exception:
        # 구버전은 아래에서 time.sleep + rerun으로 처리
        pass

with right:
    # 세션 상태 초기화
    if "dept_wait" not in st.session_state:
        st.session_state.dept_wait, st.session_state.dept_queue = make_random_board(MAJOR_NAMES, DEPTS, max_wait)
        st.session_state.last_update_ts = 0

    # 수동 새로고침
    if st.button("🔄 지금 즉시 새로 뽑기(랜덤)"):
        st.session_state.dept_wait, st.session_state.dept_queue = make_random_board(MAJOR_NAMES, DEPTS, max_wait)
        st.session_state.last_update_ts = time.time()

    # ✅ 5초마다 자동 갱신 (autorefresh 유무와 상관없이 안정적으로 동작)
    now = time.time()
    last = st.session_state.get("last_update_ts", 0)
    if now - last >= REFRESH_SEC:
        st.session_state.dept_wait, st.session_state.dept_queue = make_random_board(MAJOR_NAMES, DEPTS, max_wait)
        st.session_state.last_update_ts = now

    # 전광판 출력
    cols = st.columns(len(DEPTS))
    for i, d in enumerate(DEPTS):
        with cols[i]:
            st.metric(label=d, value=f"{st.session_state.dept_wait[d]}명 대기")
            st.write("대기자")
            st.write(st.session_state.dept_queue[d] if st.session_state.dept_wait[d] > 0 else ["없음"])

# ✅ 매 렌더마다 publish (실시간처럼 계속 쏴줌)
node.publish_board(st.session_state.dept_wait, st.session_state.dept_queue)

st.caption("※ 이 화면의 대기 현황은 ROS2 토픽으로 계속 발행되며, 로봇은 이를 구독해 이동 결정을 합니다.")

# ✅ st.autorefresh가 없는 구버전 Streamlit 폴백
if not hasattr(st, "autorefresh"):
    time.sleep(REFRESH_SEC)
    st.rerun()

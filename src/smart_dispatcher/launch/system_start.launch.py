import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    # =========================================================
    # [사진 기반 경로 설정]
    nav_launch_pkg = 'wego'
    map_pkg = 'wego_2d_nav'
    map_file_name = 'map_1764225427.yaml' 
    # =========================================================

    map_dir = os.path.join(
        get_package_share_directory(map_pkg),
        'maps',
        map_file_name
    )

    # 1. 네비게이션 실행 (Nav2)
    wego_nav_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(nav_launch_pkg), 'launch', 'navigation_diff_launch.py')
        ),
        launch_arguments={'map': map_dir}.items()
    )

    # 2. [수정] 로봇 두뇌 (Smart Dispatcher) - 주석 처리하여 실행 방지!
    # (이게 켜져 있으면 QR 없이 혼자 돌아다닙니다)
    """
    dispatcher_node = TimerAction(
        period=5.0,
        actions=[
            Node(
                package='smart_dispatcher',
                executable='dispatcher',
                name='smart_dispatcher',
                output='screen'
            )
        ]
    )
    """

    # 3. 팀원 UI (Patient UI)
    ui_node = TimerAction(
        period=8.0,
        actions=[
            Node(
                package='smart_hospital_system',
                executable='patient_ui', 
                name='patient_ui_node',
                output='screen'
            )
        ]
    )

    return LaunchDescription([
        wego_nav_launch,
        # dispatcher_node, # <--- 여기도 주석 처리 필수!
        ui_node
    ])
import json
import os

def main():
    print("========================================")
    print("      🏥 병원 로봇 초기 설정 마법사      ")
    print("========================================")
    print("우리 병원에서 운영 중인 과를 선택해주세요.")
    print("----------------------------------------")

    # 전체 지원 가능한 과 목록 (마스터 리스트)
    master_list = ["진단검사의학과", "영상의학과", "내과", "정형외과", "신경과"]
    
    selected_depts = []

    # 사용자 입력 받기
    for dept in master_list:
        while True:
            response = input(f"✅ '{dept}'가 있습니까? (y/n): ").lower()
            if response == 'y':
                selected_depts.append(dept)
                break
            elif response == 'n':
                break
            else:
                print("y 또는 n만 입력해주세요.")

    if not selected_depts:
        print("\n⚠️ 선택된 과가 없습니다. 설정을 종료합니다.")
        return

    # 설정 파일 저장 (JSON 형식)
    # 저장 위치: 유저 홈 디렉토리 (~/hospital_config.json)
    config_path = os.path.expanduser('~/hospital_config.json')
    
    config_data = {
        "hospital_name": "My Smart Hospital",
        "active_departments": selected_depts
    }

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)

    print("\n========================================")
    print(f"💾 설정이 저장되었습니다: {config_path}")
    print(f"선택된 과: {', '.join(selected_depts)}")
    print("이제 로봇을 재시작하면 이 설정대로 움직입니다.")
    print("========================================")

if __name__ == '__main__':
    main()
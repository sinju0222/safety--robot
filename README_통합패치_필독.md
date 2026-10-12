# TurtleBot – 실제 SLAM 지도 + Nav2 + 변화탐지 + 웹 통합 패치

**대상 원본:** 사용자가 첨부한 `safety--robot-main(1).zip` (2026-10-12) 기준.
**원칙:** 최신 팀원 코드를 유지하면서 변경 파일만 적용. 이 패치는 GitHub 자동 업데이트/실기기 테스트를 수행하지 않았습니다.

## 이번 수정 사항

1. `backend/websocket_server.py` : `send_map(websocket, workplace_id)`와 실제 `/api/telemetry/map` 저장 위치(`robot_data/{workplace_id}`) 일치. 임의 데모 지도는 전송하지 않음.
2. `backend/telemetry_api.py` : ROS OccupancyGrid/TF 위치 저장, 지도 메타데이터 조회(`GET /api/telemetry/map-meta?workplace_id=N`), 5초 이내 위치 조회.
3. `frontend/src/PixelGridMap.jsx` : 기존 OccupancyGrid 색상 유지(점유=검정, 자유=흰색, 미지=회색). 비율 유지 자동 화면 맞춤, 구역 오버레이, 최근 로봇 위치(파란 점), 미확인 AI 위험(빨간 느낌표), 관리자 확인 버튼. 실시간 WebSocket 재연결.
4. `frontend/src/pages/WorkplaceMain.jsx` : 고정 744×660, 124×110 구역 오버레이를 제거하고 실제 지도 크기에 맞추어 표시. **3초 뒤 강제 원점복귀 완료 처리 삭제**.
5. `frontend/src/pages/MapZoneSetup.jsx`, `MapObjectSetup.jsx` : 작업장별 실측 지도 메타데이터를 읽어 구역/물체 표시 좌표를 일치시킴. 지도 수신 전에는 편집 대기.
6. `backend/main.py` : 지도 격자 좌표로 지정된 구역과 ROS2 미터 좌표 간 변환(원점 및 회전 포함). 로봇 위치 조회 호환 API. 실제 업로드된 /map 없으면 `scan-complete` 거절. 이전 **가짜 기준 물체 3개 자동 삽입 삭제**. 순찰 제어기 주소 및 토큰 연결.
7. `frontend/src/App.jsx` : 기존의 **2.5초 뒤 맵핑 완료** 대신 실제 `/map`이 업로드될 때까지 대기(최대 120초). 물리적으로 맵핑을 완료/저장한 뒤 웹에서 `실제 로봇 지도 불러오기`를 눌러야 함.
8. `backend/robot_event_api.py` : `baseline_image`와 `current_image` AI 분석은 웹 요청과 분리된 스레드에서 실행. 분석에서 `hazard_present=true` 이고 `risk_level=MEDIUM/HIGH`인 경우에만 빨간 느낌표 추가. 오류는 기록하되 안전으로 '확정'하지 않음. 관리자 확인 후 기록 유지.
9. `ros2/robot_change_detector/main.py` : /map 갱신 전송, 지속적인 위치 전송, 초기 BASELINE 순찰 사진 저장 모드 변경 검출.
10. `ros2/robot_change_detector/server_sender.py` : VLM 응답이 최대 60초 걸리는 경우를 위해 HTTP 업로드 대기시간을 90초로 설정.
11. `ros2/robot_change_detector/patrol_controller.py` : 기준 사진/순찰 상태 공유 경로를 탐지 노드와 동일하게 설정. Nav2가 실제로 원점 복귀에 성공했을 때만 완료 알림. 로봇에 이동명령을 보내는 HTTP 엔드포인트에 공유 토큰 요구.
12. `scripts/run_web.ps1`, `scripts/run_robot.sh` : 부가 실행 보조 스크립트. 로봇 드라이버/SLAM/Nav2를 자동 설치·실행하지 않음 (팀원 환경별 명령이 다름).
13. `tests/test_robot_web_link.py` : 지도 업로드 / WebSocket / 구역 좌표 변환 / AI 경고 / ACK / AI 장애 정적 통합 테스트.

## 적용 – 변경 파일만 복사

1. Windows에서 팀원 최신 커밋과 내 로컬 버전 일치 여부 확인: `git status`, `git pull origin main`.
2. 백업 브랜치 생성: `git switch -c fix/integrated-robot-web`.
3. 이 패치 ZIP의 파일들을 **저장소 최상위**의 동일한 위치에 복사. 기존 팀원의 새로운 변경사항이 더 있다면 우선 diff 후 병합.
4. Windows에서 `python -m compileall -q backend`, Ubuntu에서 `python3 -m compileall -q ros2/robot_change_detector`.
5. `python -m pytest -q tests/test_robot_web_link.py` (필요: fastapi, requests, numpy, python-multipart, httpx, pytest).
6. Windows: `cd frontend`, `npm ci`, `npm run build`. 인터넷이 되는 컴퓨터에서 실행.
7. `git diff --check` → `git status` → 원하는 수정만 `git add <파일들>` → `git commit`, `git push`. **전체 `git add .`는 피하기.**
8. Ubuntu ROS 장비에서도 변경이 올라간 후 `git pull origin main` 및 `colcon build` 필요.

## Windows 웹 컴퓨터 – 최초 1회 설치

PowerShell에서 저장소 루트 기준:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..\ai_server
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# .env의 OPENROUTER_API_KEY에 팀에서 발급받은 실제 키 입력 (GitHub에 업로드 금지)
cd ..\frontend
npm ci
cd ..
```

**위험 판정 선택:** 기본은 팀원 코드의 `VLM` 이미지쌍 분석(`-RiskMode vlm`)입니다. 최초 요구대로 **YOLO 객체 + 관리자가 정한 구역 정책**을 기준으로 하려면 `-RiskMode yolo_policy`를 추가하세요. 이 모드에서 YOLO가 인식한 클래스와 해당 구역의 금지정책이 맞는 경우만 경고로 올리며 VLM 서버/API 키는 필요하지 않습니다. YOLO 결과가 LiDAR 변화 물체와 실제로 일치하는지 확정할 수 없으므로 관리자 확인을 권합니다.

VLM 모드에서 AI 서버(8001)의 OpenRouter 키가 **없을 경우** 지도·로봇 위치·사진 저장은 가능하지만 위험 판정 오류가 기록되고 빨간 느낌표가 생기지 않습니다. **위험 경고가 0건이어도 안전을 증명하지 않습니다.**

## Ubuntu ROS 컴퓨터 – 필수 조건

- ROS2 Jazzy가 있고 팀원 기존 드라이버, SLAM 또는 Nav2 map_server, TF/AMCL, RealSense 드라이버가 시작되어 있어야 함.
- `/map`, `/scan`, `/tf`, `/camera/camera/color/image_raw` 확인. 실제 로봇의 `/map`과 웹의 지도는 같은 좌표계·맵 ID여야 함.
- ROS2 노드 두 개(`robot_change_detector`, `patrol_controller`)는 **동일 Ubuntu 계정**에서 실행하여 `~/robot_change_output`을 공유.
- Ubuntu PC와 로봇 Raspberry Pi가 ROS2 DDS 토픽을 서로 볼 수 있도록 같은 `ROS_DOMAIN_ID`, 네트워크 설정 확인.

첫 설치 예시 (기존 ROS2 workspace가 `~/ros2_ws`인 경우):

```bash
source /opt/ros/jazzy/setup.bash
cd ~/ros2_ws/src/safety--robot
git pull origin main
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select robot_change_detector
source install/setup.bash
# 실행에 쓰는 Python 환경에 requests/numpy/cv_bridge/ultralytics/torch 등 필요.
# ultralytics, torch는 Ubuntu 기기의 아키텍처·Python 환경에 따라 별도 설치가 필요함.
```

## 두 PC 실행 (매번)

**A. Windows PC IP 확인:** PowerShell `ipconfig`의 현재 Wi-Fi IPv4. Ubuntu IP 확인: `hostname -I`.

**B. Windows:** `scripts/run_web.ps1` 호출. 양쪽 PC에 동일한 **충분히 긴 임의의 공유 토큰** 사용. 아래 모든 IP와 토큰은 예시입니다.

```powershell
cd C:\Users\93021\safety--robot
powershell -ExecutionPolicy Bypass -File .\scripts\run_web.ps1 -UbuntuIP 192.168.0.25 -PatrolToken MY_LONG_RANDOM_TOKEN_12345 -RiskMode yolo_policy
```

실행 스크립트가 **FastAPI 8000, React 5173**, `ai_server/.env`와 venv가 구성됐다면 **AI 8001**을 별도 PowerShell 창으로 실행함. `-RiskMode yolo_policy`는 VLM 서버 없이 YOLO/안전정책 기반 시연용이며, `-RiskMode vlm`(기본값)은 팀원 최신 VLM 판정을 보존함. 포트 충돌 시 기존 프로세스 종료 후 실행.

**C. Ubuntu:** (팀원 기존 방식대로 Raspberry Pi/센서/SLAM 또는 Nav2 및 AMCL을 먼저 정상 실행)

```bash
cd ~/ros2_ws/src/safety--robot
export SAFETY_BACKEND_URL=http://192.168.0.15:8000   # 실제 Windows IP
export SAFETY_WORKPLACE_ID=1                          # 웹의 실제 작업장 ID
export SAFETY_PATROL_TOKEN=MY_LONG_RANDOM_TOKEN_12345 # Windows와 동일
source /opt/ros/jazzy/setup.bash
export SAFETY_ROS_WORKSPACE=$HOME/ros2_ws
bash scripts/run_robot.sh
```

Windows와 Ubuntu **같은 Wi-Fi**여야 하며 방화벽에서 Windows 8000, Ubuntu 8090의 로컬 사설망 접속을 허용해야 함. 포트를 인터넷으로 개방하면 안 됨. 사용자 계정 인증 및 권한 관리는 아직 데모 단계.

**D. 브라우저** `http://localhost:5173` 접속 → 로봇과 연결할 작업장 선택 → 완성된 `/map`이 이미 업로드된 후 웹에서 `실제 로봇 지도 불러오기` 클릭 → 구역 편집 → 필요 시 사물 설정 → 지도 완성 → 순찰 경로를 실제 **map 좌표계의 미터**로 등록 → 순찰 시작.

**E. 상태 확인:** Windows `http://127.0.0.1:8000/health`, `http://127.0.0.1:8000/api/telemetry/map-meta?workplace_id=1` 및 `/api/telemetry/pose?workplace_id=1`, AI 서버 `http://127.0.0.1:8001/health`. Ubuntu에서 `curl http://<WINDOWS_IP>:8000/health`.

## 주의·한계 (실기기에서만 검증 가능)

- 실제 SLAM 지도 크기가 이전 124×110과 달라진 경우 **기존에 그린 구역은 새 지도에서 다시 설정**해야 함. 이전 구역 좌표를 자동 재해석하지 않음.
- 로봇의 안전한 자율주행은 Nav2/AMCL/로봇 드라이버에 의존. 이동 전 사람·장애물 없는 시험 공간, 긴급정지 확보. 프로그램 수정본은 로봇 주행 안전을 인증하지 않음.
- 위험 판정은 `SAFETY_RISK_MODE=vlm`(팀원 VLM 이미지쌍 분석) 또는 `SAFETY_RISK_MODE=yolo_policy`(YOLO 인식 + 구역별 정책) 선택 가능. 두 방식 모두 영상으로 인식된 물체가 LiDAR 변화 위치와 실제로 일치하는지 확정할 수 없으므로 위험 경고는 관리자 검토가 필요함.
- VLM 분석이 실패해도 사진과 분석 오류는 저장함. **빨간 마커가 없다는 사실은 안전하다는 뜻이 아님.**
- MapZoneSetup과 MapObjectSetup은 실제 지도 업로드가 선행돼야 함. 맵핑 버튼이 SLAM 드라이버를 자동 실행하지는 않음.
- 원점 복귀는 Nav2가 SUCCEEDED일 때만 완료로 기록; 실패하면 수동 조치 필요.
- 패치 내부 Python 통합/문법 테스트는 통과했지만, 이 실행 환경에 npm 모듈/ROS2/로봇이 없어서 React `npm run build` 및 실기기 통합 시험을 완료하지 못함.
- 첫 기준사진 수집(Baseline Patrol)과 YOLO 모델 사용 여부는 실제 ROS2/카메라/모델 환경에서 확인 필요.
- API 서버는 학습/시연용으로 관리자 로그인 인증이 아직 없어 사설망 외부에 공개하면 안 됨.

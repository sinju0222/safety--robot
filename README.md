AI·로봇 안전제어 솔루션

프로젝트 목적

작업장을 순찰하는 로봇이 LiDAR 및 RGB-D 카메라를 통해 환경 데이터를 수집하고, 기존 환경과의 변화를 탐지하여 위험도를 분석하는 안전제어 솔루션을 개발합니다.

탐지된 환경 변화와 위험도를 기반으로 Safety Policy를 자동 생성·갱신하고, 생성된 정책을 협동로봇·AMR·AGV 등 다양한 로봇 시스템의 안전 제어에 활용하는 것을 목표로 합니다.

핵심 기능

* LiDAR / RGB-D 기반 작업장 환경 데이터 수집
* 기존 환경과 현재 환경 비교 및 변화 탐지
* 환경 변화에 따른 위험도 계산
* 위험도 기반 Safety Policy 생성 및 갱신
* 로봇 제어 시스템과 Safety Policy 연동
* 위험 이벤트 및 안전정책 저장
* 안전관리 Dashboard를 통한 이벤트 및 정책 확인

기술 스택

Robot / Sensor

* TurtleBot3 Waffle Pi
* LiDAR
* Intel RealSense RGB-D Camera

Robot Software

* ROS2
* SLAM
* Nav2

Backend

* Python
* FastAPI

Frontend

* React

Database

* PostgreSQL

Collaboration

* Git
* GitHub

시스템 구성

LiDAR / RealSense
        │
        ▼
      ROS2
        │
        ▼
환경 변화 탐지
        │
        ▼
   위험도 계산
        │
        ▼
Safety Policy Engine
     │       │
     ▼       ▼
PostgreSQL  Robot Interface
     │
     ▼
React Dashboard

전체 동작 흐름

작업장 순찰
    ↓
LiDAR / RGB-D 데이터 수집
    ↓
환경 변화 탐지
    ↓
위험도 계산
    ↓
Safety Policy 생성 / 갱신
    ↓
로봇 제어 시스템 전달
    ↓
이벤트 및 정책 저장
    ↓
Dashboard 표시

Repository 구조

safety--robot/
├── backend/       # FastAPI 및 안전제어 로직
├── frontend/      # React 안전관리 Dashboard
├── ros2/          # ROS2 Node 및 로봇 인터페이스
├── database/      # PostgreSQL 관련 파일
├── docs/          # 프로젝트 설계 문서
├── tests/         # 테스트 코드
├── scripts/       # 실행 및 관리 스크립트
├── .gitignore
└── README.md

실행 예정 구조

TurtleBot3 / Sensors
        │
        ▼
      ROS2
        │
        ▼
FastAPI Backend
   │         │
   ▼         ▼
PostgreSQL  React Dashboard

현재 프로젝트는 개발 초기 단계이며, 개발 진행에 따라 각 모듈의 설치 방법, 실행 명령어, 환경변수 설정 및 API 사용 방법을 추가할 예정입니다.

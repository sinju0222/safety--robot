import os
import shutil

import cv2
import numpy as np

from cluster_manager import (
    cluster_points,
    get_center,
)
from change_detector import detect_change
from camera_manager import CameraManager
from yolo_detector import YoloDetector
from event_manager import create_event

from state_machine import (
    DetectionState,
    DetectionStateMachine,
)


TEST_CAPTURE_DIR = "test_e2e_captures"


# ======================================================
# 테스트용 가상 카메라 프레임
# ======================================================

def create_test_frame():
    """
    실제 RealSense 대신 사용할 테스트 이미지.

    YOLO 객체 탐지 정확도를 테스트하는 목적이 아니라
    전체 파이프라인 연결을 확인하기 위한 이미지이다.
    """

    frame = np.zeros(
        (480, 640, 3),
        dtype=np.uint8
    )

    cv2.rectangle(
        frame,
        (220, 140),
        (420, 340),
        (255, 255, 255),
        -1
    )

    return frame


# ======================================================
# 테스트 파일 정리
# ======================================================

def cleanup():

    if os.path.exists(TEST_CAPTURE_DIR):
        shutil.rmtree(TEST_CAPTURE_DIR)


# ======================================================
# LiDAR Scan 처리
# ======================================================

def process_lidar_scan(
    points,
    past_state,
    current_state
):
    """
    가상 LiDAR 변화 Point
        ↓
    Cluster
        ↓
    대표 좌표
        ↓
    Change Detector

    결과 Event 후보 반환
    """

    clusters = cluster_points(points)

    print(
        f"[CLUSTER] "
        f"생성된 클러스터 수: {len(clusters)}"
    )

    events = []

    for index, cluster in enumerate(
        clusters,
        start=1
    ):

        center = get_center(cluster)

        print(
            f"[CLUSTER {index}] "
            f"points={len(cluster)}, "
            f"center={center}"
        )

        change = detect_change(
            position=center,
            past_state=past_state,
            current_state=current_state
        )

        if change is not None:

            print(
                f"[CHANGE] "
                f"{change['event_type']} "
                f"{change['position']}"
            )

            events.append(change)

    return events


# ======================================================
# E2E TEST
# ======================================================

def test_e2e_added_pipeline():

    print("\n================================")
    print("E2E TEST")
    print("ADDED 전체 파이프라인")
    print("================================")

    # --------------------------------------------------
    # 시스템 생성
    # --------------------------------------------------

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    camera = CameraManager(
        save_dir=TEST_CAPTURE_DIR
    )

    yolo = YoloDetector()

    # --------------------------------------------------
    # RealSense 대신 가상 프레임 입력
    # --------------------------------------------------

    camera.update_cv_frame(
        create_test_frame()
    )

    # --------------------------------------------------
    # 연속된 가상 LiDAR Scan
    # --------------------------------------------------

    scans = [
        [
            (5.00, 2.00),
            (5.03, 2.02),
            (4.98, 1.99),
        ],
        [
            (5.04, 2.01),
            (5.02, 2.03),
            (4.99, 2.00),
        ],
        [
            (4.98, 2.02),
            (5.01, 1.99),
            (5.03, 2.01),
        ],
    ]

    confirmed_change = None

    # --------------------------------------------------
    # Scan 처리
    # --------------------------------------------------

    for scan_number, points in enumerate(
        scans,
        start=1
    ):

        print(
            f"\n---------- "
            f"SCAN {scan_number} "
            f"----------"
        )

        changes = process_lidar_scan(
            points=points,
            past_state=0,
            current_state=1
        )

        assert len(changes) == 1

        change = changes[0]

        position = (
            change["position"]["x"],
            change["position"]["y"],
        )

        # 최초 변화
        if (
            machine.get_state()
            == DetectionState.MONITORING
        ):

            machine.start_confirmation(
                position=position,
                event_type=change["event_type"]
            )

        # 확인 중인 변화
        elif (
            machine.get_state()
            == DetectionState.CONFIRMING
        ):

            confirmed = (
                machine.confirm_detection(
                    position=position,
                    event_type=change["event_type"]
                )
            )

            if confirmed:
                confirmed_change = change

    # --------------------------------------------------
    # 변화 확정 확인
    # --------------------------------------------------

    assert (
        machine.get_state()
        == DetectionState.CAPTURING
    )

    assert confirmed_change is not None

    print(
        "\n[E2E] "
        "변화 3회 연속 확인 완료"
    )

    # --------------------------------------------------
    # Camera
    # --------------------------------------------------

    image_path = camera.capture()

    assert image_path is not None
    assert os.path.exists(image_path)

    print(
        f"[CAMERA] "
        f"이미지 저장 완료: {image_path}"
    )

    machine.capture_completed()

    assert (
        machine.get_state()
        == DetectionState.ANALYZING
    )

    # --------------------------------------------------
    # YOLO
    # --------------------------------------------------

    print(
        "[YOLO] 객체 탐지 시작"
    )

    detected_objects = yolo.detect(
        image_path
    )

    assert isinstance(
        detected_objects,
        list
    )

    print(
        f"[YOLO] "
        f"탐지 객체 수: "
        f"{len(detected_objects)}"
    )

    for obj in detected_objects:

        print(
            f"[OBJECT] {obj}"
        )

    machine.analysis_completed()

    assert (
        machine.get_state()
        == DetectionState.PROCESSING
    )

    # --------------------------------------------------
    # Event 생성
    # --------------------------------------------------

    event = create_event(
        confirmed_change,
        detected_objects
    )

    assert event is not None

    assert (
        event["event_type"]
        == "ADDED"
    )

    print("\n================================")
    print("FINAL EVENT")
    print("================================")

    print(event)

    # --------------------------------------------------
    # Processing 완료
    # --------------------------------------------------

    machine.processing_completed()

    assert (
        machine.get_state()
        == DetectionState.MONITORING
    )

    print(
        "\n[E2E] "
        "State = MONITORING"
    )

    print("\n================================")
    print("E2E TEST PASS")
    print("================================")


# ======================================================
# 실행
# ======================================================

if __name__ == "__main__":

    cleanup()

    try:

        test_e2e_added_pipeline()

        print("\n================================")
        print("ALL E2E PIPELINE TESTS PASSED")
        print("================================")

    finally:

        cleanup()
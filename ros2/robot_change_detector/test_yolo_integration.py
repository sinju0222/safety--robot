import os
import shutil

import cv2
import numpy as np

from camera_manager import CameraManager
from yolo_detector import YoloDetector

from state_machine import (
    DetectionState,
    DetectionStateMachine,
)


TEST_CAPTURE_DIR = "test_yolo_captures"


def create_test_frame():
    """
    YOLO 파이프라인 실행을 위한
    테스트 이미지 생성.

    실제 물체 사진이 아니므로
    객체가 탐지되지 않아도 정상이다.
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


def cleanup():

    if os.path.exists(TEST_CAPTURE_DIR):
        shutil.rmtree(TEST_CAPTURE_DIR)


# ======================================================
# TEST 1
# YOLO 단독 실행
# ======================================================

def test_yolo_detection():

    print("\n================================")
    print("TEST 1: YOLO 실행")
    print("================================")

    camera = CameraManager(
        save_dir=TEST_CAPTURE_DIR
    )

    camera.update_cv_frame(
        create_test_frame()
    )

    image_path = camera.capture()

    assert image_path is not None
    assert os.path.exists(image_path)

    print(
        f"[CAMERA] 이미지: {image_path}"
    )

    yolo = YoloDetector()

    objects = yolo.detect(
        image_path
    )

    assert isinstance(
        objects,
        list
    )

    print(
        f"[YOLO] 탐지 객체 수: "
        f"{len(objects)}"
    )

    for obj in objects:
        print(
            f"[OBJECT] {obj}"
        )

    print("\nTEST 1 PASS")


# ======================================================
# TEST 2
# State Machine → Camera → YOLO
# ======================================================

def test_state_camera_yolo():

    print("\n================================")
    print("TEST 2: State → Camera → YOLO")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    camera = CameraManager(
        save_dir=TEST_CAPTURE_DIR
    )

    yolo = YoloDetector()

    # ------------------------------------------
    # 가상 카메라 프레임
    # ------------------------------------------

    camera.update_cv_frame(
        create_test_frame()
    )

    # ------------------------------------------
    # 변화 3회 확인
    # ------------------------------------------

    machine.start_confirmation(
        position=(5.00, 2.00),
        event_type="ADDED"
    )

    machine.confirm_detection(
        position=(5.04, 2.02),
        event_type="ADDED"
    )

    machine.confirm_detection(
        position=(4.98, 2.01),
        event_type="ADDED"
    )

    assert (
        machine.get_state()
        == DetectionState.CAPTURING
    )

    print(
        "[STATE CHECK] CAPTURING"
    )

    # ------------------------------------------
    # 이미지 촬영
    # ------------------------------------------

    image_path = camera.capture()

    assert image_path is not None

    print(
        f"[CAMERA] 저장 완료: "
        f"{image_path}"
    )

    machine.capture_completed()

    assert (
        machine.get_state()
        == DetectionState.ANALYZING
    )

    print(
        "[STATE CHECK] ANALYZING"
    )

    # ------------------------------------------
    # 실제 YOLO 실행
    # ------------------------------------------

    objects = yolo.detect(
        image_path
    )

    assert isinstance(
        objects,
        list
    )

    print(
        f"[YOLO] 탐지 객체 수: "
        f"{len(objects)}"
    )

    for obj in objects:
        print(
            f"[OBJECT] {obj}"
        )

    # ------------------------------------------
    # YOLO 분석 완료
    # ------------------------------------------

    machine.analysis_completed()

    assert (
        machine.get_state()
        == DetectionState.PROCESSING
    )

    print(
        "[STATE CHECK] PROCESSING"
    )

    print("\nTEST 2 PASS")


# ======================================================
# 실행
# ======================================================

if __name__ == "__main__":

    cleanup()

    try:

        test_yolo_detection()

        test_state_camera_yolo()

        print("\n================================")
        print("ALL YOLO INTEGRATION TESTS PASSED")
        print("================================")

    finally:

        cleanup()
        
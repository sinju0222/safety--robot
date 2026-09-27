import os
import shutil

import numpy as np
import cv2

from camera_manager import CameraManager

from state_machine import (
    DetectionState,
    DetectionStateMachine,
)


TEST_CAPTURE_DIR = "test_captures"


def create_test_frame():
    """
    RealSense 대신 사용할 가상 OpenCV 이미지 생성
    """

    frame = np.zeros(
        (480, 640, 3),
        dtype=np.uint8
    )

    # 테스트용 물체 표현
    cv2.rectangle(
        frame,
        (250, 150),
        (390, 330),
        (255, 255, 255),
        -1
    )

    return frame


def cleanup():
    """
    테스트 중 생성된 이미지 제거
    """

    if os.path.exists(TEST_CAPTURE_DIR):
        shutil.rmtree(TEST_CAPTURE_DIR)


# ======================================================
# TEST 1
# 프레임이 없을 때 촬영 실패
# ======================================================

def test_capture_without_frame():

    print("\n================================")
    print("TEST 1: 프레임 없음")
    print("================================")

    camera = CameraManager(
        save_dir=TEST_CAPTURE_DIR
    )

    path = camera.capture()

    assert path is None

    print("[RESULT] 이미지 없음 → 저장하지 않음")
    print("\nTEST 1 PASS")


# ======================================================
# TEST 2
# 가상 이미지 실제 저장
# ======================================================

def test_virtual_frame_capture():

    print("\n================================")
    print("TEST 2: 가상 이미지 촬영")
    print("================================")

    camera = CameraManager(
        save_dir=TEST_CAPTURE_DIR
    )

    # RealSense 대신 가상 프레임 입력
    camera.latest_frame = create_test_frame()

    path = camera.capture()

    print(
        f"[CAPTURE] 저장 경로: {path}"
    )

    assert path is not None
    assert os.path.exists(path)

    image = cv2.imread(path)

    assert image is not None
    assert image.shape == (480, 640, 3)

    print("[RESULT] JPG 파일 생성 확인")

    print("\nTEST 2 PASS")


# ======================================================
# TEST 3
# State Machine → Camera
# ======================================================

def test_state_machine_camera():

    print("\n================================")
    print("TEST 3: State Machine → Camera")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    camera = CameraManager(
        save_dir=TEST_CAPTURE_DIR
    )

    # ------------------------------------------
    # 가상 RealSense 프레임
    # ------------------------------------------

    camera.latest_frame = create_test_frame()

    # ------------------------------------------
    # 동일 변화 3회 발생
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
        "[STATE CHECK] CAPTURING 확인"
    )

    # ------------------------------------------
    # 실제 CameraManager.capture() 실행
    # ------------------------------------------

    image_path = camera.capture()

    assert image_path is not None
    assert os.path.exists(image_path)

    print(
        f"[CAMERA] 이미지 저장 완료: "
        f"{image_path}"
    )

    # ------------------------------------------
    # 촬영 성공 후 상태 전환
    # ------------------------------------------

    machine.capture_completed()

    assert (
        machine.get_state()
        == DetectionState.ANALYZING
    )

    print(
        "[STATE CHECK] ANALYZING 전환 완료"
    )

    print("\nTEST 3 PASS")


# ======================================================
# TEST 4
# 촬영 실패 시 ANALYZING으로 넘어가지 않는지 확인
# ======================================================

def test_capture_failure():

    print("\n================================")
    print("TEST 4: 촬영 실패")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    camera = CameraManager(
        save_dir=TEST_CAPTURE_DIR
    )

    machine.start_confirmation(
        position=(5.0, 2.0),
        event_type="ADDED"
    )

    machine.confirm_detection(
        position=(5.0, 2.0),
        event_type="ADDED"
    )

    machine.confirm_detection(
        position=(5.0, 2.0),
        event_type="ADDED"
    )

    assert (
        machine.get_state()
        == DetectionState.CAPTURING
    )

    # latest_frame이 없으므로 실패
    image_path = camera.capture()

    assert image_path is None

    # capture_completed()를 호출하지 않음
    # 따라서 CAPTURING 상태 유지
    assert (
        machine.get_state()
        == DetectionState.CAPTURING
    )

    print("[CAMERA] 촬영 실패")
    print("[STATE CHECK] CAPTURING 유지")

    print("\nTEST 4 PASS")


# ======================================================
# 전체 실행
# ======================================================

if __name__ == "__main__":

    cleanup()

    try:
        test_capture_without_frame()

        test_virtual_frame_capture()

        test_state_machine_camera()

        test_capture_failure()

        print("\n================================")
        print("ALL CAMERA INTEGRATION TESTS PASSED")
        print("================================")

    finally:
        cleanup()
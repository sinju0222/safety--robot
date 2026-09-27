from change_detector import detect_change
from event_manager import create_event

from state_machine import (
    DetectionState,
    DetectionStateMachine,
)


# ======================================================
# TEST 1
# ADDED 이벤트 생성
# ======================================================

def test_added_event():

    print("\n================================")
    print("TEST 1: ADDED Event 생성")
    print("================================")

    change = detect_change(
        position=(5.0, 2.0),
        past_state=0,
        current_state=1
    )

    assert change is not None
    assert change["event_type"] == "ADDED"

    # YOLO가 물체를 탐지했다고 가정
    detected_objects = [
        {
            "label": "box",
            "confidence": 0.91,
            "bbox": [
                100.0,
                120.0,
                250.0,
                300.0
            ]
        }
    ]

    event = create_event(
        change,
        detected_objects
    )

    print(f"[EVENT] {event}")

    assert event["robot_id"] == "TB3_01"
    assert event["event_type"] == "ADDED"

    assert (
        event["position"]["x"]
        == 5.0
    )

    assert (
        event["position"]["y"]
        == 2.0
    )

    assert event["past_state"] == 0
    assert event["current_state"] == 1

    assert len(event["objects"]) == 1

    assert (
        event["objects"][0]["label"]
        == "box"
    )

    assert "timestamp" in event

    print("\nTEST 1 PASS")


# ======================================================
# TEST 2
# REMOVED 이벤트 생성
# ======================================================

def test_removed_event():

    print("\n================================")
    print("TEST 2: REMOVED Event 생성")
    print("================================")

    past_objects = [
        {
            "label": "pallet",
            "confidence": 0.87
        }
    ]

    change = detect_change(
        position=(3.0, 4.0),
        past_state=1,
        current_state=0,
        past_objects=past_objects
    )

    assert change is not None
    assert change["event_type"] == "REMOVED"

    # REMOVED에서는 YOLO 결과가 아니라
    # 기존 객체 정보를 사용해야 한다.
    event = create_event(
        change,
        detected_objects=[
            {
                "label": "person",
                "confidence": 0.99
            }
        ]
    )

    print(f"[EVENT] {event}")

    assert event["event_type"] == "REMOVED"

    assert (
        event["objects"]
        == past_objects
    )

    assert (
        event["objects"][0]["label"]
        == "pallet"
    )

    print("\nTEST 2 PASS")


# ======================================================
# TEST 3
# State Machine PROCESSING → Event → MONITORING
# ======================================================

def test_processing_flow():

    print("\n================================")
    print("TEST 3: PROCESSING → Event")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    # ------------------------------------------
    # 변화 3회 확인
    # ------------------------------------------

    machine.start_confirmation(
        position=(5.0, 2.0),
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

    # ------------------------------------------
    # 촬영 완료
    # ------------------------------------------

    machine.capture_completed()

    assert (
        machine.get_state()
        == DetectionState.ANALYZING
    )

    # ------------------------------------------
    # YOLO 완료
    # ------------------------------------------

    machine.analysis_completed()

    assert (
        machine.get_state()
        == DetectionState.PROCESSING
    )

    print(
        "[STATE CHECK] PROCESSING"
    )

    # ------------------------------------------
    # 실제 Change 생성
    # ------------------------------------------

    change = detect_change(
        position=(5.0, 2.0),
        past_state=0,
        current_state=1
    )

    detected_objects = [
        {
            "label": "box",
            "confidence": 0.91,
            "bbox": [
                100.0,
                120.0,
                250.0,
                300.0
            ]
        }
    ]

    # ------------------------------------------
    # 실제 Event 생성
    # ------------------------------------------

    event = create_event(
        change,
        detected_objects
    )

    assert event is not None
    assert event["event_type"] == "ADDED"

    print(
        f"[EVENT CREATED] {event}"
    )

    # ------------------------------------------
    # Event 처리 완료
    # ------------------------------------------

    machine.processing_completed()

    assert (
        machine.get_state()
        == DetectionState.MONITORING
    )

    print(
        "[STATE CHECK] MONITORING"
    )

    print("\nTEST 3 PASS")


# ======================================================
# 전체 실행
# ======================================================

if __name__ == "__main__":

    test_added_event()

    test_removed_event()

    test_processing_flow()

    print("\n================================")
    print("ALL EVENT INTEGRATION TESTS PASSED")
    print("================================")
from state_machine import (
    DetectionState,
    DetectionStateMachine,
)


# ======================================================
# TEST 1
# 정상적인 변화 탐지
# ======================================================

def test_normal_flow():

    print("\n================================")
    print("TEST 1: 정상적인 변화 탐지")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    machine.start_confirmation(
        position=(5.0, 2.0),
        event_type="ADDED"
    )

    machine.confirm_detection(
        position=(5.0, 2.0),
        event_type="ADDED"
    )

    confirmed = machine.confirm_detection(
        position=(5.0, 2.0),
        event_type="ADDED"
    )

    assert confirmed is True

    assert (
        machine.get_state()
        == DetectionState.CAPTURING
    )

    machine.capture_completed()

    assert (
        machine.get_state()
        == DetectionState.ANALYZING
    )

    machine.analysis_completed()

    assert (
        machine.get_state()
        == DetectionState.PROCESSING
    )

    machine.processing_completed()

    assert (
        machine.get_state()
        == DetectionState.MONITORING
    )

    print("\nTEST 1 PASS")


# ======================================================
# TEST 2
# 순간적인 LiDAR 노이즈
# ======================================================

def test_noise():

    print("\n================================")
    print("TEST 2: 순간적인 변화")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    # 한 번 변화 발생
    machine.start_confirmation(
        position=(5.0, 2.0),
        event_type="ADDED"
    )

    assert (
        machine.get_state()
        == DetectionState.CONFIRMING
    )

    # 다음 scan에서 변화 사라짐
    machine.cancel_confirmation()

    assert (
        machine.get_state()
        == DetectionState.MONITORING
    )

    assert machine.confirm_count == 0

    print("\nTEST 2 PASS")


# ======================================================
# TEST 3
# 서로 다른 위치의 변화
# ======================================================

def test_different_position():

    print("\n================================")
    print("TEST 3: 서로 다른 위치")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    # 첫 변화
    machine.start_confirmation(
        position=(5.0, 2.0),
        event_type="ADDED"
    )

    # 전혀 다른 위치
    confirmed = machine.confirm_detection(
        position=(8.0, 7.0),
        event_type="ADDED"
    )

    assert confirmed is False

    assert (
        machine.get_state()
        == DetectionState.MONITORING
    )

    print("\nTEST 3 PASS")


# ======================================================
# TEST 4
# 약간씩 다른 좌표지만 동일 물체
# ======================================================

def test_close_positions():

    print("\n================================")
    print("TEST 4: 가까운 좌표 변화")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    # 첫 번째 scan
    machine.start_confirmation(
        position=(5.00, 2.00),
        event_type="ADDED"
    )

    # 두 번째 scan
    confirmed = machine.confirm_detection(
        position=(5.04, 2.02),
        event_type="ADDED"
    )

    assert confirmed is False

    assert (
        machine.get_state()
        == DetectionState.CONFIRMING
    )

    # 세 번째 scan
    confirmed = machine.confirm_detection(
        position=(4.98, 2.01),
        event_type="ADDED"
    )

    assert confirmed is True

    assert (
        machine.get_state()
        == DetectionState.CAPTURING
    )

    print("\nTEST 4 PASS")


# ======================================================
# 전체 테스트 실행
# ======================================================

if __name__ == "__main__":

    test_normal_flow()

    test_noise()

    test_different_position()

    test_close_positions()

    print("\n================================")
    print("ALL STATE MACHINE TESTS PASSED")
    print("================================")
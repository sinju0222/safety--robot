from change_detector import detect_change

from state_machine import (
    DetectionState,
    DetectionStateMachine,
)


def event_to_position(event):
    """
    change_detector가 반환한 event의 position을
    State Machine에서 사용하는 (x, y) 튜플로 변환한다.
    """

    return (
        event["position"]["x"],
        event["position"]["y"],
    )


def test_added_change():
    """
    TEST 1

    기존에는 물체가 없었지만
    현재 물체가 등장한 상황.

    0 -> 1 = ADDED

    같은 위치에서 3회 연속 변화가 감지되면
    State Machine이 CAPTURING 상태로
    전환되는지 확인한다.
    """

    print("\n================================")
    print("INTEGRATION TEST 1")
    print("ADDED 변화")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    # ------------------------------------------
    # 첫 번째 가상 센서 신호
    # ------------------------------------------

    event = detect_change(
        position=(5.00, 2.00),
        past_state=0,
        current_state=1
    )

    assert event is not None
    assert event["event_type"] == "ADDED"

    print("\n[CHANGE DETECTOR]")
    print(event)

    position = event_to_position(event)

    machine.start_confirmation(
        position=position,
        event_type=event["event_type"]
    )

    # ------------------------------------------
    # 두 번째 가상 센서 신호
    # ------------------------------------------

    event = detect_change(
        position=(5.04, 2.02),
        past_state=0,
        current_state=1
    )

    assert event is not None

    print("\n[CHANGE DETECTOR]")
    print(event)

    position = event_to_position(event)

    machine.confirm_detection(
        position=position,
        event_type=event["event_type"]
    )

    # ------------------------------------------
    # 세 번째 가상 센서 신호
    # ------------------------------------------

    event = detect_change(
        position=(4.98, 2.01),
        past_state=0,
        current_state=1
    )

    assert event is not None

    print("\n[CHANGE DETECTOR]")
    print(event)

    position = event_to_position(event)

    confirmed = machine.confirm_detection(
        position=position,
        event_type=event["event_type"]
    )

    # ------------------------------------------
    # 검증
    # ------------------------------------------

    assert confirmed is True

    assert (
        machine.get_state()
        == DetectionState.CAPTURING
    )

    print("\nINTEGRATION TEST 1 PASS")


def test_removed_change():
    """
    TEST 2

    기존 물체가 사라진 상황.

    1 -> 0 = REMOVED

    REMOVED 이벤트도 State Machine에서
    정상적으로 처리되는지 확인한다.
    """

    print("\n================================")
    print("INTEGRATION TEST 2")
    print("REMOVED 변화")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    positions = [
        (3.00, 4.00),
        (3.03, 4.02),
        (2.98, 3.99),
    ]

    for index, position in enumerate(positions):

        event = detect_change(
            position=position,
            past_state=1,
            current_state=0,
            past_objects=[
                {
                    "label": "box",
                    "confidence": 0.90
                }
            ]
        )

        assert event is not None
        assert event["event_type"] == "REMOVED"

        print("\n[CHANGE DETECTOR]")
        print(event)

        event_position = event_to_position(event)

        if index == 0:

            machine.start_confirmation(
                position=event_position,
                event_type=event["event_type"]
            )

        else:

            machine.confirm_detection(
                position=event_position,
                event_type=event["event_type"]
            )

    assert (
        machine.get_state()
        == DetectionState.CAPTURING
    )

    print("\nINTEGRATION TEST 2 PASS")


def test_no_change():
    """
    TEST 3

    과거 상태와 현재 상태가 같으면
    change_detector가 이벤트를 생성하지 않아야 한다.
    """

    print("\n================================")
    print("INTEGRATION TEST 3")
    print("변화 없음")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    event = detect_change(
        position=(5.0, 2.0),
        past_state=0,
        current_state=0
    )

    assert event is None

    assert (
        machine.get_state()
        == DetectionState.MONITORING
    )

    print("\n이벤트 생성 없음")
    print("State = MONITORING")

    print("\nINTEGRATION TEST 3 PASS")


if __name__ == "__main__":

    test_added_change()

    test_removed_change()

    test_no_change()

    print("\n================================")
    print("ALL INTEGRATION TESTS PASSED")
    print("================================")
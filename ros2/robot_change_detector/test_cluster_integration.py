from cluster_manager import (
    cluster_points,
    get_center,
)

from change_detector import detect_change

from state_machine import (
    DetectionState,
    DetectionStateMachine,
)


def event_to_position(event):
    """
    change_detector의 position 딕셔너리를
    State Machine용 (x, y) 튜플로 변환
    """

    return (
        event["position"]["x"],
        event["position"]["y"],
    )


def process_scan(
    points,
    past_state,
    current_state,
):
    """
    가상의 LiDAR 변화 포인트를 입력받아

    1. 클러스터링
    2. 대표 좌표 계산
    3. 변화 이벤트 생성

    까지 수행한다.
    """

    clusters = cluster_points(points)

    print(
        f"[CLUSTER] 생성된 클러스터 수: "
        f"{len(clusters)}"
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

        event = detect_change(
            position=center,
            past_state=past_state,
            current_state=current_state
        )

        if event is not None:
            events.append(event)

    return events


# ======================================================
# TEST 1
# 하나의 물체에서 여러 LiDAR Point 발생
# ======================================================

def test_single_cluster():

    print("\n================================")
    print("TEST 1: 단일 변화 영역 클러스터링")
    print("================================")

    points = [
        (5.00, 2.00),
        (5.03, 2.02),
        (4.98, 1.99),
        (5.05, 2.01),
        (5.01, 2.04),
    ]

    clusters = cluster_points(points)

    assert len(clusters) == 1

    center = get_center(
        clusters[0]
    )

    print(
        f"[RESULT] 대표 좌표 = {center}"
    )

    assert abs(center[0] - 5.0) < 0.1
    assert abs(center[1] - 2.0) < 0.1

    print("\nTEST 1 PASS")


# ======================================================
# TEST 2
# 서로 떨어진 두 변화 영역
# ======================================================

def test_multiple_clusters():

    print("\n================================")
    print("TEST 2: 복수 변화 영역")
    print("================================")

    points = [
        # 첫 번째 물체
        (5.00, 2.00),
        (5.03, 2.02),
        (4.98, 1.99),

        # 두 번째 물체
        (8.00, 7.00),
        (8.04, 7.02),
        (7.98, 6.99),
    ]

    clusters = cluster_points(points)

    print(
        f"[RESULT] 클러스터 수 = "
        f"{len(clusters)}"
    )

    for index, cluster in enumerate(
        clusters,
        start=1
    ):
        print(
            f"[CLUSTER {index}] "
            f"{cluster}"
        )

        print(
            f"[CENTER {index}] "
            f"{get_center(cluster)}"
        )

    assert len(clusters) == 2

    print("\nTEST 2 PASS")


# ======================================================
# TEST 3
# Cluster → Change Detector
# ======================================================

def test_cluster_to_change_detector():

    print("\n================================")
    print("TEST 3: Cluster → Change Detector")
    print("================================")

    points = [
        (5.00, 2.00),
        (5.03, 2.02),
        (4.98, 1.99),
        (5.05, 2.01),
    ]

    events = process_scan(
        points=points,
        past_state=0,
        current_state=1
    )

    assert len(events) == 1

    event = events[0]

    assert (
        event["event_type"]
        == "ADDED"
    )

    print(
        f"[EVENT] {event}"
    )

    print("\nTEST 3 PASS")


# ======================================================
# TEST 4
# Cluster → Change Detector → State Machine
# ======================================================

def test_full_flow():

    print("\n================================")
    print("TEST 4: 전체 통합 흐름")
    print("================================")

    machine = DetectionStateMachine(
        confirm_count=3,
        position_threshold=0.3
    )

    # ------------------------------------------
    # 가상의 연속 LiDAR Scan 3개
    # ------------------------------------------

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

    for scan_number, points in enumerate(
        scans,
        start=1
    ):
        print(
            f"\n---------- SCAN "
            f"{scan_number} ----------"
        )

        events = process_scan(
            points=points,
            past_state=0,
            current_state=1
        )

        assert len(events) == 1

        event = events[0]

        position = event_to_position(
            event
        )

        if (
            machine.get_state()
            == DetectionState.MONITORING
        ):
            machine.start_confirmation(
                position=position,
                event_type=event["event_type"]
            )

        elif (
            machine.get_state()
            == DetectionState.CONFIRMING
        ):
            machine.confirm_detection(
                position=position,
                event_type=event["event_type"]
            )

    # ------------------------------------------
    # 3회 연속 동일 변화 → CAPTURING
    # ------------------------------------------

    assert (
        machine.get_state()
        == DetectionState.CAPTURING
    )

    print(
        "\n[RESULT] "
        "변화 영역 3회 연속 확인 완료"
    )

    print(
        "[RESULT] "
        "State = CAPTURING"
    )

    print("\nTEST 4 PASS")


# ======================================================
# 실행
# ======================================================

if __name__ == "__main__":

    test_single_cluster()

    test_multiple_clusters()

    test_cluster_to_change_detector()

    test_full_flow()

    print("\n================================")
    print("ALL CLUSTER INTEGRATION TESTS PASSED")
    print("================================")
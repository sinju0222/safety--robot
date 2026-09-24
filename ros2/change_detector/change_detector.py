# change_detector.py

FREE = 0
OCCUPIED = 100


def detect_change(baseline_map, lidar_points):
    """
    기준 지도와 현재 LiDAR 데이터를 비교하여
    새롭게 나타난 장애물을 탐지한다.
    """

    changes = []

    for x, y in lidar_points:

        # 지도 범위를 벗어난 데이터는 무시
        if y < 0 or y >= len(baseline_map):
            continue

        if x < 0 or x >= len(baseline_map[0]):
            continue

        # 기준 지도에서 해당 위치 확인
        baseline_value = baseline_map[y][x]

        # 원래 빈 공간이었다면 변화 후보
        if baseline_value == FREE:
            changes.append((x, y))

    return changes


if __name__ == "__main__":

    # 테스트용 기준 지도
    baseline_map = [
        [100, 100, 100, 100, 100],
        [100,   0,   0,   0, 100],
        [100,   0,   0,   0, 100],
        [100,   0,   0,   0, 100],
        [100, 100, 100, 100, 100],
    ]

    # 테스트용 현재 LiDAR 감지 위치
    lidar_points = [
        (2, 2)
    ]

    changes = detect_change(
        baseline_map,
        lidar_points
    )

    if changes:
        print("NEW_OBSTACLE:", changes)
    else:
        print("NO_CHANGE")
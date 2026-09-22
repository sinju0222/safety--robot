import math


def quaternion_to_yaw(q):
    """
    Quaternion을 2D 회전각(yaw)으로 변환한다.
    """

    siny_cosp = 2.0 * (
        q.w * q.z +
        q.x * q.y
    )

    cosy_cosp = 1.0 - 2.0 * (
        q.y * q.y +
        q.z * q.z
    )

    return math.atan2(
        siny_cosp,
        cosy_cosp
    )


def scan_to_map_points(scan_msg, transform):
    """
    LaserScan 데이터를 map 좌표계의
    (x, y) 좌표 목록으로 변환한다.

    scan_msg:
        sensor_msgs/msg/LaserScan

    transform:
        map <- LiDAR frame TF
    """

    points = []

    # LiDAR frame의 map 기준 위치
    tx = transform.transform.translation.x
    ty = transform.transform.translation.y

    # LiDAR frame의 map 기준 방향
    yaw = quaternion_to_yaw(
        transform.transform.rotation
    )

    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)

    for i, distance in enumerate(scan_msg.ranges):

        # inf / nan 제거
        if not math.isfinite(distance):
            continue

        # LiDAR 유효 거리 밖이면 제거
        if distance < scan_msg.range_min:
            continue

        if distance > scan_msg.range_max:
            continue

        # 해당 LaserScan point의 각도
        angle = (
            scan_msg.angle_min +
            i * scan_msg.angle_increment
        )

        # -------------------------
        # LiDAR 기준 좌표
        # -------------------------

        lidar_x = (
            distance *
            math.cos(angle)
        )

        lidar_y = (
            distance *
            math.sin(angle)
        )

        # -------------------------
        # map 좌표로 변환
        # -------------------------

        map_x = (
            tx +
            lidar_x * cos_yaw -
            lidar_y * sin_yaw
        )

        map_y = (
            ty +
            lidar_x * sin_yaw +
            lidar_y * cos_yaw
        )

        points.append(
            (
                round(map_x, 3),
                round(map_y, 3)
            )
        )

    return points
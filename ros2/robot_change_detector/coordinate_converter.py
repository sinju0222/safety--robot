import math


def quaternion_to_yaw(q):
    return math.atan2(
        2.0 * (q.w * q.z + q.x * q.y),
        1.0 - 2.0 * (q.y * q.y + q.z * q.z),
    )


def scan_to_map_points(scan_msg, transform, min_range=0.0):
    """
    LaserScan endpoint들을 LiDAR 좌표계에서 map 좌표계로 변환합니다.
    ADDED 후보 탐지용입니다.
    """
    translation = transform.transform.translation
    rotation = transform.transform.rotation

    tx = float(translation.x)
    ty = float(translation.y)
    yaw = quaternion_to_yaw(rotation)

    c = math.cos(yaw)
    s = math.sin(yaw)

    points = []

    effective_min = max(float(scan_msg.range_min), float(min_range))
    max_range = float(scan_msg.range_max)

    for i, distance in enumerate(scan_msg.ranges):
        if not math.isfinite(distance):
            continue

        distance = float(distance)

        if distance < effective_min or distance > max_range:
            continue

        angle = float(scan_msg.angle_min) + i * float(scan_msg.angle_increment)

        lx = distance * math.cos(angle)
        ly = distance * math.sin(angle)

        mx = tx + lx * c - ly * s
        my = ty + lx * s + ly * c

        points.append((round(mx, 3), round(my, 3)))

    return points

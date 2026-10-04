import math

from config import (
    MIN_LIDAR_RANGE,
    REMOVED_HIT_GUARD_CELLS,
    REMOVED_MAX_RANGE_RATIO,
    REMOVED_RAY_END_MARGIN_CELLS,
)
from coordinate_converter import quaternion_to_yaw


def bresenham_cells(x0, y0, x1, y1):
    """
    두 grid cell 사이를 지나는 정수 grid cell 목록.
    LiDAR ray가 어떤 baseline cell을 실제로 통과했는지 확인할 때 사용.
    """
    cells = []

    dx = abs(x1 - x0)
    dy = abs(y1 - y0)

    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1

    err = dx - dy

    x = x0
    y = y0

    while True:
        cells.append((x, y))

        if x == x1 and y == y1:
            break

        e2 = 2 * err

        if e2 > -dy:
            err -= dy
            x += sx

        if e2 < dx:
            err += dx
            y += sy

    return cells


def _expand_cells(cells, radius, baseline):
    expanded = set()

    for gx, gy in cells:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                nx = gx + dx
                ny = gy + dy

                if baseline.in_bounds(nx, ny):
                    expanded.add((nx, ny))

    return expanded


def build_scan_observation(scan_msg, transform, baseline):
    """
    한 LaserScan으로 두 종류의 증거를 만듭니다.

    hit_points:
        현재 LiDAR가 실제로 물체에 부딪힌 endpoint.
        baseline FREE + hit => ADDED 후보.

    observed_free_cells:
        LiDAR ray가 endpoint보다 더 앞에서 '통과한' cell.
        즉 단순히 점이 안 찍힌 것이 아니라,
        센서가 그 공간이 비어 있음을 직접 관측한 증거.
        baseline OCCUPIED + observed FREE => REMOVED 후보.

    endpoint 근처는 map/TF 오차에 민감해서 REMOVED 판정에서 제외합니다.
    """
    translation = transform.transform.translation
    rotation = transform.transform.rotation

    sensor_x = float(translation.x)
    sensor_y = float(translation.y)
    sensor_yaw = quaternion_to_yaw(rotation)

    origin_grid = baseline.world_to_grid(sensor_x, sensor_y)

    if origin_grid is None:
        return {
            "hit_points": [],
            "observed_free_cells": set(),
            "hit_cells": set(),
        }

    effective_min = max(
        float(scan_msg.range_min),
        float(MIN_LIDAR_RANGE),
    )
    max_range = float(scan_msg.range_max)
    max_valid_hit_range = max_range * float(REMOVED_MAX_RANGE_RATIO)

    c = math.cos(sensor_yaw)
    s = math.sin(sensor_yaw)

    hit_points = []
    hit_cells = set()
    raw_free_cells = set()

    for i, raw_range in enumerate(scan_msg.ranges):
        # REMOVED는 보수적으로: 실제 finite return이 있는 ray만 사용
        if not math.isfinite(raw_range):
            continue

        distance = float(raw_range)

        if distance < effective_min:
            continue

        if distance > max_valid_hit_range:
            continue

        angle = (
            float(scan_msg.angle_min)
            + i * float(scan_msg.angle_increment)
        )

        lx = distance * math.cos(angle)
        ly = distance * math.sin(angle)

        end_x = sensor_x + lx * c - ly * s
        end_y = sensor_y + lx * s + ly * c

        endpoint_grid = baseline.world_to_grid(end_x, end_y)

        if endpoint_grid is None:
            continue

        hit_points.append(
            (round(end_x, 3), round(end_y, 3))
        )
        hit_cells.add(endpoint_grid)

        ray_cells = bresenham_cells(
            origin_grid[0],
            origin_grid[1],
            endpoint_grid[0],
            endpoint_grid[1],
        )

        # 센서 자기 위치 cell 제외
        if len(ray_cells) <= 1:
            continue

        ray_cells = ray_cells[1:]

        # endpoint와 그 직전 몇 cell은 map/localization 오차 보호영역
        if len(ray_cells) <= REMOVED_RAY_END_MARGIN_CELLS:
            continue

        definitely_free = ray_cells[
            :-REMOVED_RAY_END_MARGIN_CELLS
        ]

        for cell in definitely_free:
            if baseline.in_bounds(*cell):
                raw_free_cells.add(cell)

    # 다른 ray의 endpoint 주변도 제거 후보에서 제외
    hit_guard = _expand_cells(
        hit_cells,
        REMOVED_HIT_GUARD_CELLS,
        baseline,
    )

    observed_free_cells = raw_free_cells - hit_guard

    return {
        "hit_points": hit_points,
        "observed_free_cells": observed_free_cells,
        "hit_cells": hit_cells,
    }

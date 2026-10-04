import math

from config import CLUSTER_DISTANCE


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def cluster_points(points):
    """
    서로 가까운 변화 포인트를 하나의 cluster로 묶습니다.
    """
    clusters = []

    for point in points:
        matched = None

        for cluster in clusters:
            if any(distance(point, p) <= CLUSTER_DISTANCE for p in cluster):
                matched = cluster
                break

        if matched is None:
            clusters.append([point])
        else:
            matched.append(point)

    return clusters


def get_center(cluster):
    if not cluster:
        return None

    x = sum(point[0] for point in cluster) / len(cluster)
    y = sum(point[1] for point in cluster) / len(cluster)

    return (round(x, 3), round(y, 3))

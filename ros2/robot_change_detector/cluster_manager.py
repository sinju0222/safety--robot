import math

from config import CLUSTER_DISTANCE


def distance(a, b):
    return math.sqrt(
        (a[0] - b[0]) ** 2 +
        (a[1] - b[1]) ** 2
    )


def cluster_points(points):

    clusters = []

    for point in points:

        added = False

        for cluster in clusters:

            if any(
                distance(point, existing) <= CLUSTER_DISTANCE
                for existing in cluster
            ):
                cluster.append(point)
                added = True
                break

        if not added:
            clusters.append([point])

    return clusters


def get_center(cluster):

    x = sum(p[0] for p in cluster) / len(cluster)
    y = sum(p[1] for p in cluster) / len(cluster)

    return (
        round(x, 3),
        round(y, 3)
    )
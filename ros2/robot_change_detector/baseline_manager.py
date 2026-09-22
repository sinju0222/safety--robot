import json
import math


class BaselineManager:

    FREE = 0
    OCCUPIED = 100
    UNKNOWN = -1

    def __init__(self, object_path=None):

        # 과거 사물 정보
        self.objects = []

        if object_path:
            with open(
                object_path,
                "r",
                encoding="utf-8"
            ) as f:
                self.objects = json.load(f)

        # 기준 OccupancyGrid
        self.resolution = None
        self.width = None
        self.height = None

        self.origin_x = None
        self.origin_y = None

        self.map_data = None

        self.map_ready = False

    # -------------------------------------------------
    # 기준 지도 저장
    # -------------------------------------------------

    def set_baseline_map(self, map_msg):
        """
        ROS2 OccupancyGrid를 기준 지도로 저장한다.

        최초 1회만 저장한다.
        이후 /map이 변경되어도 기준 지도는 변경하지 않는다.
        """

        if self.map_ready:
            return

        self.resolution = (
            map_msg.info.resolution
        )

        self.width = (
            map_msg.info.width
        )

        self.height = (
            map_msg.info.height
        )

        self.origin_x = (
            map_msg.info.origin.position.x
        )

        self.origin_y = (
            map_msg.info.origin.position.y
        )

        self.map_data = list(
            map_msg.data
        )

        self.map_ready = True

    # -------------------------------------------------
    # 실제 좌표 → Grid 좌표
    # -------------------------------------------------

    def world_to_grid(self, x, y):

        if not self.map_ready:
            return None

        grid_x = int(
            (x - self.origin_x)
            / self.resolution
        )

        grid_y = int(
            (y - self.origin_y)
            / self.resolution
        )

        if (
            grid_x < 0
            or grid_x >= self.width
        ):
            return None

        if (
            grid_y < 0
            or grid_y >= self.height
        ):
            return None

        return grid_x, grid_y

    # -------------------------------------------------
    # 기준 지도 값 조회
    # -------------------------------------------------

    def get_map_value(self, x, y):

        grid = self.world_to_grid(
            x,
            y
        )

        if grid is None:
            return None

        grid_x, grid_y = grid

        index = (
            grid_y * self.width
            + grid_x
        )

        return self.map_data[index]

    # -------------------------------------------------
    # 해당 위치가 과거에 빈 공간인지 확인
    # -------------------------------------------------

    def is_free(self, x, y):

        value = self.get_map_value(
            x,
            y
        )

        return value == self.FREE

    # -------------------------------------------------
    # 과거 객체 검색
    # -------------------------------------------------

    def find_nearest_object(
        self,
        x,
        y,
        tolerance=0.20
    ):

        nearest = None
        nearest_distance = float("inf")

        for item in self.objects:

            px = item["position"]["x"]
            py = item["position"]["y"]

            distance = math.sqrt(
                (x - px) ** 2
                + (y - py) ** 2
            )

            if (
                distance <= tolerance
                and distance < nearest_distance
            ):
                nearest = item
                nearest_distance = distance

        return nearest
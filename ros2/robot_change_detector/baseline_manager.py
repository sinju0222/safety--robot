import math


class BaselineManager:
    FREE = 0
    OCCUPIED = 100
    UNKNOWN = -1

    # OccupancyGrid에서 50 이상이면 occupied로 취급
    OCCUPIED_THRESHOLD = 50

    def __init__(self):
        self.resolution = None
        self.width = None
        self.height = None

        self.origin_x = None
        self.origin_y = None
        self.origin_yaw = 0.0

        self.map_data = None
        self.map_ready = False

    @staticmethod
    def _quaternion_to_yaw(q):
        return math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        )

    def set_baseline_map(self, map_msg):
        """
        프로그램 시작 후 처음 받은 /map을 '이전 상황'으로 저장.
        이후에는 확정된 변화만 이 baseline에 반영합니다.
        """
        if self.map_ready:
            return

        self.resolution = float(map_msg.info.resolution)
        self.width = int(map_msg.info.width)
        self.height = int(map_msg.info.height)

        self.origin_x = float(map_msg.info.origin.position.x)
        self.origin_y = float(map_msg.info.origin.position.y)
        self.origin_yaw = self._quaternion_to_yaw(
            map_msg.info.origin.orientation
        )

        self.map_data = list(map_msg.data)
        self.map_ready = True

    def world_to_grid(self, x, y):
        if not self.map_ready:
            return None

        dx = float(x) - self.origin_x
        dy = float(y) - self.origin_y

        c = math.cos(self.origin_yaw)
        s = math.sin(self.origin_yaw)

        local_x = c * dx + s * dy
        local_y = -s * dx + c * dy

        gx = int(math.floor(local_x / self.resolution))
        gy = int(math.floor(local_y / self.resolution))

        if not self.in_bounds(gx, gy):
            return None

        return gx, gy

    def grid_to_world(self, gx, gy):
        """
        grid cell 중앙을 map/world 좌표로 변환합니다.
        """
        if not self.map_ready or not self.in_bounds(gx, gy):
            return None

        local_x = (float(gx) + 0.5) * self.resolution
        local_y = (float(gy) + 0.5) * self.resolution

        c = math.cos(self.origin_yaw)
        s = math.sin(self.origin_yaw)

        world_x = self.origin_x + c * local_x - s * local_y
        world_y = self.origin_y + s * local_x + c * local_y

        return (round(world_x, 3), round(world_y, 3))

    def in_bounds(self, gx, gy):
        return (
            self.width is not None
            and self.height is not None
            and 0 <= gx < self.width
            and 0 <= gy < self.height
        )

    def get_grid_value(self, gx, gy):
        if not self.map_ready or not self.in_bounds(gx, gy):
            return self.UNKNOWN

        return self.map_data[gy * self.width + gx]

    def get_map_value(self, x, y):
        grid = self.world_to_grid(x, y)

        if grid is None:
            return self.UNKNOWN

        return self.get_grid_value(*grid)

    def is_free(self, x, y):
        return self.get_map_value(x, y) == self.FREE

    def is_occupied(self, x, y):
        value = self.get_map_value(x, y)
        return value >= self.OCCUPIED_THRESHOLD

    def is_occupied_grid(self, gx, gy):
        value = self.get_grid_value(gx, gy)
        return value >= self.OCCUPIED_THRESHOLD

    def _mark_points(self, points, value, padding_cells):
        if not self.map_ready:
            return 0

        changed_cells = set()

        for x, y in points:
            grid = self.world_to_grid(x, y)

            if grid is None:
                continue

            gx, gy = grid

            for dx in range(-padding_cells, padding_cells + 1):
                for dy in range(-padding_cells, padding_cells + 1):
                    nx = gx + dx
                    ny = gy + dy

                    if self.in_bounds(nx, ny):
                        changed_cells.add((nx, ny))

        for gx, gy in changed_cells:
            self.map_data[gy * self.width + gx] = value

        return len(changed_cells)

    def mark_points_occupied(self, points, padding_cells=2):
        """
        ADDED 저장 후 현재 물체 영역을 baseline OCCUPIED로 반영.
        """
        return self._mark_points(
            points,
            self.OCCUPIED,
            padding_cells,
        )

    def mark_points_free(self, points, padding_cells=2):
        """
        REMOVED 저장 후 사라진 영역을 baseline FREE로 반영.
        같은 제거 이벤트가 계속 반복되는 것을 막습니다.
        """
        return self._mark_points(
            points,
            self.FREE,
            padding_cells,
        )

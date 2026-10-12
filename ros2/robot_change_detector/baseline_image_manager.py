import json
import math
import shutil
from pathlib import Path


class BaselineImageManager:
    """
    VLM 비교용 RGB baseline 이미지 관리.

    지원 기능:
    1. 기존 좌표 기반 baseline 저장
    2. 기존 위치 기반 baseline 검색
    3. Waypoint ID 기반 baseline 저장
    4. Waypoint ID 기반 baseline 검색
    """

    def __init__(
        self,
        save_dir,
        metadata_file,
        max_distance=0.7,
        max_yaw_difference=math.radians(45.0),
    ):
        self.save_dir = Path(save_dir).expanduser()
        self.metadata_file = Path(metadata_file).expanduser()

        self.max_distance = float(max_distance)
        self.max_yaw_difference = float(max_yaw_difference)

        self.save_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.metadata_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.baselines = []
        self.load()

    # =====================================================
    # Load / Save
    # =====================================================

    def load(self):
        if not self.metadata_file.exists():
            self.baselines = []
            return

        try:
            data = json.loads(
                self.metadata_file.read_text(
                    encoding="utf-8"
                )
            )

            self.baselines = (
                data
                if isinstance(data, list)
                else []
            )

        except (
            json.JSONDecodeError,
            OSError,
        ):
            self.baselines = []

    def save(self):
        self.metadata_file.write_text(
            json.dumps(
                self.baselines,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # =====================================================
    # Angle
    # =====================================================

    @staticmethod
    def angle_difference(
        angle1,
        angle2,
    ):
        difference = (
            angle1
            - angle2
            + math.pi
        ) % (2.0 * math.pi) - math.pi

        return abs(difference)

    # =====================================================
    # Existing baseline registration
    # =====================================================

    def add_baseline(
        self,
        image_path,
        x,
        y,
        yaw,
    ):
        source = Path(image_path)

        if not source.is_file():
            raise FileNotFoundError(
                f"Baseline image not found: {source}"
            )

        baseline_id = (
            max(
                (
                    int(item.get("id", 0))
                    for item in self.baselines
                ),
                default=0,
            )
            + 1
        )

        suffix = (
            source.suffix
            if source.suffix
            else ".jpg"
        )

        filename = (
            f"baseline_{baseline_id:05d}{suffix}"
        )

        destination = (
            self.save_dir / filename
        )

        shutil.copy2(
            source,
            destination,
        )

        item = {
            "id": baseline_id,
            "x": float(x),
            "y": float(y),
            "yaw": float(yaw),
            "image": str(destination),
        }

        self.baselines.append(item)
        self.save()

        return item

    # =====================================================
    # Existing baseline search
    # =====================================================

    def find_nearest(
        self,
        x,
        y,
        yaw,
    ):
        if not self.baselines:
            return None

        x = float(x)
        y = float(y)
        yaw = float(yaw)

        best_item = None
        best_score = None

        for item in self.baselines:
            try:
                baseline_x = float(item["x"])
                baseline_y = float(item["y"])
                baseline_yaw = float(item["yaw"])
            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            distance = math.hypot(
                x - baseline_x,
                y - baseline_y,
            )

            yaw_difference = (
                self.angle_difference(
                    yaw,
                    baseline_yaw,
                )
            )

            if distance > self.max_distance:
                continue

            if yaw_difference > self.max_yaw_difference:
                continue

            score = (
                distance
                + 0.3 * yaw_difference
            )

            if (
                best_score is None
                or score < best_score
            ):
                best_score = score
                best_item = item

        return best_item

    def get_image_path(
        self,
        x,
        y,
        yaw,
    ):
        item = self.find_nearest(
            x,
            y,
            yaw,
        )

        if item is None:
            return None

        image_path = Path(
            item["image"]
        )

        if not image_path.is_file():
            return None

        return str(image_path)

    # =====================================================
    # Waypoint baseline registration
    # =====================================================

    def add_waypoint_baseline(
        self,
        waypoint_id,
        image_path,
        x,
        y,
        yaw,
    ):
        """
        지정된 Waypoint의 기준 이미지 저장.

        예:
        waypoint_1.jpg
        waypoint_2.jpg
        waypoint_3.jpg

        동일 Waypoint의 기준 이미지가 존재하면
        새로운 기준 이미지로 교체한다.
        """

        waypoint_id = int(
            waypoint_id
        )

        if waypoint_id < 1:
            raise ValueError(
                "waypoint_id must be >= 1"
            )

        source = Path(
            image_path
        ).expanduser()

        if not source.is_file():
            raise FileNotFoundError(
                f"Image not found: {source}"
            )

        destination = (
            self.save_dir
            / f"waypoint_{waypoint_id}.jpg"
        )

        if source.resolve() != destination.resolve():
            shutil.copy2(
                source,
                destination,
            )

        item = {
            "id": waypoint_id,
            "waypoint_id": waypoint_id,
            "x": float(x),
            "y": float(y),
            "yaw": float(yaw),
            "image": str(destination),
        }

        # 동일 Waypoint의 기존 메타데이터 제거
        self.baselines = [
            baseline
            for baseline in self.baselines
            if baseline.get(
                "waypoint_id"
            ) != waypoint_id
        ]

        self.baselines.append(
            item
        )

        self.save()

        return item

    # =====================================================
    # Waypoint baseline search
    # =====================================================

    def get_waypoint_baseline(
        self,
        waypoint_id,
    ):
        """
        Waypoint ID에 해당하는 기준 이미지 검색.

        이미지가 없으면 None 반환.
        """

        waypoint_id = int(
            waypoint_id
        )

        for item in self.baselines:
            if item.get(
                "waypoint_id"
            ) != waypoint_id:
                continue

            image_path = Path(
                item["image"]
            )

            if image_path.is_file():
                return str(
                    image_path
                )

        return None

    # =====================================================
    # Waypoint baseline count
    # =====================================================

    def count_waypoint_baselines(self):
        """
        저장된 Waypoint 기준 이미지 개수 반환.
        실제 파일이 존재하는 이미지만 계산한다.
        """

        count = 0

        for item in self.baselines:
            if "waypoint_id" not in item:
                continue

            image_path = Path(
                item["image"]
            )

            if image_path.is_file():
                count += 1

        return count

    # =====================================================
    # Utility
    # =====================================================

    def count(self):
        return len(
            self.baselines
        )

    def clear(self):
        self.baselines = []
        self.save()

        if not self.save_dir.exists():
            return

        for path in self.save_dir.iterdir():
            if path.is_file():
                path.unlink()
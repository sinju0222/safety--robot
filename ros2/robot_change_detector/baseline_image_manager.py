import json
import math
import shutil
from pathlib import Path


class BaselineImageManager:
    """
    VLM 비교용 RGB baseline 이미지를 관리한다.

    기준 순찰에서 촬영한 이미지와 당시 로봇의
    x, y, yaw를 함께 저장하고, 이후 순찰에서
    가장 가까운 기준 이미지를 검색한다.
    """

    def __init__(
        self,
        save_dir,
        metadata_file,
        max_distance=0.7,
        max_yaw_difference=math.radians(45.0),
    ):
        self.save_dir = Path(save_dir)
        self.metadata_file = Path(metadata_file)

        self.max_distance = float(
            max_distance
        )
        self.max_yaw_difference = float(
            max_yaw_difference
        )

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
    # Baseline registration
    # =====================================================

    def add_baseline(
        self,
        image_path,
        x,
        y,
        yaw,
    ):
        source = Path(image_path)

        if not source.exists():
            raise FileNotFoundError(
                f"Baseline image not found: "
                f"{source}"
            )

        baseline_id = (
            max(
                (
                    int(
                        item.get(
                            "id",
                            0,
                        )
                    )
                    for item
                    in self.baselines
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
            f"baseline_"
            f"{baseline_id:05d}"
            f"{suffix}"
        )

        destination = (
            self.save_dir
            / filename
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

        self.baselines.append(
            item
        )
        self.save()

        return item

    # =====================================================
    # Baseline search
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
                baseline_x = float(
                    item["x"]
                )
                baseline_y = float(
                    item["y"]
                )
                baseline_yaw = float(
                    item["yaw"]
                )
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

            if (
                distance
                > self.max_distance
            ):
                continue

            if (
                yaw_difference
                > self.max_yaw_difference
            ):
                continue

            score = (
                distance
                + 0.3
                * yaw_difference
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

        if not image_path.exists():
            return None

        return str(image_path)

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

        for path in (
            self.save_dir.iterdir()
        ):
            if path.is_file():
                path.unlink()
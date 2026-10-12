import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
from cv_bridge import CvBridge


class CameraManager:
    """
    ROS2 카메라 이미지 관리.

    기존 기능:
    - 최신 ROS Image 메시지 저장
    - 변화 감지 시 JPG 촬영

    추가 기능:
    - Waypoint 도착 후 새로운 프레임 촬영
    - Waypoint별 이미지 저장
    - 기준 이미지와 현재 이미지 구분
    - 촬영 실패 및 타임아웃 처리
    """

    def __init__(
        self,
        save_dir="captures",
    ):
        self.save_dir = Path(
            save_dir
        ).expanduser()

        self.save_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.bridge = CvBridge()

        self.latest_msg = None
        self.frame_sequence = 0

        self.lock = threading.Lock()
        self.frame_condition = threading.Condition(
            self.lock
        )

    # =====================================================
    # ROS Image update
    # =====================================================

    def update_frame(
        self,
        image_msg,
    ):
        """
        ROS2 카메라 토픽에서 수신한
        최신 이미지를 저장한다.
        """

        with self.frame_condition:
            self.latest_msg = image_msg
            self.frame_sequence += 1

            self.frame_condition.notify_all()

    # =====================================================
    # JPG save
    # =====================================================

    def _save_image(
        self,
        image_msg,
        destination,
    ):
        """
        ROS Image 메시지를 OpenCV 이미지로
        변환한 뒤 JPG 파일로 저장한다.
        """

        if image_msg is None:
            return None

        destination = Path(
            destination
        ).expanduser()

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            frame = self.bridge.imgmsg_to_cv2(
                image_msg,
                desired_encoding="bgr8",
            )

            success = cv2.imwrite(
                str(destination),
                frame,
                [
                    int(
                        cv2.IMWRITE_JPEG_QUALITY
                    ),
                    90,
                ],
            )

            if not success:
                return None

            return str(destination)

        except Exception:
            return None

    # =====================================================
    # Existing capture
    # =====================================================

    def capture(self):
        """
        기존 변화 감지용 촬영 기능.

        현재 저장된 최신 프레임을
        JPG 이미지로 저장한다.
        """

        with self.lock:
            image_msg = self.latest_msg

        if image_msg is None:
            return None

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        image_path = (
            self.save_dir
            / f"change_{timestamp}.jpg"
        )

        return self._save_image(
            image_msg,
            image_path,
        )

    # =====================================================
    # Waypoint capture
    # =====================================================

    def capture_waypoint(
        self,
        waypoint_id,
        mode="MONITORING",
        timeout=5.0,
    ):
        """
        Waypoint 도착 후 새 카메라 프레임을
        수신하여 JPG로 저장한다.

        BASELINE:
            baseline_images/waypoint_1.jpg

        MONITORING:
            current_images/waypoint_1_시간.jpg

        주의:
        이 함수는 새 프레임을 기다리므로
        ROS2 콜백 실행 스레드에서 직접
        호출하면 안 된다.
        """

        waypoint_id = int(
            waypoint_id
        )

        if waypoint_id < 1:
            raise ValueError(
                "waypoint_id must be >= 1"
            )

        mode = str(
            mode
        ).upper()

        if mode not in {
            "BASELINE",
            "MONITORING",
        }:
            raise ValueError(
                "mode must be BASELINE "
                "or MONITORING"
            )

        # ---------------------------------------------
        # Capture request time
        # ---------------------------------------------

        with self.frame_condition:
            previous_sequence = (
                self.frame_sequence
            )

            deadline = (
                time.monotonic()
                + float(timeout)
            )

            while (
                self.frame_sequence
                <= previous_sequence
            ):
                remaining = (
                    deadline
                    - time.monotonic()
                )

                if remaining <= 0:
                    return None

                self.frame_condition.wait(
                    timeout=remaining
                )

            image_msg = self.latest_msg

        # ---------------------------------------------
        # Image destination
        # ---------------------------------------------

        if mode == "BASELINE":
            image_dir = (
                self.save_dir.parent
                / "baseline_images"
            )

            filename = (
                f"waypoint_{waypoint_id}.jpg"
            )

        else:
            image_dir = (
                self.save_dir.parent
                / "current_images"
            )

            timestamp = (
                datetime.now().strftime(
                    "%Y%m%d_%H%M%S_%f"
                )
            )

            filename = (
                f"waypoint_{waypoint_id}_"
                f"{timestamp}.jpg"
            )

        image_path = (
            image_dir
            / filename
        )

        return self._save_image(
            image_msg,
            image_path,
        )
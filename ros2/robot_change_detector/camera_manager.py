from datetime import datetime
from pathlib import Path

import cv2
from cv_bridge import CvBridge


class CameraManager:
    """
    Raspberry Pi 4 부하 절약:
    평소에는 최신 ROS Image 메시지만 기억하고,
    변화 확정 때만 OpenCV 변환 + JPG 저장.
    """

    def __init__(self, save_dir="captures"):
        self.save_dir = Path(save_dir).expanduser()
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.bridge = CvBridge()
        self.latest_msg = None

    def update_frame(self, image_msg):
        self.latest_msg = image_msg

    def capture(self):
        if self.latest_msg is None:
            return None

        try:
            frame = self.bridge.imgmsg_to_cv2(
                self.latest_msg,
                desired_encoding="bgr8",
            )
        except Exception:
            return None

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        image_path = (
            self.save_dir
            / f"change_{timestamp}.jpg"
        )

        success = cv2.imwrite(
            str(image_path),
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 90],
        )

        if not success:
            return None

        return str(image_path)

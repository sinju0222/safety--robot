import os
from datetime import datetime

import cv2
from cv_bridge import CvBridge


class CameraManager:

    def __init__(self, save_dir="captures"):

        self.bridge = CvBridge()
        self.latest_frame = None
        self.save_dir = save_dir

        os.makedirs(
            self.save_dir,
            exist_ok=True
        )

    def update_frame(self, image_msg):
        """
        ROS2 Image 메시지를 OpenCV 이미지로 변환하여
        가장 최근 프레임을 보관한다.
        """

        try:
            self.latest_frame = (
                self.bridge.imgmsg_to_cv2(
                    image_msg,
                    desired_encoding="bgr8"
                )
            )

        except Exception as e:
            print(
                f"[CAMERA ERROR] {e}"
            )

    def capture(self):
        """
        가장 최근 RealSense RGB 프레임을 저장한다.
        """

        if self.latest_frame is None:
            return None

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        path = os.path.join(
            self.save_dir,
            f"change_{timestamp}.jpg"
        )

        success = cv2.imwrite(
            path,
            self.latest_frame
        )

        if not success:
            return None

        return path
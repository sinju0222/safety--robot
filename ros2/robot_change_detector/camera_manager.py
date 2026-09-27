import os
from datetime import datetime

import cv2


# ==================================================
# ROS2 CvBridge
# ==================================================

try:
    from cv_bridge import CvBridge

    CV_BRIDGE_AVAILABLE = True

except ImportError:
    CvBridge = None
    CV_BRIDGE_AVAILABLE = False


class CameraManager:

    def __init__(self, save_dir="captures"):

        # ROS2 환경에서는 CvBridge 사용
        # Mac 테스트 환경에서는 None
        if CV_BRIDGE_AVAILABLE:
            self.bridge = CvBridge()
        else:
            self.bridge = None

        self.latest_frame = None
        self.save_dir = save_dir

        os.makedirs(
            self.save_dir,
            exist_ok=True
        )

    # ==================================================
    # ROS2 Image 메시지 입력
    # ==================================================

    def update_frame(self, image_msg):
        """
        ROS2 Image 메시지를 OpenCV 이미지로 변환하여
        가장 최근 프레임을 저장한다.

        실제 TurtleBot / ROS2 환경에서 사용한다.
        """

        if self.bridge is None:
            print(
                "[CAMERA] cv_bridge를 사용할 수 없습니다. "
                "ROS2 환경에서 실행해주세요."
            )
            return False

        try:
            self.latest_frame = (
                self.bridge.imgmsg_to_cv2(
                    image_msg,
                    desired_encoding="bgr8"
                )
            )

            return True

        except Exception as e:
            print(
                f"[CAMERA ERROR] {e}"
            )

            return False

    # ==================================================
    # OpenCV Frame 직접 입력
    # ==================================================

    def update_cv_frame(self, frame):
        """
        OpenCV 이미지를 직접 입력한다.

        실제 ROS2 환경뿐 아니라
        가상 테스트에서도 사용할 수 있다.
        """

        if frame is None:
            return False

        self.latest_frame = frame

        return True

    # ==================================================
    # 이미지 저장
    # ==================================================

    def capture(self):
        """
        가장 최근 RGB 프레임을 이미지 파일로 저장한다.
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
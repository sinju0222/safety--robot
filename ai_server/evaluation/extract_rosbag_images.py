from pathlib import Path

import cv2
import numpy as np
from mcap_ros2.reader import read_ros2_messages


BASE_DIR = Path(__file__).resolve().parent

MCAP_PATH = (
    BASE_DIR
    / "rosbag_data"
    / "rosbag2_2026_10_02-17_19_28"
    / "rosbag2_2026_10_02-17_19_28_0.mcap"
)

OUTPUT_DIR = BASE_DIR / "real_images"

IMAGE_TOPIC = "/camera/camera/color/image_raw"


def ros_image_to_numpy(msg):
    """
    sensor_msgs/msg/Image를 OpenCV 이미지로 변환합니다.
    """

    height = msg.height
    width = msg.width
    encoding = msg.encoding.lower()

    data = np.frombuffer(
        msg.data,
        dtype=np.uint8,
    )

    if encoding == "rgb8":
        image = data.reshape(
            height,
            width,
            3,
        )

        image = cv2.cvtColor(
            image,
            cv2.COLOR_RGB2BGR,
        )

    elif encoding == "bgr8":
        image = data.reshape(
            height,
            width,
            3,
        )

    elif encoding == "rgba8":
        image = data.reshape(
            height,
            width,
            4,
        )

        image = cv2.cvtColor(
            image,
            cv2.COLOR_RGBA2BGR,
        )

    elif encoding == "bgra8":
        image = data.reshape(
            height,
            width,
            4,
        )

        image = cv2.cvtColor(
            image,
            cv2.COLOR_BGRA2BGR,
        )

    else:
        raise ValueError(
            f"지원하지 않는 encoding: {msg.encoding}"
        )

    return image


def main():

    print("=" * 60)
    print("ROS2 MCAP RealSense RGB Image Extractor")
    print("=" * 60)

    if not MCAP_PATH.exists():
        raise FileNotFoundError(
            f"MCAP 파일을 찾을 수 없습니다:\n{MCAP_PATH}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print(f"MCAP: {MCAP_PATH}")
    print(f"Topic: {IMAGE_TOPIC}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    frame_count = 0

    with open(MCAP_PATH, "rb") as stream:

        for message in read_ros2_messages(
            stream,
            topics=[IMAGE_TOPIC],
        ):

            ros_msg = message.ros_msg

            try:
                image = ros_image_to_numpy(
                    ros_msg
                )

            except Exception as error:
                print(
                    f"[ERROR] frame "
                    f"{frame_count}: {error}"
                )
                continue

            output_path = (
                OUTPUT_DIR
                / f"frame_{frame_count:04d}.png"
            )

            success = cv2.imwrite(
                str(output_path),
                image,
            )

            if not success:
                print(
                    f"[ERROR] 저장 실패: "
                    f"{output_path}"
                )
                continue

            print(
                f"[SAVE] "
                f"{output_path.name} "
                f"{image.shape[1]}x"
                f"{image.shape[0]}"
            )

            frame_count += 1

    print()
    print("=" * 60)
    print("추출 완료")
    print(f"총 RGB 이미지: {frame_count}장")
    print(f"저장 위치: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
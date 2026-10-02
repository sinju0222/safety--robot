from datetime import datetime
from pathlib import Path


def create_event(
    change,
    detected_objects=None,
    image_path=None,
    robot_pose=None,
):
    """
    변화 감지 결과를 최종 Event JSON 형식으로 변환한다.

    최종 형식:

    {
        "event_id": "evt_001",
        "timestamp": "2026-10-01T19:55:21+09:00",

        "change": {
            "type": "ADDED",
            "x": 3.21,
            "y": 5.43
        },

        "robot": {
            "x": 2.84,
            "y": 4.91,
            "yaw": 1.57
        },

        "image": "change_001.jpg"
    }
    """

    if robot_pose is None:
        raise ValueError(
            "robot_pose가 필요합니다."
        )

    if image_path is None:
        raise ValueError(
            "image_path가 필요합니다."
        )

    # 현재 시간
    now = datetime.now().astimezone()

    # 이벤트 ID
    event_id = (
        "evt_"
        + now.strftime(
            "%Y%m%d_%H%M%S_%f"
        )
    )

    # 이미지 파일 이름만 사용
    image_name = Path(
        image_path
    ).name

    # 최종 Event
    event = {

        "event_id": event_id,

        "timestamp": now.isoformat(),

        "change": {
            "type": change["event_type"],

            "x": float(
                change["position"]["x"]
            ),

            "y": float(
                change["position"]["y"]
            ),
        },

        "robot": {
            "x": float(
                robot_pose["x"]
            ),

            "y": float(
                robot_pose["y"]
            ),

            "yaw": float(
                robot_pose["yaw"]
            ),
        },

        "image": image_name,
    }

    return event
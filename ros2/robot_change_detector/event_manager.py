import json
from datetime import datetime
from pathlib import Path


def create_event(change, detected_objects, image_path, robot_pose,
                 save_dir="events", workplace_id=None):
    if robot_pose is None:
        raise ValueError("robot_pose is required")
    if image_path is None:
        raise ValueError("image_path is required")

    now = datetime.now().astimezone()
    event_id = "evt_" + now.strftime("%Y%m%d_%H%M%S_%f")
    event = {
        "event_id": event_id,
        "timestamp": now.isoformat(),
        "change": {
            "type": change["event_type"],
            "x": round(float(change["position"]["x"]), 3),
            "y": round(float(change["position"]["y"]), 3),
        },
        "robot": {
            "x": round(float(robot_pose["x"]), 3),
            "y": round(float(robot_pose["y"]), 3),
            "yaw": round(float(robot_pose["yaw"]), 3),
        },
        "image": Path(image_path).name,
        "objects": detected_objects or [],
    }
    if workplace_id is not None:
        event["workplace_id"] = int(workplace_id)

    output_dir = Path(save_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{event_id}.json"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(event, file, ensure_ascii=False, indent=2)
    return event

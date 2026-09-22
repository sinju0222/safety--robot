def detect_change(
    position,
    past_state,
    current_state,
    past_objects=None
):

    if past_objects is None:
        past_objects = []

    # 변화 없음
    if past_state == current_state:
        return None

    # 기존 물체가 사라짐
    if past_state == 1 and current_state == 0:

        return {
            "event_type": "REMOVED",
            "position": {
                "x": position[0],
                "y": position[1]
            },
            "past_state": 1,
            "current_state": 0,
            "objects": past_objects,
            "need_capture": True,
            "need_yolo": False
        }

    # 새로운 물체 등장
    if past_state == 0 and current_state == 1:

        return {
            "event_type": "ADDED",
            "position": {
                "x": position[0],
                "y": position[1]
            },
            "past_state": 0,
            "current_state": 1,
            "objects": [],
            "need_capture": True,
            "need_yolo": True
        }

    return None
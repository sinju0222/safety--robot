# change_detector.py

FREE = 0
OCCUPIED = 1
UNKNOWN = 255


def detect_change(position, past_state, current_state):
    """
    변화 위치와 이전/현재 상태를 이용하여
    하나의 변화 이벤트를 생성한다.
    """

    if past_state == FREE and current_state == OCCUPIED:
        event_type = "ADDED"

    elif past_state == OCCUPIED and current_state == FREE:
        event_type = "REMOVED"

    else:
        return None

    return {
        "event_type": event_type,

        "position": {
            "x": float(position[0]),
            "y": float(position[1]),
        },

        "past_state": int(past_state),

        "current_state": int(current_state),
    }


if __name__ == "__main__":

    position = (3.0, 5.0)

    change = detect_change(
        position=position,
        past_state=FREE,
        current_state=OCCUPIED,
    )

    print("감지된 변화:")

    print(change)
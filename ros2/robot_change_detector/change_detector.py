FREE = 0
OCCUPIED = 1


def detect_change(position, past_state, current_state):
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

from datetime import datetime


def create_event(change, detected_objects=None):

    if detected_objects is None:
        detected_objects = []

    if change["event_type"] == "ADDED":
        objects = detected_objects
    else:
        objects = change["objects"]

    return {
        "robot_id": "TB3_01",

        "event_type": change["event_type"],

        "position": change["position"],

        "past_state": change["past_state"],

        "current_state": change["current_state"],

        "objects": objects,

        "timestamp": datetime.now().isoformat()
    }
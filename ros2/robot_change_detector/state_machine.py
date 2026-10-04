from enum import Enum
import math


class DetectionState(Enum):
    MONITORING = "MONITORING"
    CONFIRMING = "CONFIRMING"
    CAPTURING = "CAPTURING"
    ANALYZING = "ANALYZING"
    PROCESSING = "PROCESSING"


class DetectionStateMachine:
    def __init__(self, position_threshold=0.30):
        self.position_threshold = float(position_threshold)
        self.reset()

    def get_state(self):
        return self.state

    def get_progress(self):
        return (
            self.confirmation_count,
            self.candidate_confirm_count_required,
        )

    def start_confirmation(
        self,
        position,
        event_type,
        required_count,
    ):
        self.state = DetectionState.CONFIRMING
        self.candidate_position = tuple(position)
        self.candidate_event_type = event_type

        self.candidate_confirm_count_required = int(required_count)
        self.confirmation_count = 1

    def confirm_detection(self, position, event_type):
        if self.state != DetectionState.CONFIRMING:
            return False

        same_type = (
            event_type
            == self.candidate_event_type
        )

        distance = math.hypot(
            float(position[0]) - float(self.candidate_position[0]),
            float(position[1]) - float(self.candidate_position[1]),
        )

        same_position = (
            distance <= self.position_threshold
        )

        if not (same_type and same_position):
            self.reset()
            return False

        self.confirmation_count += 1
        self.candidate_position = tuple(position)

        if (
            self.confirmation_count
            >= self.candidate_confirm_count_required
        ):
            self.state = DetectionState.CAPTURING
            return True

        return False

    def capture_completed(self):
        if self.state == DetectionState.CAPTURING:
            self.state = DetectionState.ANALYZING

    def analysis_completed(self):
        if self.state == DetectionState.ANALYZING:
            self.state = DetectionState.PROCESSING

    def processing_completed(self):
        if self.state == DetectionState.PROCESSING:
            self.reset()

    def cancel_confirmation(self):
        if self.state == DetectionState.CONFIRMING:
            self.reset()

    def reset(self):
        self.state = DetectionState.MONITORING

        self.candidate_position = None
        self.candidate_event_type = None

        self.candidate_confirm_count_required = 0
        self.confirmation_count = 0

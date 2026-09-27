from enum import Enum, auto
import math


class DetectionState(Enum):
    """
    환경 변화 탐지 파이프라인 상태
    """

    MONITORING = auto()
    CONFIRMING = auto()
    CAPTURING = auto()
    ANALYZING = auto()
    PROCESSING = auto()


class DetectionStateMachine:
    """
    환경 변화 탐지 State Machine

    MONITORING
        ↓ 변화 후보 발견
    CONFIRMING
        ↓ 동일 위치 변화 연속 확인
    CAPTURING
        ↓ 이미지 촬영 완료
    ANALYZING
        ↓ YOLO 분석 완료
    PROCESSING
        ↓ 데이터 처리 완료
    MONITORING
    """

    def __init__(
        self,
        confirm_count=3,
        position_threshold=0.3
    ):
        # 현재 상태
        self.state = DetectionState.MONITORING

        # 변화 확정에 필요한 연속 감지 횟수
        self.confirm_count_required = confirm_count

        # 현재 연속 감지 횟수
        self.confirm_count = 0

        # 동일 변화라고 판단할 최대 거리(m)
        self.position_threshold = position_threshold

        # 현재 확인 중인 변화 위치
        self.current_position = None

        # 현재 변화 종류
        # ADDED / REMOVED
        self.current_event_type = None

    # ==================================================
    # 현재 상태 조회
    # ==================================================

    def get_state(self):
        return self.state

    # ==================================================
    # 상태 변경
    # ==================================================

    def _set_state(self, new_state):
        old_state = self.state
        self.state = new_state

        print(
            f"[STATE] "
            f"{old_state.name} -> {new_state.name}"
        )

    # ==================================================
    # 두 좌표 사이 거리 계산
    # ==================================================

    def _calculate_distance(
        self,
        position1,
        position2
    ):
        x1, y1 = position1
        x2, y2 = position2

        return math.sqrt(
            (x2 - x1) ** 2
            + (y2 - y1) ** 2
        )

    # ==================================================
    # 동일 위치 변화인지 확인
    # ==================================================

    def _is_same_position(self, position):
        if self.current_position is None:
            return False

        distance = self._calculate_distance(
            self.current_position,
            position
        )

        print(
            f"[POSITION] 기준 위치: "
            f"{self.current_position}"
        )

        print(
            f"[POSITION] 현재 위치: "
            f"{position}"
        )

        print(
            f"[POSITION] 거리 차이: "
            f"{distance:.3f} m"
        )

        return (
            distance
            <= self.position_threshold
        )

    # ==================================================
    # 최초 변화 발견
    # ==================================================

    def start_confirmation(
        self,
        position,
        event_type="ADDED"
    ):
        if (
            self.state
            != DetectionState.MONITORING
        ):
            return False

        self.current_position = position
        self.current_event_type = event_type

        self.confirm_count = 1

        self._set_state(
            DetectionState.CONFIRMING
        )

        print(
            f"[CONFIRM] "
            f"{self.confirm_count}/"
            f"{self.confirm_count_required}"
        )

        return True

    # ==================================================
    # 다음 변화 신호 확인
    # ==================================================

    def confirm_detection(
        self,
        position,
        event_type="ADDED"
    ):
        if (
            self.state
            != DetectionState.CONFIRMING
        ):
            return False

        # ----------------------------------------------
        # 변화 종류 확인
        # ----------------------------------------------

        if (
            event_type
            != self.current_event_type
        ):
            print(
                "[CONFIRM] "
                "변화 종류가 다릅니다."
            )

            self.reset()

            return False

        # ----------------------------------------------
        # 위치 확인
        # ----------------------------------------------

        if not self._is_same_position(position):
            print(
                "[CONFIRM] "
                "다른 위치의 변화입니다."
            )

            self.reset()

            return False

        # ----------------------------------------------
        # 동일 변화로 인정
        # ----------------------------------------------

        self.confirm_count += 1

        print(
            f"[CONFIRM] "
            f"{self.confirm_count}/"
            f"{self.confirm_count_required}"
        )

        # 아직 확인 횟수가 부족함
        if (
            self.confirm_count
            < self.confirm_count_required
        ):
            return False

        # 변화 확정
        self._set_state(
            DetectionState.CAPTURING
        )

        return True

    # ==================================================
    # 변화가 사라짐
    # ==================================================

    def cancel_confirmation(self):
        if (
            self.state
            != DetectionState.CONFIRMING
        ):
            return False

        print(
            "[CONFIRM] "
            "변화 후보가 사라졌습니다."
        )

        self.reset()

        return True

    # ==================================================
    # 이미지 촬영 완료
    # ==================================================

    def capture_completed(self):
        if (
            self.state
            != DetectionState.CAPTURING
        ):
            return False

        self._set_state(
            DetectionState.ANALYZING
        )

        return True

    # ==================================================
    # YOLO 분석 완료
    # ==================================================

    def analysis_completed(self):
        if (
            self.state
            != DetectionState.ANALYZING
        ):
            return False

        self._set_state(
            DetectionState.PROCESSING
        )

        return True

    # ==================================================
    # 데이터 처리 완료
    # ==================================================

    def processing_completed(self):
        if (
            self.state
            != DetectionState.PROCESSING
        ):
            return False

        print(
            "[PROCESSING] "
            "변화 이벤트 처리 완료"
        )

        self.reset()

        return True

    # ==================================================
    # 초기화
    # ==================================================

    def reset(self):
        old_state = self.state

        self.state = (
            DetectionState.MONITORING
        )

        self.confirm_count = 0
        self.current_position = None
        self.current_event_type = None

        print(
            f"[STATE] "
            f"{old_state.name} -> MONITORING"
        )
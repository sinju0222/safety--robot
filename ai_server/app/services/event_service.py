import uuid

from app.schemas.change_event import (
    ChangeEvent,
    Position,
    create_timestamp,
)


# =========================================================
# 임시 이벤트 저장소
#
# 현재 프로젝트에서는 DB를 사용하지 않으므로
# 서버 메모리에 이벤트를 저장한다.
# 서버가 종료되면 데이터는 초기화된다.
# =========================================================

_events: dict[str, ChangeEvent] = {}


# =========================================================
# 이벤트 생성
# =========================================================

def create_event(
    change_type: str,
    x: float,
    y: float,
    detected_object: str,
    risk_score: int,
    risk_level: str,
    reason: str,
):

    event_id = str(
        uuid.uuid4()
    )

    event = ChangeEvent(
        event_id=event_id,

        change_type=change_type,

        position=Position(
            x=x,
            y=y,
        ),

        detected_object=detected_object,

        risk_score=risk_score,

        risk_level=risk_level,

        reason=reason,

        acknowledged=False,

        created_at=create_timestamp(),
    )

    _events[event_id] = event

    return event


# =========================================================
# 전체 이벤트 조회
# =========================================================

def get_events():

    return list(
        _events.values()
    )


# =========================================================
# 미확인 이벤트만 조회
# =========================================================

def get_unacknowledged_events():

    return [
        event
        for event in _events.values()
        if not event.acknowledged
    ]


# =========================================================
# 이벤트 하나 조회
# =========================================================

def get_event(
    event_id: str,
):

    return _events.get(
        event_id
    )


# =========================================================
# 작업자 확인
# =========================================================

def acknowledge_event(
    event_id: str,
):

    event = _events.get(
        event_id
    )

    if event is None:
        return None

    event.acknowledged = True

    return event
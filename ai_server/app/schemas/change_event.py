from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel


ChangeType = Literal[
    "ADDED",
    "REMOVED",
]

RiskLevel = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
]


class Position(BaseModel):
    x: float
    y: float


class ChangeEvent(BaseModel):
    event_id: str

    change_type: ChangeType

    position: Position

    detected_object: str

    risk_score: int

    risk_level: RiskLevel

    reason: str

    acknowledged: bool = False

    created_at: datetime


def create_timestamp():
    return datetime.now(
        timezone.utc
    )
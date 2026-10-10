from typing import Literal

from pydantic import BaseModel


# =========================================================
# 허용 값
# =========================================================

ChangeType = Literal[
    "NO_CHANGE",
    "ADDED",
    "REMOVED",
    "MOVED",
    "STATE_CHANGED",
    "MIXED",
]

RiskLevel = Literal[
    "NORMAL",
    "LOW",
    "MEDIUM",
    "HIGH",
]

HazardType = Literal[
    "trip_hazard",
    "object_on_path",
    "path_obstruction",
    "sharp_tool_hazard",
    "rolling_object_hazard",
    "unstable_object",
    "falling_object_hazard",
]


# =========================================================
# 환경 변화 분석
# =========================================================

class ChangeAnalysis(BaseModel):
    change_detected: bool

    change_type: ChangeType

    added_objects: list[str]

    removed_objects: list[str]

    moved_objects: list[str]

    state_changed_objects: list[str]


# =========================================================
# 위험 분석
# =========================================================

class RiskAssessment(BaseModel):
    hazard_present: bool

    hazard_types: list[HazardType]

    risk_level: RiskLevel


# =========================================================
# 상황 설명
# =========================================================

class SituationAnalysis(BaseModel):
    summary: str


# =========================================================
# VLM 최종 분석 결과
# =========================================================

class VLMAnalysisResult(BaseModel):
    change: ChangeAnalysis

    risk_assessment: RiskAssessment

    situation: SituationAnalysis

    recommended_actions: list[str]


# =========================================================
# 성능 정보
# =========================================================

class PerformanceInfo(BaseModel):
    requested_model: str

    actual_model: str | None = None

    latency_seconds: float

    prompt_tokens: int | None = None

    completion_tokens: int | None = None

    total_tokens: int | None = None


# =========================================================
# AI 서버 최종 응답
# =========================================================

class RiskAnalysisResponse(BaseModel):
    status: Literal["success"] = "success"

    model: str

    x: float

    y: float

    analysis: VLMAnalysisResult

    performance: PerformanceInfo

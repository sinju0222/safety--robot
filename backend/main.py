from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(
    title="Safety Robot API",
    version="0.3.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# Models
# =========================================================

class Policy(BaseModel):
    noObjects: bool = False
    noBottle: bool = False
    noBox: bool = False


class Position(BaseModel):
    x: float
    y: float


class MapObject(BaseModel):
    id: int

    detectedClass: str

    name: str

    type: str

    position: Position

    zone: str

    status: str = "baseline"


class MapData(BaseModel):
    # empty
    # creating
    # object_setup
    # ready

    status: str = "empty"

    image: Optional[str] = None

    objects: List[MapObject] = []


class WorkplaceCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )


class ChangeEventCreate(BaseModel):
    objectType: str

    objectName: str

    zone: str

    x: float

    y: float

    distanceToCobot: Optional[float] = None


class ChangeEvent(BaseModel):
    id: int

    type: str = "NEW_OBJECT"

    objectType: str

    objectName: str

    zone: str

    position: dict

    distanceToCobot: Optional[float] = None

    policyViolation: bool = False

    distanceViolation: bool = False

    policyName: Optional[str] = None

    riskLevel: str = "NORMAL"

    action: str = "NONE"

    actionText: str = "조치 없음"

    detectedAt: str


class Patrol(BaseModel):
    id: int

    status: str

    startedAt: str

    endedAt: Optional[str] = None

    duration: int = 0

    changeCount: int = 0

    riskEventCount: int = 0

    events: List[ChangeEvent] = []

    returnedHome: bool = False


class Workplace(BaseModel):
    id: int

    name: str

    lastPatrol: Optional[str] = None

    map: MapData

    policies: Dict[str, Policy]

    patrols: List[Patrol] = []


# =========================================================
# 기본 데이터 생성
# =========================================================

def create_default_policies():
    return {
        "A": Policy(),
        "B": Policy(),
        "C": Policy(),
    }


def create_workplace(
    workplace_id: int,
    name: str,
):
    return Workplace(
        id=workplace_id,
        name=name,
        lastPatrol=None,
        map=MapData(),
        policies=create_default_policies(),
        patrols=[],
    )


# =========================================================
# Memory DB
#
# 나중에 PostgreSQL로 교체
# =========================================================

workplaces: Dict[int, Workplace] = {}

next_workplace_id = 1

next_patrol_id = 1

next_event_id = 1


# =========================================================
# 공통 함수
# =========================================================

def find_workplace(
    workplace_id: int,
):
    workplace = workplaces.get(
        workplace_id
    )

    if workplace is None:
        raise HTTPException(
            status_code=404,
            detail="작업장을 찾을 수 없습니다.",
        )

    return workplace


def find_patrol(
    workplace: Workplace,
    patrol_id: int,
):
    for patrol in workplace.patrols:

        if patrol.id == patrol_id:
            return patrol

    raise HTTPException(
        status_code=404,
        detail="순찰 기록을 찾을 수 없습니다.",
    )


# =========================================================
# Risk Engine
#
# 현재:
# Rule 기반 임시 Risk Engine
#
# 추후:
# ML Risk Engine으로 교체
# =========================================================

def evaluate_risk(
    workplace: Workplace,
    event_data: ChangeEventCreate,
):

    zone = event_data.zone

    policy = workplace.policies.get(
        zone
    )

    policy_violation = False

    distance_violation = False

    policy_name = None

    risk_level = "NORMAL"

    action = "NONE"

    action_text = "조치 없음"

    # -----------------------------------------------------
    # 구역 Safety Policy
    # -----------------------------------------------------

    if policy:

        if policy.noObjects:

            policy_violation = True

            policy_name = (
                "사물 배치 금지"
            )

        elif (
            event_data.objectType
            == "water_bottle"
            and policy.noBottle
        ):

            policy_violation = True

            policy_name = (
                "물병 금지"
            )

        elif (
            event_data.objectType
            == "box"
            and policy.noBox
        ):

            policy_violation = True

            policy_name = (
                "상자 금지"
            )

    # -----------------------------------------------------
    # 협동로봇 안전거리
    # -----------------------------------------------------

    if (
        event_data.objectType == "box"
        and
        event_data.distanceToCobot
        is not None
        and
        event_data.distanceToCobot <= 1.0
    ):

        distance_violation = True

        if policy_name is None:

            policy_name = (
                "협동로봇 1m 안전거리"
            )

    # -----------------------------------------------------
    # 최종 판단
    # -----------------------------------------------------

    dangerous = (
        policy_violation
        or
        distance_violation
    )

    if dangerous:

        risk_level = "HIGH"

        action = "COBOT_STOP"

        action_text = (
            "협동로봇 작업 중단"
        )

    return {
        "policyViolation":
            policy_violation,

        "distanceViolation":
            distance_violation,

        "policyName":
            policy_name,

        "riskLevel":
            risk_level,

        "action":
            action,

        "actionText":
            action_text,
    }


# =========================================================
# Health
# =========================================================

@app.get("/health")
def health_check():

    return {
        "status": "ok",
    }


# =========================================================
# Workplace
# =========================================================

@app.get("/workplaces")
def get_workplaces():

    return list(
        workplaces.values()
    )


@app.get(
    "/workplaces/{workplace_id}"
)
def get_workplace(
    workplace_id: int,
):

    return find_workplace(
        workplace_id
    )


@app.post(
    "/workplaces",
    status_code=201,
)
def create_new_workplace(
    data: WorkplaceCreate,
):

    global next_workplace_id

    workplace = create_workplace(
        next_workplace_id,
        data.name,
    )

    workplaces[
        next_workplace_id
    ] = workplace

    next_workplace_id += 1

    return workplace


# =========================================================
# MAP
# =========================================================


# ---------------------------------------------------------
# 지도 제작 시작
#
# empty → creating
# ---------------------------------------------------------

@app.post(
    "/workplaces/{workplace_id}/map/start"
)
def start_mapping(
    workplace_id: int,
):

    workplace = find_workplace(
        workplace_id
    )

    workplace.map.status = (
        "creating"
    )

    workplace.map.objects = []

    return {
        "message":
            "지도 제작을 시작했습니다.",

        "map":
            workplace.map,
    }


# ---------------------------------------------------------
# 지도 스캔 완료
#
# creating → object_setup
#
# 현재는 Mock 객체 생성
#
# 실제 하드웨어 연결 후:
#
# SLAM
# +
# RealSense
# +
# YOLO
# +
# TF
#
# 결과가 이 API에 들어오게 됨
# ---------------------------------------------------------

@app.post(
    "/workplaces/{workplace_id}/map/scan-complete"
)
def scan_complete(
    workplace_id: int,
):

    workplace = find_workplace(
        workplace_id
    )

    if (
        workplace.map.status
        != "creating"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "현재 지도 제작 중이 "
                "아닙니다."
            ),
        )

    # -----------------------------------------------------
    # MOCK 탐지 객체
    # -----------------------------------------------------

    mock_objects = [

        MapObject(
            id=1,

            detectedClass="robot",

            name="미지정 객체 1",

            type="cobot",

            position=Position(
                x=2.4,
                y=3.1,
            ),

            zone="A",

            status="baseline",
        ),

        MapObject(
            id=2,

            detectedClass="pallet",

            name="미지정 객체 2",

            type="storage",

            position=Position(
                x=4.2,
                y=1.8,
            ),

            zone="B",

            status="baseline",
        ),

        MapObject(
            id=3,

            detectedClass="workbench",

            name="미지정 객체 3",

            type="equipment",

            position=Position(
                x=1.5,
                y=4.0,
            ),

            zone="C",

            status="baseline",
        ),
    ]

    workplace.map.objects = (
        mock_objects
    )

    workplace.map.status = (
        "object_setup"
    )

    return {
        "message":
            "지도 스캔이 완료되었습니다.",

        "map":
            workplace.map,
    }


# ---------------------------------------------------------
# 탐지 객체 수정 / 저장
#
# 관리자가 이름 / 종류 / Zone 등을 수정한 결과
# ---------------------------------------------------------

@app.put(
    "/workplaces/{workplace_id}/map/objects"
)
def update_map_objects(
    workplace_id: int,
    objects: List[MapObject],
):

    workplace = find_workplace(
        workplace_id
    )

    if (
        workplace.map.status
        != "object_setup"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "현재 초기 사물 설정 "
                "단계가 아닙니다."
            ),
        )

    workplace.map.objects = (
        objects
    )

    return {
        "message":
            "지도 객체가 저장되었습니다.",

        "objects":
            workplace.map.objects,
    }


# ---------------------------------------------------------
# 초기 객체 설정 완료
#
# object_setup → ready
# ---------------------------------------------------------

@app.post(
    "/workplaces/{workplace_id}/map/complete"
)
def complete_mapping(
    workplace_id: int,
):

    workplace = find_workplace(
        workplace_id
    )

    if (
        workplace.map.status
        != "object_setup"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "초기 사물 설정이 "
                "완료되지 않았습니다."
            ),
        )

    workplace.map.status = (
        "ready"
    )

    return {
        "message":
            "지도 설정이 완료되었습니다.",

        "map":
            workplace.map,
    }


# ---------------------------------------------------------
# 지도 조회
# ---------------------------------------------------------

@app.get(
    "/workplaces/{workplace_id}/map"
)
def get_map(
    workplace_id: int,
):

    workplace = find_workplace(
        workplace_id
    )

    return workplace.map


# =========================================================
# Safety Policy
# =========================================================

@app.get(
    "/workplaces/{workplace_id}/policies"
)
def get_policies(
    workplace_id: int,
):

    workplace = find_workplace(
        workplace_id
    )

    return workplace.policies


@app.put(
    "/workplaces/{workplace_id}/policies"
)
def update_policies(
    workplace_id: int,
    policies: Dict[str, Policy],
):

    workplace = find_workplace(
        workplace_id
    )

    workplace.policies = (
        policies
    )

    return {
        "message":
            "안전정책이 저장되었습니다.",

        "policies":
            workplace.policies,
    }


# =========================================================
# Patrol Start
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/patrols/start",
    status_code=201,
)
def start_patrol(
    workplace_id: int,
):

    global next_patrol_id

    workplace = find_workplace(
        workplace_id
    )

    if (
        workplace.map.status
        != "ready"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "지도 설정이 "
                "완료되지 않았습니다."
            ),
        )

    patrol = Patrol(
        id=next_patrol_id,

        status="running",

        startedAt=(
            datetime.now().isoformat()
        ),

        events=[],
    )

    next_patrol_id += 1

    workplace.patrols.insert(
        0,
        patrol,
    )

    return patrol


# =========================================================
# Change Event
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/patrols/{patrol_id}/events",
    status_code=201,
)
def create_change_event(
    workplace_id: int,
    patrol_id: int,
    data: ChangeEventCreate,
):

    global next_event_id

    workplace = find_workplace(
        workplace_id
    )

    patrol = find_patrol(
        workplace,
        patrol_id,
    )

    if (
        patrol.status
        != "running"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "현재 진행 중인 "
                "순찰이 아닙니다."
            ),
        )

    risk_result = evaluate_risk(
        workplace,
        data,
    )

    event = ChangeEvent(
        id=next_event_id,

        type="NEW_OBJECT",

        objectType=
            data.objectType,

        objectName=
            data.objectName,

        zone=
            data.zone,

        position={
            "x": data.x,
            "y": data.y,
        },

        distanceToCobot=
            data.distanceToCobot,

        detectedAt=(
            datetime.now().isoformat()
        ),

        **risk_result,
    )

    next_event_id += 1

    patrol.events.insert(
        0,
        event,
    )

    patrol.changeCount = len(
        patrol.events
    )

    patrol.riskEventCount = len(
        [
            event
            for event
            in patrol.events
            if event.riskLevel
            == "HIGH"
        ]
    )

    return event


# =========================================================
# Return Home
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/patrols/{patrol_id}/return-home"
)
def return_home(
    workplace_id: int,
    patrol_id: int,
):

    workplace = find_workplace(
        workplace_id
    )

    patrol = find_patrol(
        workplace,
        patrol_id,
    )

    if (
        patrol.status
        != "running"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "순찰 중인 상태가 "
                "아닙니다."
            ),
        )

    patrol.status = (
        "returning"
    )

    return {
        "message":
            "원점 복귀를 시작합니다.",

        "patrol":
            patrol,
    }


# =========================================================
# Patrol Complete
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/patrols/{patrol_id}/complete"
)
def complete_patrol(
    workplace_id: int,
    patrol_id: int,
):

    workplace = find_workplace(
        workplace_id
    )

    patrol = find_patrol(
        workplace,
        patrol_id,
    )

    if patrol.status not in [
        "running",
        "returning",
    ]:

        raise HTTPException(
            status_code=400,
            detail=(
                "완료할 수 없는 "
                "순찰 상태입니다."
            ),
        )

    end_time = datetime.now()

    start_time = (
        datetime.fromisoformat(
            patrol.startedAt
        )
    )

    patrol.endedAt = (
        end_time.isoformat()
    )

    patrol.duration = int(
        (
            end_time
            - start_time
        ).total_seconds()
    )

    patrol.status = (
        "completed"
    )

    patrol.returnedHome = True

    workplace.lastPatrol = (
        end_time.strftime(
            "%Y.%m.%d"
        )
    )

    return patrol


# =========================================================
# Patrol List
# =========================================================

@app.get(
    "/workplaces/{workplace_id}/patrols"
)
def get_patrols(
    workplace_id: int,
):

    workplace = find_workplace(
        workplace_id
    )

    return workplace.patrols


@app.get(
    "/workplaces/{workplace_id}/patrols/{patrol_id}"
)
def get_patrol(
    workplace_id: int,
    patrol_id: int,
):

    workplace = find_workplace(
        workplace_id
    )

    return find_patrol(
        workplace,
        patrol_id,
    )
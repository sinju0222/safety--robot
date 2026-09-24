from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# =========================================================
# FastAPI
# =========================================================

app = FastAPI(
    title="Safety Robot API",
    version="0.5.0",
)

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
# Models - Common
# =========================================================

class Position(BaseModel):
    x: float
    y: float


# =========================================================
# Models - Zone
# =========================================================

class ZoneBounds(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class MapZone(BaseModel):
    id: int
    name: str
    type: str
    bounds: ZoneBounds


# =========================================================
# Models - Map Object
# =========================================================

class MapObject(BaseModel):
    id: int
    detectedClass: str
    name: str
    type: str
    position: Position

    zone: Optional[str] = None
    zoneId: Optional[int] = None

    status: str = "baseline"


# =========================================================
# Models - Map
# =========================================================

class MapData(BaseModel):
    status: str = "empty"

    image: Optional[str] = None

    zones: List[MapZone] = Field(
        default_factory=list
    )

    objects: List[MapObject] = Field(
        default_factory=list
    )


# =========================================================
# Models - Policy
# =========================================================

class ZonePolicy(BaseModel):
    noObjects: bool = False
    noBottle: bool = False
    noBox: bool = False


# zoneId를 key로 사용합니다.
#
# 예:
#
# {
#     "1": {
#         "noObjects": False,
#         "noBottle": True,
#         "noBox": False
#     },
#     "2": {
#         ...
#     }
# }

Policies = Dict[str, ZonePolicy]


# =========================================================
# Models - Workplace
# =========================================================

class WorkplaceCreate(BaseModel):
    name: str


class Workplace(BaseModel):
    id: int
    name: str

    lastPatrol: Optional[str] = None

    map: MapData = Field(
        default_factory=MapData
    )

    policies: Policies = Field(
        default_factory=dict
    )

    patrols: List[dict] = Field(
        default_factory=list
    )


# =========================================================
# Models - Patrol Event
# =========================================================

class PatrolEventCreate(BaseModel):
    objectType: str
    objectName: str

    zone: Optional[str] = None
    zoneId: Optional[int] = None

    x: float
    y: float

    distanceToCobot: Optional[float] = None


# =========================================================
# In-memory Database
# =========================================================

workplaces: Dict[int, Workplace] = {}

next_workplace_id = 1
next_patrol_id = 1
next_event_id = 1


# =========================================================
# Helper - Workplace
# =========================================================

def get_workplace(
    workplace_id: int,
) -> Workplace:

    workplace = workplaces.get(
        workplace_id
    )

    if workplace is None:
        raise HTTPException(
            status_code=404,
            detail="작업장을 찾을 수 없습니다.",
        )

    return workplace


# =========================================================
# Helper - Zone
# =========================================================

def normalize_bounds(
    bounds: ZoneBounds,
) -> ZoneBounds:

    return ZoneBounds(
        x1=min(
            bounds.x1,
            bounds.x2,
        ),
        y1=min(
            bounds.y1,
            bounds.y2,
        ),
        x2=max(
            bounds.x1,
            bounds.x2,
        ),
        y2=max(
            bounds.y1,
            bounds.y2,
        ),
    )


def find_zone_for_position(
    workplace: Workplace,
    x: float,
    y: float,
) -> Optional[MapZone]:
    """
    x, y 좌표가 어느 Semantic Zone에
    포함되는지 확인합니다.
    """

    for zone in workplace.map.zones:

        bounds = zone.bounds

        if (
            bounds.x1 <= x <= bounds.x2
            and
            bounds.y1 <= y <= bounds.y2
        ):
            return zone

    return None


# =========================================================
# Helper - Policy
# =========================================================

def get_zone_policy(
    workplace: Workplace,
    zone_id: Optional[int],
) -> Optional[ZonePolicy]:
    """
    Semantic Zone ID를 이용해
    해당 구역의 안전정책을 가져옵니다.
    """

    if zone_id is None:
        return None

    return workplace.policies.get(
        str(zone_id)
    )


# =========================================================
# Helper - Risk Engine
# =========================================================

def evaluate_risk(
    workplace: Workplace,
    event: PatrolEventCreate,
):
    """
    현재 임시 Rule 기반 Risk Engine.

    처리 흐름:

    변화 객체 좌표
        ↓
    Semantic Zone 판별
        ↓
    zoneId 확인
        ↓
    해당 Zone Policy 조회
        ↓
    정책 위반 검사
        ↓
    Semantic Rule 검사
        ↓
    Risk 결과 생성

    추후 ML Risk Engine으로 교체합니다.
    """

    violations = []

    # -----------------------------------------------------
    # 1. 좌표 기반 Semantic Zone 판별
    # -----------------------------------------------------

    semantic_zone = (
        find_zone_for_position(
            workplace,
            event.x,
            event.y,
        )
    )

    # -----------------------------------------------------
    # 2. Zone Policy 조회
    # -----------------------------------------------------

    zone_policy = None

    if semantic_zone:
        zone_policy = (
            get_zone_policy(
                workplace,
                semantic_zone.id,
            )
        )

    # -----------------------------------------------------
    # 3. 관리자 설정 Zone Policy 검사
    # -----------------------------------------------------

    if zone_policy:

        if zone_policy.noObjects:
            violations.append(
                "사물 배치 금지 정책 위반"
            )

        if (
            event.objectType
            == "water_bottle"
            and
            zone_policy.noBottle
        ):
            violations.append(
                "물병 금지 정책 위반"
            )

        if (
            event.objectType
            == "box"
            and
            zone_policy.noBox
        ):
            violations.append(
                "상자 금지 정책 위반"
            )

    # -----------------------------------------------------
    # 4. Semantic Zone 자체 안전 Rule
    # -----------------------------------------------------

    if semantic_zone:

        if (
            semantic_zone.type
            == "restricted_area"
        ):
            violations.append(
                "접근제한구역 변화 탐지"
            )

        elif (
            semantic_zone.type
            == "hazard_area"
        ):
            violations.append(
                "위험구역 변화 탐지"
            )

        elif (
            semantic_zone.type
            == "passage"
            and
            event.objectType
            in [
                "box",
                "pallet",
            ]
        ):
            violations.append(
                "통로 적치물 탐지"
            )

    # -----------------------------------------------------
    # 5. 협동로봇 근접 Rule
    # -----------------------------------------------------

    if (
        event.objectType == "box"
        and
        event.distanceToCobot
        is not None
        and
        event.distanceToCobot
        <= 1.0
    ):
        violations.append(
            "협동로봇 1m 이내 적치물"
        )

    # -----------------------------------------------------
    # 6. Risk Result
    # -----------------------------------------------------

    if violations:

        return {
            "riskScore": 90,

            "riskLevel":
                "HIGH",

            "policyName":
                ", ".join(
                    violations
                ),

            "action":
                "COBOT_STOP",

            "zoneId": (
                semantic_zone.id
                if semantic_zone
                else None
            ),

            "zoneName": (
                semantic_zone.name
                if semantic_zone
                else None
            ),

            "zoneType": (
                semantic_zone.type
                if semantic_zone
                else None
            ),
        }

    return {
        "riskScore": 0,

        "riskLevel":
            "NORMAL",

        "policyName":
            None,

        "action":
            None,

        "zoneId": (
            semantic_zone.id
            if semantic_zone
            else None
        ),

        "zoneName": (
            semantic_zone.name
            if semantic_zone
            else None
        ),

        "zoneType": (
            semantic_zone.type
            if semantic_zone
            else None
        ),
    }


# =========================================================
# Health
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "version": "0.5.0",
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
def get_workplace_api(
    workplace_id: int,
):

    return get_workplace(
        workplace_id
    )


@app.post("/workplaces")
def create_workplace(
    data: WorkplaceCreate,
):

    global next_workplace_id

    name = data.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="작업장 이름을 입력해주세요.",
        )

    workplace = Workplace(
        id=next_workplace_id,
        name=name,
    )

    workplaces[
        next_workplace_id
    ] = workplace

    next_workplace_id += 1

    return workplace


# =========================================================
# Map - Start
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/map/start"
)
def start_mapping(
    workplace_id: int,
):

    workplace = get_workplace(
        workplace_id
    )

    workplace.map = MapData(
        status="creating",
        image=None,
        zones=[],
        objects=[],
    )

    # 새 지도를 만들면 기존 Zone ID와
    # 정책 연결이 유효하지 않으므로 초기화합니다.
    workplace.policies = {}

    return {
        "message":
            "지도 생성을 시작했습니다.",

        "map":
            workplace.map,
    }


# =========================================================
# Map - Scan Complete
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/map/scan-complete"
)
def scan_complete(
    workplace_id: int,
):

    workplace = get_workplace(
        workplace_id
    )

    if (
        workplace.map.status
        != "creating"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "현재 지도 생성 상태가 "
                "아닙니다."
            ),
        )

    workplace.map.status = (
        "zone_setup"
    )

    workplace.map.image = None

    workplace.map.zones = []

    # -----------------------------------------------------
    # Mock Baseline Objects
    # -----------------------------------------------------

    workplace.map.objects = [
        MapObject(
            id=1,

            detectedClass=
                "robot",

            name=
                "미지정 객체 1",

            type=
                "cobot",

            position=Position(
                x=2.4,
                y=3.1,
            ),

            zone=None,
            zoneId=None,

            status=
                "baseline",
        ),

        MapObject(
            id=2,

            detectedClass=
                "pallet",

            name=
                "미지정 객체 2",

            type=
                "storage",

            position=Position(
                x=4.2,
                y=1.8,
            ),

            zone=None,
            zoneId=None,

            status=
                "baseline",
        ),

        MapObject(
            id=3,

            detectedClass=
                "workbench",

            name=
                "미지정 객체 3",

            type=
                "equipment",

            position=Position(
                x=1.5,
                y=4.0,
            ),

            zone=None,
            zoneId=None,

            status=
                "baseline",
        ),
    ]

    return {
        "message": (
            "지도 스캔이 완료되었습니다. "
            "구역을 설정해주세요."
        ),

        "map":
            workplace.map,
    }


# =========================================================
# Map - Save Zones
# =========================================================

@app.put(
    "/workplaces/{workplace_id}/map/zones"
)
def save_map_zones(
    workplace_id: int,
    zones: List[MapZone],
):

    workplace = get_workplace(
        workplace_id
    )

    if (
        workplace.map.status
        != "zone_setup"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "현재 구역 설정 단계가 "
                "아닙니다."
            ),
        )

    validated_zones = []

    used_ids = set()

    allowed_types = [
        "work_area",
        "passage",
        "storage",
        "empty_area",
        "hazard_area",
        "restricted_area",
    ]

    for zone in zones:

        if not zone.name.strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    "모든 구역의 이름을 "
                    "입력해주세요."
                ),
            )

        if zone.id in used_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    "구역 ID가 중복되었습니다."
                ),
            )

        used_ids.add(
            zone.id
        )

        if (
            zone.type
            not in allowed_types
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "지원하지 않는 "
                    f"구역 유형입니다: {zone.type}"
                ),
            )

        normalized_zone = (
            MapZone(
                id=zone.id,

                name=
                    zone.name.strip(),

                type=
                    zone.type,

                bounds=
                    normalize_bounds(
                        zone.bounds
                    ),
            )
        )

        validated_zones.append(
            normalized_zone
        )

    workplace.map.zones = (
        validated_zones
    )

    return {
        "message":
            "구역이 저장되었습니다.",

        "zones":
            workplace.map.zones,

        "map":
            workplace.map,
    }


# =========================================================
# Map - Complete Zone Setup
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/map/zones/complete"
)
def complete_zone_setup(
    workplace_id: int,
):

    workplace = get_workplace(
        workplace_id
    )

    if (
        workplace.map.status
        != "zone_setup"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "현재 구역 설정 단계가 "
                "아닙니다."
            ),
        )

    if (
        len(
            workplace.map.zones
        )
        == 0
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "최소 1개의 구역을 "
                "설정해주세요."
            ),
        )

    # -----------------------------------------------------
    # Baseline Object → Semantic Zone 연결
    # -----------------------------------------------------

    for obj in (
        workplace.map.objects
    ):

        zone = (
            find_zone_for_position(
                workplace,
                obj.position.x,
                obj.position.y,
            )
        )

        if zone:
            obj.zoneId = (
                zone.id
            )

            obj.zone = (
                zone.name
            )

        else:
            obj.zoneId = None
            obj.zone = None

    workplace.map.status = (
        "object_setup"
    )

    return {
        "message": (
            "구역 설정이 완료되었습니다. "
            "사물 설정 단계로 이동합니다."
        ),

        "map":
            workplace.map,
    }


# =========================================================
# Map - Save Objects
# =========================================================

@app.put(
    "/workplaces/{workplace_id}/map/objects"
)
def save_map_objects(
    workplace_id: int,
    objects: List[MapObject],
):

    workplace = get_workplace(
        workplace_id
    )

    if (
        workplace.map.status
        != "object_setup"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "현재 사물 설정 단계가 "
                "아닙니다."
            ),
        )

    updated_objects = []

    for obj in objects:

        if not obj.name.strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    "모든 사물의 이름을 "
                    "입력해주세요."
                ),
            )

        zone = (
            find_zone_for_position(
                workplace,
                obj.position.x,
                obj.position.y,
            )
        )

        if zone:
            obj.zoneId = (
                zone.id
            )

            obj.zone = (
                zone.name
            )

        else:
            obj.zoneId = None
            obj.zone = None

        updated_objects.append(
            obj
        )

    workplace.map.objects = (
        updated_objects
    )

    return {
        "message":
            "사물 정보가 저장되었습니다.",

        "objects":
            workplace.map.objects,

        "map":
            workplace.map,
    }


# =========================================================
# Map - Complete
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/map/complete"
)
def complete_mapping(
    workplace_id: int,
):

    workplace = get_workplace(
        workplace_id
    )

    if (
        workplace.map.status
        != "object_setup"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "사물 설정 단계가 "
                "완료되지 않았습니다."
            ),
        )

    workplace.map.status = (
        "ready"
    )

    # -----------------------------------------------------
    # Semantic Zone별 기본 정책 생성
    # -----------------------------------------------------

    policies = {}

    for zone in (
        workplace.map.zones
    ):
        policies[
            str(zone.id)
        ] = ZonePolicy()

    workplace.policies = (
        policies
    )

    return {
        "message": (
            "Baseline Semantic Map이 "
            "완성되었습니다."
        ),

        "map":
            workplace.map,

        "policies":
            workplace.policies,
    }


# =========================================================
# Map - Get
# =========================================================

@app.get(
    "/workplaces/{workplace_id}/map"
)
def get_map(
    workplace_id: int,
):

    workplace = get_workplace(
        workplace_id
    )

    return workplace.map


# =========================================================
# Policies - Get
# =========================================================

@app.get(
    "/workplaces/{workplace_id}/policies"
)
def get_policies(
    workplace_id: int,
):

    workplace = get_workplace(
        workplace_id
    )

    return workplace.policies


# =========================================================
# Policies - Update
# =========================================================

@app.put(
    "/workplaces/{workplace_id}/policies"
)
def update_policies(
    workplace_id: int,
    policies: Policies,
):

    workplace = get_workplace(
        workplace_id
    )

    # -----------------------------------------------------
    # 현재 지도에 실제 존재하는 Zone ID만 허용
    # -----------------------------------------------------

    valid_zone_ids = {
        str(zone.id)
        for zone
        in workplace.map.zones
    }

    received_zone_ids = set(
        policies.keys()
    )

    unknown_zone_ids = (
        received_zone_ids
        - valid_zone_ids
    )

    if unknown_zone_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "존재하지 않는 구역의 "
                "정책이 포함되어 있습니다: "
                + ", ".join(
                    sorted(
                        unknown_zone_ids
                    )
                )
            ),
        )

    # -----------------------------------------------------
    # 정책이 누락된 Zone에는 기본값 추가
    # -----------------------------------------------------

    completed_policies = {}

    for zone in (
        workplace.map.zones
    ):
        zone_key = str(
            zone.id
        )

        completed_policies[
            zone_key
        ] = (
            policies.get(
                zone_key,
                ZonePolicy(),
            )
        )

    workplace.policies = (
        completed_policies
    )

    return workplace.policies


# =========================================================
# Patrol - Start
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/patrols/start"
)
def start_patrol(
    workplace_id: int,
):

    global next_patrol_id

    workplace = get_workplace(
        workplace_id
    )

    if (
        workplace.map.status
        != "ready"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "완성된 지도가 필요합니다."
            ),
        )

    patrol = {
        "id":
            next_patrol_id,

        "status":
            "running",

        "startedAt":
            datetime.now().isoformat(),

        "completedAt":
            None,

        "duration":
            0,

        "changeCount":
            0,

        "riskEventCount":
            0,

        "events":
            [],
    }

    workplace.patrols.insert(
        0,
        patrol,
    )

    next_patrol_id += 1

    return patrol


# =========================================================
# Patrol - Event
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/patrols/{patrol_id}/events"
)
def create_patrol_event(
    workplace_id: int,
    patrol_id: int,
    data: PatrolEventCreate,
):

    global next_event_id

    workplace = get_workplace(
        workplace_id
    )

    patrol = next(
        (
            patrol
            for patrol
            in workplace.patrols
            if patrol["id"]
            == patrol_id
        ),
        None,
    )

    if patrol is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "순찰 기록을 "
                "찾을 수 없습니다."
            ),
        )

    if (
        patrol["status"]
        != "running"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "현재 진행 중인 "
                "순찰이 아닙니다."
            ),
        )

    risk = evaluate_risk(
        workplace,
        data,
    )

    event = {
        "id":
            next_event_id,

        "objectType":
            data.objectType,

        "objectName":
            data.objectName,

        "zone":
            risk["zoneName"],

        "zoneId":
            risk["zoneId"],

        "zoneType":
            risk["zoneType"],

        "position": {
            "x":
                data.x,

            "y":
                data.y,
        },

        "distanceToCobot":
            data.distanceToCobot,

        "riskScore":
            risk["riskScore"],

        "riskLevel":
            risk["riskLevel"],

        "policyName":
            risk["policyName"],

        "action":
            risk["action"],

        "createdAt":
            datetime.now().isoformat(),

        "image":
            None,
    }

    patrol[
        "events"
    ].insert(
        0,
        event,
    )

    patrol[
        "changeCount"
    ] = len(
        patrol["events"]
    )

    patrol[
        "riskEventCount"
    ] = len(
        [
            item
            for item
            in patrol[
                "events"
            ]
            if item[
                "riskLevel"
            ] == "HIGH"
        ]
    )

    next_event_id += 1

    return event


# =========================================================
# Patrol - Return Home
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/patrols/{patrol_id}/return-home"
)
def return_home(
    workplace_id: int,
    patrol_id: int,
):

    workplace = get_workplace(
        workplace_id
    )

    patrol = next(
        (
            patrol
            for patrol
            in workplace.patrols
            if patrol["id"]
            == patrol_id
        ),
        None,
    )

    if patrol is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "순찰 기록을 "
                "찾을 수 없습니다."
            ),
        )

    if (
        patrol["status"]
        != "running"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "현재 진행 중인 "
                "순찰이 아닙니다."
            ),
        )

    patrol["status"] = (
        "returning"
    )

    return {
        "message":
            "Home 위치로 복귀합니다.",

        "patrol":
            patrol,
    }


# =========================================================
# Patrol - Complete
# =========================================================

@app.post(
    "/workplaces/{workplace_id}/patrols/{patrol_id}/complete"
)
def complete_patrol(
    workplace_id: int,
    patrol_id: int,
):

    workplace = get_workplace(
        workplace_id
    )

    patrol = next(
        (
            patrol
            for patrol
            in workplace.patrols
            if patrol["id"]
            == patrol_id
        ),
        None,
    )

    if patrol is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "순찰 기록을 "
                "찾을 수 없습니다."
            ),
        )

    if (
        patrol["status"]
        not in [
            "running",
            "returning",
        ]
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "이미 완료된 "
                "순찰입니다."
            ),
        )

    completed_at = (
        datetime.now()
    )

    started_at = (
        datetime.fromisoformat(
            patrol[
                "startedAt"
            ]
        )
    )

    duration = int(
        (
            completed_at
            - started_at
        ).total_seconds()
    )

    patrol["status"] = (
        "completed"
    )

    patrol[
        "completedAt"
    ] = (
        completed_at.isoformat()
    )

    patrol[
        "duration"
    ] = duration

    workplace.lastPatrol = (
        completed_at.isoformat()
    )

    return patrol


# =========================================================
# Patrol - List
# =========================================================

@app.get(
    "/workplaces/{workplace_id}/patrols"
)
def get_patrols(
    workplace_id: int,
):

    workplace = get_workplace(
        workplace_id
    )

    return workplace.patrols


# =========================================================
# Patrol - Detail
# =========================================================

@app.get(
    "/workplaces/{workplace_id}/patrols/{patrol_id}"
)
def get_patrol_detail(
    workplace_id: int,
    patrol_id: int,
):

    workplace = get_workplace(
        workplace_id
    )

    patrol = next(
        (
            patrol
            for patrol
            in workplace.patrols
            if patrol["id"]
            == patrol_id
        ),
        None,
    )

    if patrol is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "순찰 기록을 "
                "찾을 수 없습니다."
            ),
        )

    return patrol
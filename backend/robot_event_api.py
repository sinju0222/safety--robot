"""Receive robot change events and analyze them with the VLM AI server."""

import json
import math
import os
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

import requests
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse


router = APIRouter(
    prefix="/api/robot-events",
    tags=["robot-events"],
)

DATA_DIR = (
    Path(__file__).resolve().parent
    / "robot_event_data"
)

IMAGE_DIR = (
    DATA_DIR
    / "images"
)

LATEST_FILE = (
    DATA_DIR
    / "latest.json"
)

HISTORY_FILE = (
    DATA_DIR
    / "events.jsonl"
)

HAZARDS_FILE = (
    DATA_DIR
    / "hazards.json"
)

IMAGE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

HAZARD_LOCK = threading.RLock()


# =========================================================
# AI Server
# =========================================================

AI_SERVER_URL = (
    os.environ.get(
        "SAFETY_AI_SERVER_URL",
        "http://127.0.0.1:8001",
    )
    .strip()
    .rstrip("/")
)

AI_TIMEOUT = 60.0


# =========================================================
# Hazard storage
# =========================================================

def load_hazards():
    if not HAZARDS_FILE.exists():
        return {}

    try:
        data = json.loads(
            HAZARDS_FILE.read_text(
                encoding="utf-8"
            )
        )
    except (
        json.JSONDecodeError,
        OSError,
    ):
        return {}

    return (
        data
        if isinstance(data, dict)
        else {}
    )


def save_hazards(hazards):
    tmp = (
        HAZARDS_FILE
        .with_suffix(".tmp")
    )

    tmp.write_text(
        json.dumps(
            hazards,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tmp.replace(
        HAZARDS_FILE
    )


# =========================================================
# Utility
# =========================================================

def safe_filename(value):
    return re.sub(
        r"[^a-zA-Z0-9._-]",
        "_",
        str(value),
    )[:150]


def valid_coordinate(value):
    return (
        isinstance(
            value,
            (int, float),
        )
        and not isinstance(
            value,
            bool,
        )
        and math.isfinite(
            value
        )
    )


async def save_upload(
    upload,
    destination,
):
    try:
        with destination.open(
            "wb"
        ) as output_file:
            shutil.copyfileobj(
                upload.file,
                output_file,
            )
    finally:
        await upload.close()


# =========================================================
# AI analysis
# =========================================================

def analyze_with_ai(
    baseline_path,
    current_path,
    x,
    y,
):
    url = (
        f"{AI_SERVER_URL}"
        "/analyze-risk"
    )

    with (
        Path(baseline_path).open(
            "rb"
        ) as baseline_file,
        Path(current_path).open(
            "rb"
        ) as current_file,
    ):
        response = requests.post(
            url,
            data={
                "x": str(x),
                "y": str(y),
            },
            files={
                "baseline_image": (
                    Path(
                        baseline_path
                    ).name,
                    baseline_file,
                    "image/jpeg",
                ),
                "current_image": (
                    Path(
                        current_path
                    ).name,
                    current_file,
                    "image/jpeg",
                ),
            },
            timeout=AI_TIMEOUT,
        )

    response.raise_for_status()

    result = response.json()

    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            "AI server returned "
            "invalid response."
        )

    analysis = result.get(
        "analysis"
    )

    if not isinstance(
        analysis,
        dict,
    ):
        raise ValueError(
            "AI response does not "
            "contain analysis."
        )

    return result


# =========================================================
# Receive robot event
# =========================================================

@router.post("")
async def receive_robot_event(
    event_json: str = Form(...),
    baseline_image: UploadFile = File(...),
    current_image: UploadFile = File(...),
):
    # -----------------------------------------------------
    # Event JSON
    # -----------------------------------------------------

    try:
        event = json.loads(
            event_json
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail=(
                "event_json 형식 오류"
            ),
        )

    if not isinstance(
        event,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "이벤트는 JSON 객체여야 합니다"
            ),
        )

    # -----------------------------------------------------
    # Event ID
    # -----------------------------------------------------

    event_id = str(
        event.get(
            "event_id"
        )
        or (
            "evt_"
            + datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S_%f"
            )
        )
    )

    event[
        "event_id"
    ] = event_id

    safe_event_id = (
        safe_filename(
            event_id
        )
    )

    # -----------------------------------------------------
    # Image filenames
    # -----------------------------------------------------

    baseline_original = (
        safe_filename(
            Path(
                baseline_image.filename
                or "baseline.jpg"
            ).name
        )
    )

    current_original = (
        safe_filename(
            Path(
                current_image.filename
                or "current.jpg"
            ).name
        )
    )

    baseline_saved_name = (
        f"{safe_event_id}"
        f"_baseline_"
        f"{baseline_original}"
    )

    current_saved_name = (
        f"{safe_event_id}"
        f"_current_"
        f"{current_original}"
    )

    baseline_path = (
        IMAGE_DIR
        / baseline_saved_name
    )

    current_path = (
        IMAGE_DIR
        / current_saved_name
    )

    # -----------------------------------------------------
    # Save images
    # -----------------------------------------------------

    try:
        await save_upload(
            baseline_image,
            baseline_path,
        )

        await save_upload(
            current_image,
            current_path,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "이미지 저장 실패: "
                f"{exc}"
            ),
        )

    event[
        "baselineImage"
    ] = baseline_saved_name

    event[
        "baselineImageUrl"
    ] = (
        "/api/robot-events/image/"
        f"{baseline_saved_name}"
    )

    event[
        "image"
    ] = current_saved_name

    event[
        "imageUrl"
    ] = (
        "/api/robot-events/image/"
        f"{current_saved_name}"
    )

    event[
        "currentImage"
    ] = current_saved_name

    event[
        "currentImageUrl"
    ] = event[
        "imageUrl"
    ]

    event[
        "receivedAt"
    ] = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    # -----------------------------------------------------
    # Coordinates
    # -----------------------------------------------------

    change = (
        event.get(
            "change"
        )
        or {}
    )

    x = change.get(
        "x"
    )

    y = change.get(
        "y"
    )

    # event_manager의 구조가
    # position 객체인 경우도 지원
    if (
        not valid_coordinate(x)
        or not valid_coordinate(y)
    ):
        position = (
            change.get(
                "position"
            )
            or {}
        )

        x = position.get(
            "x"
        )

        y = position.get(
            "y"
        )

    # 변화 위치가 없으면
    # robot_pose를 fallback으로 사용
    if (
        not valid_coordinate(x)
        or not valid_coordinate(y)
    ):
        robot_pose = (
            event.get(
                "robot_pose"
            )
            or {}
        )

        x = robot_pose.get(
            "x"
        )

        y = robot_pose.get(
            "y"
        )

    valid_coords = (
        valid_coordinate(x)
        and valid_coordinate(y)
    )

    # -----------------------------------------------------
    # VLM
    # -----------------------------------------------------

    if valid_coords:
        try:
            ai_result = (
                analyze_with_ai(
                    baseline_path=(
                        baseline_path
                    ),
                    current_path=(
                        current_path
                    ),
                    x=x,
                    y=y,
                )
            )

            event[
                "ai_status"
            ] = "success"

            event[
                "ai"
            ] = ai_result

            event[
                "analysis"
            ] = ai_result.get(
                "analysis"
            )

        except Exception as exc:
            event[
                "ai_status"
            ] = "error"

            event[
                "ai_error"
            ] = str(exc)

            event[
                "analysis"
            ] = None

    else:
        event[
            "ai_status"
        ] = "error"

        event[
            "ai_error"
        ] = (
            "Valid event coordinates "
            "not available."
        )

        event[
            "analysis"
        ] = None

    # -----------------------------------------------------
    # Compatibility risk field
    #
    # 기존 Frontend가 event.risk를 참조해도
    # 깨지지 않도록 VLM 결과에서 생성한다.
    # -----------------------------------------------------

    analysis = (
        event.get(
            "analysis"
        )
        or {}
    )

    risk_assessment = (
        analysis.get(
            "risk_assessment"
        )
        or {}
    )

    situation = (
        analysis.get(
            "situation"
        )
        or {}
    )

    recommended_actions = (
        analysis.get(
            "recommended_actions"
        )
        or []
    )

    risk_level = (
        risk_assessment.get(
            "risk_level"
        )
    )

    hazard_present = (
        risk_assessment.get(
            "hazard_present"
        )
        is True
    )

    hazard_types = (
        risk_assessment.get(
            "hazard_types"
        )
        or []
    )

    summary = (
        situation.get(
            "summary"
        )
        or ""
    )

    event[
        "risk"
    ] = {
        "is_danger": (
            risk_level
            in {
                "MEDIUM",
                "HIGH",
            }
        ),
        "risk_level":
            risk_level,
        "hazard_present":
            hazard_present,
        "hazard_types":
            hazard_types,
        "reason":
            summary
            or None,
    }

    # -----------------------------------------------------
    # Save latest/history
    # -----------------------------------------------------

    LATEST_FILE.write_text(
        json.dumps(
            event,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with HISTORY_FILE.open(
        "a",
        encoding="utf-8",
    ) as history_file:
        history_file.write(
            json.dumps(
                event,
                ensure_ascii=False,
            )
            + "\n"
        )

    # -----------------------------------------------------
    # Dashboard change marker
    #
    # LiDAR에서 이미 변화가 확정되어 넘어온 이벤트이므로
    # 위험도와 관계없이 지도에 ⚠️를 표시한다.
    # -----------------------------------------------------

    if valid_coords:
        with HAZARD_LOCK:
            hazards = (
                load_hazards()
            )

            # 같은 event_id가 retry되어도
            # acknowledged 이벤트를 다시 활성화하지 않는다.
            if event_id not in hazards:
                hazards[
                    event_id
                ] = {
                    "event_id":
                        event_id,

                    "workplace_id":
                        event.get(
                            "workplace_id"
                        ),

                    "x":
                        float(x),

                    "y":
                        float(y),

                    "change_type":
                        (
                            analysis
                            .get(
                                "change",
                                {},
                            )
                            .get(
                                "change_type"
                            )
                            or change.get(
                                "type"
                            )
                            or change.get(
                                "event_type"
                            )
                        ),

                    "risk_level":
                        risk_level,

                    "hazard_present":
                        hazard_present,

                    "hazard_types":
                        hazard_types,

                    "reason":
                        summary
                        or (
                            "환경 변화가 "
                            "감지되었습니다."
                        ),

                    "situation":
                        summary,

                    "recommended_actions":
                        recommended_actions,

                    "baselineImageUrl":
                        event[
                            "baselineImageUrl"
                        ],

                    "imageUrl":
                        event[
                            "imageUrl"
                        ],

                    "currentImageUrl":
                        event[
                            "currentImageUrl"
                        ],

                    "ai_status":
                        event[
                            "ai_status"
                        ],

                    "timestamp":
                        event[
                            "receivedAt"
                        ],

                    "status":
                        "active",

                    "acknowledged_at":
                        None,
                }

                save_hazards(
                    hazards
                )

    return event


# =========================================================
# Latest
# =========================================================

@router.get("/latest")
def get_latest_event():
    if not LATEST_FILE.exists():
        return {
            "event": None
        }

    return {
        "event": json.loads(
            LATEST_FILE.read_text(
                encoding="utf-8"
            )
        )
    }


# =========================================================
# Active hazards / change markers
# =========================================================

@router.get("/hazards")
def get_active_hazards(
    workplace_id: int | None = Query(
        default=None,
        ge=1,
    ),
):
    with HAZARD_LOCK:
        hazards = (
            load_hazards()
        )

    active = [
        hazard
        for hazard
        in hazards.values()
        if (
            hazard.get(
                "status"
            )
            == "active"
        )
        and (
            workplace_id is None
            or hazard.get(
                "workplace_id"
            )
            == workplace_id
        )
    ]

    return {
        "hazards": active
    }


# =========================================================
# Acknowledge
# =========================================================

@router.post(
    "/hazards/{event_id}/ack"
)
def acknowledge_hazard(
    event_id: str
):
    with HAZARD_LOCK:
        hazards = (
            load_hazards()
        )

        if event_id not in hazards:
            raise HTTPException(
                status_code=404,
                detail=(
                    "위험 이벤트 없음"
                ),
            )

        hazard = hazards[
            event_id
        ]

        if (
            hazard.get(
                "status"
            )
            != "acknowledged"
        ):
            hazard[
                "status"
            ] = "acknowledged"

            hazard[
                "acknowledged_at"
            ] = (
                datetime.now()
                .astimezone()
                .isoformat()
            )

            save_hazards(
                hazards
            )

    return {
        "success": True,
        "hazard": hazard,
    }


# =========================================================
# Images
# =========================================================

@router.get(
    "/image/{filename}"
)
def get_event_image(
    filename: str
):
    safe_name = (
        Path(filename).name
    )

    if safe_name != filename:
        raise HTTPException(
            status_code=400,
            detail="잘못된 파일명",
        )

    path = (
        IMAGE_DIR
        / safe_name
    )

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="이미지 없음",
        )

    return FileResponse(
        path
    )
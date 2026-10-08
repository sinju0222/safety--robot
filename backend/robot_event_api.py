"""Receive RealSense events, classify policy risks, track review status."""
import json
import math
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/robot-events", tags=["robot-events"])
DATA_DIR = Path(__file__).resolve().parent / "robot_event_data"
IMAGE_DIR = DATA_DIR / "images"
LATEST_FILE = DATA_DIR / "latest.json"
HISTORY_FILE = DATA_DIR / "events.jsonl"
HAZARDS_FILE = DATA_DIR / "hazards.json"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
HAZARD_LOCK = threading.RLock()


def load_hazards():
    if not HAZARDS_FILE.exists():
        return {}
    data = json.loads(HAZARDS_FILE.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def save_hazards(hazards):
    tmp = HAZARDS_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(hazards, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(HAZARDS_FILE)


def safe_filename(value):
    return re.sub(r"[^a-zA-Z0-9._-]", "_", str(value))[:150]


@router.post("")
async def receive_robot_event(
    request: Request,
    event_json: str = Form(...),
    image: UploadFile = File(...),
):
    try:
        event = json.loads(event_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="event_json 형식 오류")
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="이벤트는 JSON 객체여야 합니다")

    # Preserve an externally provided ID only as data; sanitize filename separately.
    event_id = str(event.get("event_id") or (
        "evt_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    ))
    event["event_id"] = event_id
    original_name = safe_filename(Path(image.filename or "change.jpg").name)
    saved_name = f"{safe_filename(event_id)}_{original_name}"
    image_path = IMAGE_DIR / saved_name

    # Never trust a Pi-supplied risk flag; evaluate using backend workplace policies.
    evaluator = getattr(request.app.state, "robot_risk_evaluator", None)
    event["risk"] = evaluator(event) if callable(evaluator) else {
        "is_danger": False, "reason": None
    }

    try:
        with image_path.open("wb") as f:
            shutil.copyfileobj(image.file, f)
    finally:
        await image.close()

    event["image"] = saved_name
    event["imageUrl"] = f"/api/robot-events/image/{saved_name}"
    event["receivedAt"] = datetime.now().astimezone().isoformat()
    LATEST_FILE.write_text(
        json.dumps(event, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    risk = event["risk"]
    change = event.get("change") or {}
    x, y = change.get("x"), change.get("y")
    valid_coords = (
        isinstance(x, (int, float)) and not isinstance(x, bool)
        and isinstance(y, (int, float)) and not isinstance(y, bool)
        and math.isfinite(x) and math.isfinite(y)
    )
    if risk.get("is_danger") is True and valid_coords:
        with HAZARD_LOCK:
            hazards = load_hazards()
            # An acknowledged ID is never reactivated by a retry.
            if event_id not in hazards:
                hazards[event_id] = {
                    "event_id": event_id,
                    "workplace_id": event.get("workplace_id"),
                    "x": x, "y": y,
                    "change_type": change.get("type"),
                    "reason": risk.get("reason") or "위험 정책 위반",
                    "zoneId": risk.get("zoneId"),
                    "zoneName": risk.get("zoneName"),
                    "label": risk.get("label"),
                    "confidence": risk.get("confidence"),
                    "imageUrl": event["imageUrl"],
                    "timestamp": event["receivedAt"],
                    "status": "active",
                    "acknowledged_at": None,
                }
                save_hazards(hazards)
    return event


@router.get("/latest")
def get_latest_event():
    if not LATEST_FILE.exists():
        return {"event": None}
    return {"event": json.loads(LATEST_FILE.read_text(encoding="utf-8"))}


@router.get("/hazards")
def get_active_hazards(workplace_id: int | None = Query(default=None, ge=1)):
    with HAZARD_LOCK:
        hazards = load_hazards()
    active = [
        h for h in hazards.values()
        if h.get("status") == "active"
        and (workplace_id is None or h.get("workplace_id") == workplace_id)
    ]
    return {"hazards": active}


@router.post("/hazards/{event_id}/ack")
def acknowledge_hazard(event_id: str):
    # Demo only. Production: require verified admin authentication/authorization.
    with HAZARD_LOCK:
        hazards = load_hazards()
        if event_id not in hazards:
            raise HTTPException(status_code=404, detail="위험 이벤트 없음")
        hazard = hazards[event_id]
        if hazard.get("status") != "acknowledged":
            hazard["status"] = "acknowledged"
            hazard["acknowledged_at"] = datetime.now().astimezone().isoformat()
            save_hazards(hazards)
    return {"success": True, "hazard": hazard}


@router.get("/image/{filename}")
def get_event_image(filename: str):
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="잘못된 파일명")
    path = IMAGE_DIR / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="이미지 없음")
    return FileResponse(path)

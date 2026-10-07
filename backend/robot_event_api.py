import json
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse


router = APIRouter(
    prefix="/api/robot-events",
    tags=["robot-events"],
)


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = (
    BASE_DIR
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


IMAGE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


@router.post("")
async def receive_robot_event(
    event_json: str = Form(...),
    image: UploadFile = File(...),
):

    try:
        event = json.loads(
            event_json
        )

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="event_json 형식 오류",
        )

    event_id = event.get(
        "event_id"
    )

    if not event_id:
        event_id = (
            "evt_"
            + datetime.now().strftime(
                "%Y%m%d_%H%M%S_%f"
            )
        )

    original_name = Path(
        image.filename
        or "change.jpg"
    ).name

    saved_name = (
        f"{event_id}_"
        f"{original_name}"
    )

    image_path = (
        IMAGE_DIR
        / saved_name
    )

    try:
        with image_path.open(
            "wb"
        ) as file:

            shutil.copyfileobj(
                image.file,
                file,
            )

    finally:
        await image.close()

    event["image"] = (
        saved_name
    )

    event["imageUrl"] = (
        "/api/robot-events/"
        f"image/{saved_name}"
    )

    event["receivedAt"] = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

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
    ) as file:

        file.write(
            json.dumps(
                event,
                ensure_ascii=False,
            )
            + "\n"
        )

    return event


@router.get("/latest")
def get_latest_event():

    if not LATEST_FILE.exists():

        return {
            "event": None
        }

    event = json.loads(
        LATEST_FILE.read_text(
            encoding="utf-8"
        )
    )

    return {
        "event": event
    }


@router.get(
    "/image/{filename}"
)
def get_event_image(
    filename: str
):

    safe_name = Path(
        filename
    ).name

    if safe_name != filename:

        raise HTTPException(
            status_code=400,
            detail="잘못된 파일명",
        )

    image_path = (
        IMAGE_DIR
        / safe_name
    )

    if not image_path.exists():

        raise HTTPException(
            status_code=404,
            detail="이미지 없음",
        )

    return FileResponse(
        image_path
    )
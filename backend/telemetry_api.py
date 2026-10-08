"""Raspberry Pi -> Windows map and robot-pose telemetry (one folder per workplace)."""
import json
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])
DATA_ROOT = Path(__file__).resolve().parent / "robot_data"
WRITE_LOCK = threading.Lock()


class MapUpload(BaseModel):
    workplace_id: int = Field(ge=1)
    width: int = Field(gt=0, le=2000)
    height: int = Field(gt=0, le=2000)
    resolution: float = Field(gt=0)
    origin: dict[str, Any]
    data: list[int]


class PoseUpload(BaseModel):
    workplace_id: int = Field(ge=1)
    x: float
    y: float
    yaw: float


def workspace_dir(workplace_id: int) -> Path:
    if workplace_id < 1:
        raise HTTPException(status_code=400, detail="잘못된 작업장 ID")
    return DATA_ROOT / str(workplace_id)


def write_json_atomic(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


@router.post("/map")
def receive_map(payload: MapUpload):
    if payload.width * payload.height > 2_000_000:
        raise HTTPException(status_code=413, detail="지도가 너무 큽니다")
    if len(payload.data) != payload.width * payload.height:
        raise HTTPException(status_code=400, detail="지도 셀 개수 오류")
    origin = payload.origin
    try:
        ox, oy = float(origin["x"]), float(origin["y"])
        yaw = float(origin.get("yaw", 0.0))
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=400, detail="origin 형식 오류")
    if not all(map(math.isfinite, (ox, oy, yaw, payload.resolution))):
        raise HTTPException(status_code=400, detail="좌표 값 오류")
    directory = workspace_dir(payload.workplace_id)
    directory.mkdir(parents=True, exist_ok=True)
    values = np.asarray(payload.data, dtype=np.int16)
    if np.any((values < -1) | (values > 100)):
        raise HTTPException(status_code=400, detail="지도 점유 값 오류")
    grid = values.reshape(payload.height, payload.width)
    meta = {
        "type": "map", "width": payload.width,
        "height": payload.height, "resolution": payload.resolution,
        "origin": {"x": ox, "y": oy, "yaw": yaw},
        "workplace_id": payload.workplace_id,
    }
    with WRITE_LOCK:
        temp_grid = directory / "slam_map.tmp"
        with temp_grid.open("wb") as f:
            np.save(f, grid)
        temp_grid.replace(directory / "slam_map.npy")
        write_json_atomic(directory / "slam_map_meta.json", meta)
    return {"saved": True, "workplace_id": payload.workplace_id}


@router.post("/pose")
def receive_robot_pose(payload: PoseUpload):
    if not all(map(math.isfinite, (payload.x, payload.y, payload.yaw))):
        raise HTTPException(status_code=400, detail="로봇 좌표 값 오류")
    directory = workspace_dir(payload.workplace_id)
    with WRITE_LOCK:
        write_json_atomic(directory / "robot_pose.json", {
            "x": payload.x, "y": payload.y, "yaw": payload.yaw,
            "receivedAt": datetime.now(timezone.utc).isoformat(),
            "workplace_id": payload.workplace_id,
        })
    return {"saved": True}

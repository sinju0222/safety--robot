"""Serve each workplace's actual ROS2 /map and current robot position.

The map and metadata are uploaded by telemetry_api.py. No static demo map
is used for robot telemetry, avoiding incorrect coordinates in the dashboard.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect

DATA_ROOT = Path(__file__).resolve().parent / "robot_data"
POSE_MAX_AGE_SECONDS = 5.0


def load_slam_map(workplace_id: int):
    if int(workplace_id) < 1:
        raise ValueError("Invalid workplace_id")

    directory = DATA_ROOT / str(int(workplace_id))
    grid_path = directory / "slam_map.npy"
    metadata_path = directory / "slam_map_meta.json"
    if not grid_path.is_file() or not metadata_path.is_file():
        return None

    with metadata_path.open(encoding="utf-8") as file:
        metadata = json.load(file)
    grid = np.load(grid_path, allow_pickle=False)
    if grid.ndim != 2:
        raise ValueError("SLAM map must be 2D")
    height, width = grid.shape
    if width != int(metadata["width"]) or height != int(metadata["height"]):
        raise ValueError("SLAM map grid/metadata dimensions differ")
    if int(metadata.get("workplace_id", workplace_id)) != int(workplace_id):
        raise ValueError("Wrong workplace map metadata")

    result = {
        "type": "map",
        "workplace_id": int(workplace_id),
        "width": width,
        "height": height,
        "resolution": float(metadata["resolution"]),
        "origin": metadata["origin"],
        "data": grid.reshape(-1).tolist(),
    }

    pose_path = directory / "robot_pose.json"
    if pose_path.is_file():
        try:
            with pose_path.open(encoding="utf-8") as file:
                pose = json.load(file)
            received_at = datetime.fromisoformat(pose["receivedAt"])
            if received_at.tzinfo is None:
                received_at = received_at.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - received_at).total_seconds()
            if 0 <= age <= POSE_MAX_AGE_SECONDS:
                result["robot"] = {
                    "x": float(pose["x"]),
                    "y": float(pose["y"]),
                    "yaw": float(pose.get("yaw", 0.0)),
                }
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            pass
    return result


async def send_map(websocket: WebSocket, workplace_id: int = 1):
    while True:
        try:
            map_data = load_slam_map(workplace_id)
            if map_data is None:
                await websocket.send_json({
                    "type": "waiting",
                    "message": "Waiting for robot map upload",
                    "workplace_id": workplace_id,
                })
            else:
                await websocket.send_json(map_data)
            await asyncio.sleep(1)
        except WebSocketDisconnect:
            break
        except Exception as exc:
            # Keep the connection alive while an upload is in progress.
            print(f"Map WebSocket workplace {workplace_id}: {exc}")
            try:
                await websocket.send_json({
                    "type": "waiting",
                    "message": "Map data temporarily unavailable",
                    "workplace_id": workplace_id,
                })
                await asyncio.sleep(1)
            except Exception:
                break

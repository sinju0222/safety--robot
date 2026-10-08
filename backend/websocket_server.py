
import asyncio
import json
from pathlib import Path

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect


# 백엔드 내부의 robot_data 폴더
DATA_PATH = Path(__file__).resolve().parent / "robot_data"


def load_slam_map():

    # 실제 지도 데이터
    grid = np.load(
        DATA_PATH / "slam_map.npy",
        allow_pickle=False,
    )

    # 지도 좌표 정보
    with (DATA_PATH / "slam_map.json").open(
        "r",
        encoding="utf-8",
    ) as file:
        metadata = json.load(file)

    height, width = grid.shape

    # 두 파일이 같은 지도인지 확인
    if (
        width != int(metadata["width"])
        or height != int(metadata["height"])
    ):
        raise ValueError(
            "slam_map.npy와 slam_map.json의 "
            "지도 크기가 일치하지 않습니다."
        )

    origin = metadata["origin"]

    return {
        "type": "map",

        "width": width,
        "height": height,

        "resolution": float(
            metadata["resolution"]
        ),

        "origin": {
            "x": float(origin["x"]),
            "y": float(origin["y"]),
        },

        "data": grid.flatten().tolist(),
    }


async def send_map(websocket: WebSocket):

    while True:
        try:
            map_data = load_slam_map()

            await websocket.send_json(
                map_data
            )

            await asyncio.sleep(1)

        except WebSocketDisconnect:
            break

        except Exception as e:
            print(
                "Websocket error:",
                e
            )
            break

import asyncio
import json
import numpy as np
import os

from fastapi import WebSocket


DATA_PATH = "./robot_data"



def load_slam_map():

    file_path = os.path.join(
        DATA_PATH,
        "slam_map.npy"
    )


    grid = np.load(file_path)


    return {

        "type": "map",

        "width": int(grid.shape[1]),

        "height": int(grid.shape[0]),

        "data": grid.flatten().tolist()

    }



async def send_map(websocket: WebSocket):


    while True:


        try:

            map_data = load_slam_map()


            await websocket.send_json(
                map_data
            )


            # 테스트용 1초 주기
            await asyncio.sleep(1)



        except Exception as e:

            print(
                "Websocket error:",
                e
            )

            break
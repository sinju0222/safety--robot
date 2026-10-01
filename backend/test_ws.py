import asyncio
import websockets


async def test():

    uri = "ws://127.0.0.1:8000/ws/map"

    async with websockets.connect(uri) as ws:

        while True:

            data = await ws.recv()

            print(data[:200])


asyncio.run(test())
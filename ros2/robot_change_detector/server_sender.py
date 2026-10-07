import json
import queue
import threading
import time
from pathlib import Path

import requests


class ServerSender:
    def __init__(
        self,
        backend_url,
        timeout=5.0,
        retry_count=3,
        retry_delay=2.0,
    ):
        self.backend_url = backend_url.rstrip("/")
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay

        self.queue = queue.Queue()

        self.worker = threading.Thread(
            target=self._worker_loop,
            daemon=True,
        )

        self.worker.start()

    @property
    def enabled(self):
        return bool(self.backend_url)

    def send_event(self, event, image_path):
        if not self.enabled:
            return

        self.queue.put(
            {
                "event": event,
                "image_path": image_path,
            }
        )

    def _worker_loop(self):
        while True:
            data = self.queue.get()

            event = data["event"]
            image_path = data["image_path"]

            success = False

            for attempt in range(self.retry_count):
                try:
                    self._upload(
                        event,
                        image_path,
                    )

                    success = True
                    break

                except Exception as e:
                    print(
                        f"[SERVER] upload failed "
                        f"{attempt + 1}/{self.retry_count}: {e}"
                    )

                    time.sleep(
                        self.retry_delay
                    )

            if success:
                print(
                    "[SERVER] event uploaded"
                )

            self.queue.task_done()

    def _upload(
        self,
        event,
        image_path,
    ):
        image_path = Path(
            image_path
        )

        url = (
            f"{self.backend_url}"
            "/api/robot-events"
        )

        with image_path.open(
            "rb"
        ) as image_file:

            response = requests.post(
                url,
                data={
                    "event_json":
                        json.dumps(
                            event,
                            ensure_ascii=False,
                        )
                },
                files={
                    "image": (
                        image_path.name,
                        image_file,
                        "image/jpeg",
                    )
                },
                timeout=self.timeout,
            )

        response.raise_for_status()
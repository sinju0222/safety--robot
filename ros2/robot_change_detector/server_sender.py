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
        timeout=30.0,
        retry_count=3,
        retry_delay=2.0,
    ):
        self.backend_url = (
            backend_url.rstrip("/")
        )
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
        return bool(
            self.backend_url
        )

    def send_event(
        self,
        event,
        baseline_image_path,
        current_image_path,
    ):
        if not self.enabled:
            return

        self.queue.put(
            {
                "event": event,
                "baseline_image_path":
                    baseline_image_path,
                "current_image_path":
                    current_image_path,
            }
        )

    def _worker_loop(self):
        while True:
            data = self.queue.get()

            try:
                success = False

                for attempt in range(
                    self.retry_count
                ):
                    try:
                        self._upload(
                            event=data[
                                "event"
                            ],
                            baseline_image_path=data[
                                "baseline_image_path"
                            ],
                            current_image_path=data[
                                "current_image_path"
                            ],
                        )

                        success = True
                        break

                    except Exception as exc:
                        print(
                            "[SERVER] upload failed "
                            f"{attempt + 1}/"
                            f"{self.retry_count}: "
                            f"{exc}"
                        )

                        if (
                            attempt + 1
                            < self.retry_count
                        ):
                            time.sleep(
                                self.retry_delay
                            )

                if success:
                    print(
                        "[SERVER] "
                        "event uploaded"
                    )

            finally:
                self.queue.task_done()

    def _upload(
        self,
        event,
        baseline_image_path,
        current_image_path,
    ):
        baseline_image_path = Path(
            baseline_image_path
        )
        current_image_path = Path(
            current_image_path
        )

        if not baseline_image_path.exists():
            raise FileNotFoundError(
                "Baseline image not found: "
                f"{baseline_image_path}"
            )

        if not current_image_path.exists():
            raise FileNotFoundError(
                "Current image not found: "
                f"{current_image_path}"
            )

        url = (
            f"{self.backend_url}"
            "/api/robot-events"
        )

        with (
            baseline_image_path.open(
                "rb"
            ) as baseline_file,
            current_image_path.open(
                "rb"
            ) as current_file,
        ):
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
                    "baseline_image": (
                        baseline_image_path.name,
                        baseline_file,
                        "image/jpeg",
                    ),
                    "current_image": (
                        current_image_path.name,
                        current_file,
                        "image/jpeg",
                    ),
                },
                timeout=self.timeout,
            )

        response.raise_for_status()
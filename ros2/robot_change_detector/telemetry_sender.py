"""Non-blocking upload of ROS occupancy map and ongoing robot pose to FastAPI."""
import math
import threading
import time
import requests


class TelemetrySender:
    def __init__(self, backend_url, workplace_id=1):
        self.backend_url = backend_url.rstrip("/")
        self.workplace_id = int(workplace_id)
        self._lock = threading.Lock()
        self._map_payload = None
        self._map_uploaded = False
        self._pose = None
        self._stop = threading.Event()
        if self.enabled:
            self._worker = threading.Thread(target=self._loop, daemon=True)
            self._worker.start()

    @property
    def enabled(self):
        return bool(self.backend_url)

    def update_map(self, msg):
        q = msg.info.origin.orientation
        yaw = math.atan2(
            2 * (q.w * q.z + q.x * q.y),
            1 - 2 * (q.y * q.y + q.z * q.z),
        )
        payload = {
            "workplace_id": self.workplace_id,
            "width": int(msg.info.width),
            "height": int(msg.info.height),
            "resolution": float(msg.info.resolution),
            "origin": {
                "x": float(msg.info.origin.position.x),
                "y": float(msg.info.origin.position.y),
                "yaw": float(yaw),
            },
            "data": list(msg.data),
        }
        with self._lock:
            self._map_payload = payload
            self._map_uploaded = False

    def update_pose(self, pose):
        if pose is None:
            return
        with self._lock:
            self._pose = {
                "workplace_id": self.workplace_id,
                "x": float(pose["x"]),
                "y": float(pose["y"]),
                "yaw": float(pose["yaw"]),
            }

    def _loop(self):
        session = requests.Session()
        while not self._stop.is_set():
            with self._lock:
                map_payload = self._map_payload if not self._map_uploaded else None
                pose = self._pose
            if map_payload is not None:
                try:
                    res = session.post(
                        f"{self.backend_url}/api/telemetry/map",
                        json=map_payload, timeout=6,
                    )
                    res.raise_for_status()
                    with self._lock:
                        if map_payload is self._map_payload:
                            self._map_uploaded = True
                    print("[TELEMETRY] map uploaded")
                except requests.RequestException as exc:
                    print("[TELEMETRY] map upload failed:", exc)
            if pose is not None:
                try:
                    res = session.post(
                        f"{self.backend_url}/api/telemetry/pose",
                        json=pose, timeout=3,
                    )
                    res.raise_for_status()
                except requests.RequestException as exc:
                    print("[TELEMETRY] pose upload failed:", exc)
            self._stop.wait(1.0)

    def close(self):
        self._stop.set()

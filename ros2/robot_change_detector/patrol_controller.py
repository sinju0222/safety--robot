import json
import math
import os
import threading
import time
import uuid

from http.server import (
    BaseHTTPRequestHandler,
    ThreadingHTTPServer,
)
from pathlib import Path

import requests
import rclpy

from geometry_msgs.msg import (
    PoseStamped,
    PoseWithCovarianceStamped,
)
from nav2_simple_commander.robot_navigator import (
    BasicNavigator,
    TaskResult,
)
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String


# =========================================================
# Configuration
# =========================================================

PACKAGE_DIR = Path(__file__).resolve().parent

OUTPUT_DIR = Path(
    os.getenv(
        "SAFETY_OUTPUT_DIR",
        str(Path.home() / "robot_change_output"),
    )
).expanduser()

WAYPOINT_FILE = Path(
    os.getenv(
        "SAFETY_WAYPOINT_FILE",
        str(PACKAGE_DIR / "data" / "waypoints.json"),
    )
).expanduser()

PATROL_MODE_FILE = Path(
    os.getenv(
        "SAFETY_PATROL_MODE_FILE",
        str(OUTPUT_DIR / "patrol_mode.json"),
    )
).expanduser()

BASELINE_METADATA_FILE = Path(
    os.getenv(
        "SAFETY_BASELINE_IMAGE_METADATA",
        str(OUTPUT_DIR / "baseline_images.json"),
    )
).expanduser()

BASELINE_COMPLETE_FILE = Path(
    os.getenv(
        "SAFETY_BASELINE_COMPLETE_FILE",
        str(OUTPUT_DIR / "baseline_complete.json"),
    )
).expanduser()

BACKEND_URL = os.getenv(
    "SAFETY_BACKEND_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

COMMAND_HOST = os.getenv(
    "SAFETY_PATROL_HOST",
    "0.0.0.0",
)

COMMAND_PORT = int(
    os.getenv(
        "SAFETY_PATROL_PORT",
        "8090",
    )
)

CAPTURE_TIMEOUT = float(
    os.getenv(
        "SAFETY_WAYPOINT_CAPTURE_TIMEOUT",
        "15",
    )
)

ARRIVAL_SETTLE_SECONDS = float(
    os.getenv(
        "SAFETY_WAYPOINT_SETTLE_SECONDS",
        "1.0",
    )
)


# =========================================================
# Utility
# =========================================================

def yaw_to_quaternion(yaw):
    return (
        math.sin(yaw / 2.0),
        math.cos(yaw / 2.0),
    )


# =========================================================
# Patrol Controller
# =========================================================

class PatrolController(Node):

    def __init__(self):
        super().__init__("patrol_controller")

        self.navigator = BasicNavigator()

        self.lock = threading.RLock()

        self.running = False
        self.returning = False

        self.waypoints = []
        self.home = None
        self.current_pose = None
        self.current_index = -1

        self.workplace_id = None
        self.patrol_id = None

        self.active_patrol_mode = "IDLE"
        self.active_session_id = None

        self.worker = None

        self.capture_condition = (
            threading.Condition()
        )

        self.capture_results = {}

        self.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self._pose_callback,
            10,
        )

        self.arrival_publisher = (
            self.create_publisher(
                String,
                "/patrol/waypoint_arrived",
                10,
            )
        )

        self.create_subscription(
            String,
            "/patrol/waypoint_capture_done",
            self._capture_done_callback,
            10,
        )

        self.get_logger().info(
            "Patrol controller started."
        )

        self.get_logger().info(
            f"Waypoint file: {WAYPOINT_FILE}"
        )

    # =====================================================
    # Waypoint configuration
    # =====================================================

    def load_saved_waypoints(self):
        """
        RViz2에서 설정한 Waypoint 3개를
        JSON 파일에서 불러온다.
        """

        if not WAYPOINT_FILE.is_file():
            raise ValueError(
                "Waypoint file not found: "
                f"{WAYPOINT_FILE}"
            )

        try:
            data = json.loads(
                WAYPOINT_FILE.read_text(
                    encoding="utf-8"
                )
            )

        except (
            json.JSONDecodeError,
            OSError,
        ) as exc:
            raise ValueError(
                f"Waypoint file error: {exc}"
            )

        waypoints = data.get("waypoints")

        if not isinstance(waypoints, list):
            raise ValueError(
                "waypoints must be a list."
            )

        if len(waypoints) != 3:
            raise ValueError(
                "Exactly 3 waypoints are required."
            )

        normalized = []

        for index, waypoint in enumerate(
            waypoints,
            start=1,
        ):
            if not isinstance(waypoint, dict):
                raise ValueError(
                    f"Invalid waypoint {index}"
                )

            try:
                x = float(waypoint["x"])
                y = float(waypoint["y"])
                yaw = float(
                    waypoint.get("yaw", 0.0)
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                raise ValueError(
                    f"Invalid coordinates: WP{index}"
                )

            if not all(
                math.isfinite(value)
                for value in (x, y, yaw)
            ):
                raise ValueError(
                    f"Non-finite coordinates: WP{index}"
                )

            normalized.append(
                {
                    "id": index,
                    "x": x,
                    "y": y,
                    "yaw": yaw,
                }
            )

        self.get_logger().info(
            "Loaded saved waypoints: "
            + ", ".join(
                (
                    f"WP{wp['id']}"
                    f"({wp['x']:.2f}, {wp['y']:.2f})"
                )
                for wp in normalized
            )
        )

        return normalized

    # =====================================================
    # Pose
    # =====================================================

    def make_pose(self, x, y, yaw=0.0):
        pose = PoseStamped()

        pose.header.frame_id = "map"
        pose.header.stamp = (
            self.navigator.get_clock().now().to_msg()
        )

        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)

        z, w = yaw_to_quaternion(float(yaw))

        pose.pose.orientation.z = z
        pose.pose.orientation.w = w

        return pose

    def _pose_callback(self, msg):
        pose = msg.pose.pose

        yaw = math.atan2(
            2.0 * (
                pose.orientation.w
                * pose.orientation.z
                + pose.orientation.x
                * pose.orientation.y
            ),
            1.0 - 2.0 * (
                pose.orientation.y ** 2
                + pose.orientation.z ** 2
            ),
        )

        with self.lock:
            self.current_pose = {
                "x": float(pose.position.x),
                "y": float(pose.position.y),
                "yaw": float(yaw),
            }

    # =====================================================
    # Status
    # =====================================================

    def get_status(self):
        with self.lock:
            return {
                "running": self.running,
                "returning": self.returning,
                "current_index": self.current_index,
                "waypoint_count": len(self.waypoints),
                "waypoints": self.waypoints,
                "mode": self.active_patrol_mode,
                "session_id": self.active_session_id,
            }

    # =====================================================
    # Baseline
    # =====================================================

    def _verify_baseline_images(self):
        if not BASELINE_METADATA_FILE.exists():
            return False

        try:
            data = json.loads(
                BASELINE_METADATA_FILE.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(data, dict):
                data = data.get(
                    "images",
                    data.get("baselines", []),
                )

            if not isinstance(data, list):
                return False

            ids = set()

            for item in data:
                if not isinstance(item, dict):
                    continue

                try:
                    waypoint_id = int(
                        item["waypoint_id"]
                    )

                    image_path = Path(
                        item["image"]
                    ).expanduser()

                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    continue

                if image_path.is_file():
                    ids.add(waypoint_id)

            return all(
                waypoint_id in ids
                for waypoint_id in range(
                    1,
                    len(self.waypoints) + 1,
                )
            )

        except Exception:
            return False

    def has_baseline_images(self):
        if not BASELINE_COMPLETE_FILE.exists():
            return False

        try:
            completion = json.loads(
                BASELINE_COMPLETE_FILE.read_text(
                    encoding="utf-8"
                )
            )

            if completion.get("completed") is not True:
                return False

            if (
                completion.get("waypoint_count")
                != len(self.waypoints)
            ):
                return False

            return self._verify_baseline_images()

        except Exception:
            return False

    def mark_baseline_complete(self):
        BASELINE_COMPLETE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        BASELINE_COMPLETE_FILE.write_text(
            json.dumps(
                {
                    "completed": True,
                    "waypoint_count": len(
                        self.waypoints
                    ),
                    "completed_at": time.time(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self.get_logger().info(
            "Baseline patrol completed."
        )

    # =====================================================
    # Patrol mode
    # =====================================================

    def set_patrol_mode(self, mode):
        PATROL_MODE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp_file = PATROL_MODE_FILE.with_suffix(
            ".tmp"
        )

        temp_file.write_text(
            json.dumps(
                {
                    "mode": mode,
                    "session_id": self.active_session_id,
                    "updated_at": time.time(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temp_file.replace(
            PATROL_MODE_FILE
        )

        self.get_logger().info(
            f"Patrol mode: {mode}"
        )

    # =====================================================
    # Capture response
    # =====================================================

    def _capture_done_callback(self, msg):
        try:
            data = json.loads(msg.data)

            request_id = data.get(
                "request_id"
            )

            if not request_id:
                return

            with self.capture_condition:
                self.capture_results[
                    request_id
                ] = data

                self.capture_condition.notify_all()

        except Exception as exc:
            self.get_logger().warning(
                f"Capture response error: {exc}"
            )

    def request_waypoint_capture(
        self,
        waypoint_id,
        waypoint,
    ):
        request_id = uuid.uuid4().hex

        with self.lock:
            if not self.running:
                return False

            mode = self.active_patrol_mode
            session_id = self.active_session_id

        message = {
            "request_id": request_id,
            "session_id": session_id,
            "waypoint_id": waypoint_id,
            "mode": mode,
            "x": float(waypoint["x"]),
            "y": float(waypoint["y"]),
            "yaw": float(waypoint["yaw"]),
        }

        ros_message = String()
        ros_message.data = json.dumps(
            message,
            ensure_ascii=False,
        )

        self.arrival_publisher.publish(
            ros_message
        )

        self.get_logger().info(
            f"Capture requested: WP{waypoint_id}"
        )

        deadline = (
            time.monotonic()
            + CAPTURE_TIMEOUT
        )

        with self.capture_condition:
            while True:
                result = self.capture_results.pop(
                    request_id,
                    None,
                )

                if result is not None:
                    if (
                        result.get("session_id")
                        != session_id
                        or result.get("waypoint_id")
                        != waypoint_id
                    ):
                        return False

                    success = (
                        result.get("success") is True
                    )

                    if not success:
                        self.get_logger().error(
                            f"Capture failed: {result.get('error')}"
                        )

                    return success

                with self.lock:
                    if not self.running:
                        return False

                remaining = (
                    deadline
                    - time.monotonic()
                )

                if remaining <= 0:
                    self.get_logger().error(
                        f"Capture timeout: WP{waypoint_id}"
                    )
                    return False

                self.capture_condition.wait(
                    timeout=min(
                        remaining,
                        0.2,
                    )
                )

    # =====================================================
    # Start patrol
    # =====================================================

    def start_patrol(
        self,
        workplace_id=None,
        patrol_id=None,
    ):
        waypoints = self.load_saved_waypoints()

        with self.lock:
            if self.running or self.returning:
                raise RuntimeError(
                    "Patrol is already active."
                )

            if self.current_pose is None:
                raise RuntimeError(
                    "Robot pose is not available."
                )

            self.waypoints = waypoints

            self.workplace_id = workplace_id
            self.patrol_id = patrol_id

            self.home = dict(
                self.current_pose
            )

            self.current_index = -1
            self.running = True
            self.returning = False

            self.active_session_id = (
                uuid.uuid4().hex
            )

            self.active_patrol_mode = (
                "MONITORING"
                if self.has_baseline_images()
                else "BASELINE"
            )

        self.set_patrol_mode(
            self.active_patrol_mode
        )

        self.worker = threading.Thread(
            target=self._patrol_worker,
            daemon=True,
        )

        self.worker.start()

        return {
            "status": "started",
            "mode": self.active_patrol_mode,
            "waypoint_count": len(
                self.waypoints
            ),
        }

    # =====================================================
    # Backend completion
    # =====================================================

    def notify_backend_complete(self):
        if (
            self.workplace_id is None
            or self.patrol_id is None
        ):
            self.get_logger().info(
                "Patrol finished without backend ID."
            )
            return

        url = (
            f"{BACKEND_URL}"
            f"/workplaces/{self.workplace_id}"
            f"/patrols/{self.patrol_id}/complete"
        )

        try:
            response = requests.post(
                url,
                timeout=10,
            )

            response.raise_for_status()

            self.get_logger().info(
                "Backend patrol completion updated."
            )

        except requests.RequestException as exc:
            self.get_logger().error(
                f"Backend completion failed: {exc}"
            )

    # =====================================================
    # Patrol worker
    # =====================================================

    def _patrol_worker(self):
        completed = False

        try:
            self.get_logger().info(
                "Waiting for Nav2..."
            )

            self.navigator.waitUntilNav2Active()

            for index, waypoint in enumerate(
                self.waypoints
            ):
                with self.lock:
                    if not self.running:
                        return

                    self.current_index = index

                waypoint_id = index + 1

                self.get_logger().info(
                    f"Moving to WP{waypoint_id}"
                )

                pose = self.make_pose(
                    waypoint["x"],
                    waypoint["y"],
                    waypoint["yaw"],
                )

                self.navigator.goToPose(
                    pose
                )

                while not (
                    self.navigator.isTaskComplete()
                ):
                    with self.lock:
                        if not self.running:
                            self.navigator.cancelTask()
                            return

                    time.sleep(0.2)

                result = (
                    self.navigator.getResult()
                )

                if result != TaskResult.SUCCEEDED:
                    self.get_logger().error(
                        f"Navigation failed: WP{waypoint_id}"
                    )
                    return

                self.get_logger().info(
                    f"Reached WP{waypoint_id}"
                )

                time.sleep(
                    ARRIVAL_SETTLE_SECONDS
                )

                with self.lock:
                    if not self.running:
                        return

                captured = (
                    self.request_waypoint_capture(
                        waypoint_id,
                        waypoint,
                    )
                )

                if not captured:
                    self.get_logger().error(
                        "Patrol stopped because "
                        f"WP{waypoint_id} capture failed."
                    )
                    return

                self.get_logger().info(
                    f"WP{waypoint_id} capture complete."
                )

            completed = True

            if (
                self.active_patrol_mode
                == "BASELINE"
            ):
                if not self._verify_baseline_images():
                    self.get_logger().error(
                        "Baseline images incomplete."
                    )
                    completed = False
                    return

                self.mark_baseline_complete()

            self.notify_backend_complete()

        except Exception as exc:
            self.get_logger().error(
                f"Patrol error: {exc}"
            )

        finally:
            with self.lock:
                self.running = False
                self.current_index = -1

            if not self.returning:
                self.set_patrol_mode("IDLE")

            self.get_logger().info(
                "Patrol completed."
                if completed
                else "Patrol stopped."
            )

    # =====================================================
    # Return home
    # =====================================================

    def return_home(self):
        with self.lock:
            if self.home is None:
                raise RuntimeError(
                    "Home position is not configured."
                )

            if self.returning:
                raise RuntimeError(
                    "Already returning home."
                )

            self.running = False
            self.returning = True

        with self.capture_condition:
            self.capture_condition.notify_all()

        self.navigator.cancelTask()

        worker = threading.Thread(
            target=self._return_worker,
            daemon=True,
        )

        worker.start()

    def _return_worker(self):
        try:
            self.navigator.waitUntilNav2Active()

            pose = self.make_pose(
                self.home["x"],
                self.home["y"],
                self.home["yaw"],
            )

            self.navigator.goToPose(
                pose
            )

            while not (
                self.navigator.isTaskComplete()
            ):
                time.sleep(0.2)

            result = (
                self.navigator.getResult()
            )

            if result == TaskResult.SUCCEEDED:
                self.get_logger().info(
                    "Returned home."
                )
            else:
                self.get_logger().error(
                    "Return-home failed."
                )

        except Exception as exc:
            self.get_logger().error(
                f"Return-home error: {exc}"
            )

        finally:
            with self.lock:
                self.returning = False
                self.current_index = -1

            self.set_patrol_mode(
                "IDLE"
            )


# =========================================================
# HTTP API
# =========================================================

controller = None


class CommandHandler(BaseHTTPRequestHandler):

    def send_json(self, status_code, data):
        body = json.dumps(
            data,
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(
            status_code
        )

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(
            self.headers.get(
                "Content-Length",
                "0",
            )
        )

        if length <= 0:
            return {}

        return json.loads(
            self.rfile.read(length).decode(
                "utf-8"
            )
        )

    def do_GET(self):
        if self.path == "/status":
            self.send_json(
                200,
                controller.get_status(),
            )
            return

        self.send_json(
            404,
            {"detail": "Not found"},
        )

    def do_POST(self):
        try:
            if self.path == "/patrol/start":
                data = self.read_json()

                result = controller.start_patrol(
                    workplace_id=data.get(
                        "workplace_id"
                    ),
                    patrol_id=data.get(
                        "patrol_id"
                    ),
                )

                self.send_json(
                    200,
                    result,
                )
                return

            if self.path == "/patrol/return-home":
                controller.return_home()

                self.send_json(
                    200,
                    {"status": "returning"},
                )
                return

            self.send_json(
                404,
                {"detail": "Not found"},
            )

        except ValueError as exc:
            self.send_json(
                400,
                {"detail": str(exc)},
            )

        except RuntimeError as exc:
            self.send_json(
                409,
                {"detail": str(exc)},
            )

        except Exception as exc:
            self.send_json(
                500,
                {"detail": str(exc)},
            )

    def log_message(self, format, *args):
        return


# =========================================================
# HTTP Server
# =========================================================

def run_http_server():
    server = ThreadingHTTPServer(
        (COMMAND_HOST, COMMAND_PORT),
        CommandHandler,
    )

    controller.get_logger().info(
        f"Patrol HTTP server: {COMMAND_HOST}:{COMMAND_PORT}"
    )

    server.serve_forever()


# =========================================================
# Main
# =========================================================

def main(args=None):
    global controller

    rclpy.init(args=args)

    controller = PatrolController()

    server_thread = threading.Thread(
        target=run_http_server,
        daemon=True,
    )

    server_thread.start()

    executor = MultiThreadedExecutor(
        num_threads=2
    )

    executor.add_node(
        controller
    )

    try:
        executor.spin()

    except KeyboardInterrupt:
        pass

    finally:
        executor.shutdown()

        controller.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
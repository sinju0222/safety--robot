import json
import math
import os
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from rclpy.node import Node


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

PACKAGE_DIR = Path(
    __file__
).resolve().parent

PATROL_MODE_FILE = Path(
    os.getenv(
        "SAFETY_PATROL_MODE_FILE",
        str(
            PACKAGE_DIR
            / "data"
            / "patrol_mode.json"
        ),
    )
)

BASELINE_METADATA_FILE = Path(
    os.getenv(
        "SAFETY_BASELINE_IMAGE_METADATA",
        str(
            PACKAGE_DIR
            / "data"
            / "baseline_images.json"
        ),
    )
)


BASELINE_COMPLETE_FILE = Path(
    os.getenv(
        "SAFETY_BASELINE_COMPLETE_FILE",
        str(
            PACKAGE_DIR
            / "data"
            / "baseline_complete.json"
        ),
    )
)


def yaw_to_quaternion(yaw):
    """
    2D yaw 값을 geometry_msgs Quaternion의
    z, w 값으로 변환합니다.
    """
    return (
        math.sin(yaw / 2.0),
        math.cos(yaw / 2.0),
    )


class PatrolController(Node):

    def __init__(self):
        super().__init__(
            "patrol_controller"
        )

        self.navigator = BasicNavigator()

        self.lock = threading.Lock()

        self.running = False
        self.returning = False

        self.waypoints = []
        self.home = None
        self.current_pose = None

        self.pose_subscription = self.create_subscription(
            PoseWithCovarianceStamped,
            "/amcl_pose",
            self._pose_callback,
            10,
        )

        self.current_index = -1

        self.workplace_id = None
        self.patrol_id = None

        self.worker = None

        self.get_logger().info(
            "Patrol controller started."
        )

    def make_pose(
        self,
        x,
        y,
        yaw=0.0,
    ):
        pose = PoseStamped()

        pose.header.frame_id = "map"
        pose.header.stamp = (
            self.navigator
            .get_clock()
            .now()
            .to_msg()
        )

        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        pose.pose.position.z = 0.0

        z, w = yaw_to_quaternion(
            float(yaw)
        )

        pose.pose.orientation.z = z
        pose.pose.orientation.w = w

        return pose

    def _pose_callback(
        self,
        msg,
    ):
        pose = msg.pose.pose

        x = pose.position.x
        y = pose.position.y

        z = pose.orientation.z
        w = pose.orientation.w

        yaw = 2.0 * math.atan2(
            z,
            w,
        )

        with self.lock:
            self.current_pose = {
                "x": float(x),
                "y": float(y),
                "yaw": float(yaw),
            }

    def get_status(self):
        with self.lock:
            return {
                "running":
                    self.running,

                "returning":
                    self.returning,

                "current_index":
                    self.current_index,

                "waypoint_count":
                    len(
                        self.waypoints
                    ),
            }

    def has_baseline_images(self):
        if not BASELINE_COMPLETE_FILE.exists():
            return False

        if not BASELINE_METADATA_FILE.exists():
            return False

        try:
            data = json.loads(
                BASELINE_METADATA_FILE.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(data, list):
                return len(data) > 0

            if isinstance(data, dict):
                images = data.get(
                    "images",
                    data.get(
                        "baselines",
                        [],
                    ),
                )
                return (
                    isinstance(images, list)
                    and len(images) > 0
                )

        except Exception as exc:
            self.get_logger().warning(
                "Baseline metadata read failed: "
                f"{exc}"
            )

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
                    "completed_at":
                        time.time(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self.get_logger().info(
            "Baseline patrol completed."
        )

    def set_patrol_mode(
        self,
        mode,
    ):
        PATROL_MODE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp_file = (
            PATROL_MODE_FILE
            .with_suffix(".tmp")
        )

        temp_file.write_text(
            json.dumps(
                {
                    "mode": mode,
                    "updated_at":
                        time.time(),
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
            f"Patrol mode selected: {mode}"
        )

    def start_patrol(
        self,
        waypoints,
        workplace_id=None,
        patrol_id=None,
    ):
        if not waypoints:
            raise ValueError(
                "At least one waypoint is required."
            )

        with self.lock:

            if (
                self.running
                or self.returning
            ):
                raise RuntimeError(
                    "Patrol is already active."
                )

            self.waypoints = waypoints
            self.workplace_id = (
                workplace_id
            )
            self.patrol_id = (
                patrol_id
            )

            if self.current_pose is None:
                raise RuntimeError(
                    "현재 로봇 위치를 아직 받지 못했습니다."
                )

            self.home = dict(
                self.current_pose
            )

            self.current_index = -1
            self.running = True
            self.returning = False

        patrol_mode = (
            "MONITORING"
            if self.has_baseline_images()
            else "BASELINE"
        )

        self.active_patrol_mode = (
            patrol_mode
        )

        self.set_patrol_mode(
            patrol_mode
        )

        self.worker = threading.Thread(
            target=self._patrol_worker,
            daemon=True,
        )

        self.worker.start()

    def notify_backend_complete(self):
        if (
            self.workplace_id is None
            or self.patrol_id is None
        ):
            self.get_logger().warning(
                "Cannot notify backend: "
                "patrol ID is missing."
            )
            return

        url = (
            f"{BACKEND_URL}"
            f"/workplaces/"
            f"{self.workplace_id}"
            f"/patrols/"
            f"{self.patrol_id}"
            f"/complete"
        )

        try:
            response = requests.post(
                url,
                timeout=10,
            )

            response.raise_for_status()

            self.get_logger().info(
                "Backend patrol completion "
                "updated."
            )

        except requests.RequestException as exc:
            self.get_logger().error(
                "Backend patrol completion "
                f"failed: {exc}"
            )

    def _patrol_worker(self):

        self.get_logger().info(
            "Waiting for Nav2..."
        )

        try:
            self.navigator.waitUntilNav2Active()

            for index, waypoint in enumerate(
                self.waypoints
            ):

                with self.lock:

                    if not self.running:
                        return

                    self.current_index = index

                self.get_logger().info(
                    (
                        "Moving to waypoint "
                        f"{index + 1}/"
                        f"{len(self.waypoints)}"
                    )
                )

                pose = self.make_pose(
                    waypoint["x"],
                    waypoint["y"],
                    waypoint.get(
                        "yaw",
                        0.0,
                    ),
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
                    self.navigator
                    .getResult()
                )

                if (
                    result
                    != TaskResult.SUCCEEDED
                ):
                    self.get_logger().error(
                        (
                            "Failed to reach "
                            f"waypoint {index + 1}."
                        )
                    )

                    with self.lock:
                        self.running = False

                    return

            self.get_logger().info(
                "Patrol route completed."
            )

            if (
                getattr(
                    self,
                    "active_patrol_mode",
                    None,
                )
                == "BASELINE"
            ):
                self.mark_baseline_complete()

            self.set_patrol_mode(
                "IDLE"
            )

            with self.lock:
                self.running = False
                self.current_index = -1

            self.notify_backend_complete()

        except Exception as exc:

            self.get_logger().error(
                f"Patrol error: {exc}"
            )

            with self.lock:
                self.running = False
                self.current_index = -1

    def return_home(self):

        with self.lock:

            if self.home is None:
                raise RuntimeError(
                    "Home position is not configured."
                )

            self.running = False
            self.returning = True

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
                self.home.get(
                    "yaw",
                    0.0,
                ),
            )

            self.get_logger().info(
                "Returning to home."
            )

            self.navigator.goToPose(
                pose
            )

            while not (
                self.navigator.isTaskComplete()
            ):
                time.sleep(0.2)

            result = (
                self.navigator
                .getResult()
            )

            if (
                result
                == TaskResult.SUCCEEDED
            ):
                self.get_logger().info(
                    "Robot returned home."
                )
            else:
                self.get_logger().error(
                    "Failed to return home."
                )

        except Exception as exc:

            self.get_logger().error(
                f"Return-home error: {exc}"
            )

        finally:

            self.set_patrol_mode(
                "IDLE"
            )

            with self.lock:
                self.returning = False
                self.current_index = -1


controller = None


class CommandHandler(
    BaseHTTPRequestHandler
):

    def send_json(
        self,
        status_code,
        data,
    ):
        body = json.dumps(
            data
        ).encode("utf-8")

        self.send_response(
            status_code
        )

        self.send_header(
            "Content-Type",
            "application/json",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.end_headers()

        self.wfile.write(
            body
        )

    def read_json(self):

        length = int(
            self.headers.get(
                "Content-Length",
                "0",
            )
        )

        if length <= 0:
            return {}

        raw = self.rfile.read(
            length
        )

        return json.loads(
            raw.decode("utf-8")
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
            {
                "detail":
                    "Not found"
            },
        )

    def do_POST(self):

        try:

            if self.path == "/patrol/start":

                data = self.read_json()

                controller.start_patrol(
                    data.get(
                        "waypoints",
                        [],
                    ),
                    workplace_id=data.get(
                        "workplace_id"
                    ),
                    patrol_id=data.get(
                        "patrol_id"
                    ),
                )

                self.send_json(
                    200,
                    {
                        "status":
                            "started"
                    },
                )

                return

            if (
                self.path
                == "/patrol/return-home"
            ):

                controller.return_home()

                self.send_json(
                    200,
                    {
                        "status":
                            "returning"
                    },
                )

                return

            self.send_json(
                404,
                {
                    "detail":
                        "Not found"
                },
            )

        except ValueError as exc:

            self.send_json(
                400,
                {
                    "detail":
                        str(exc)
                },
            )

        except RuntimeError as exc:

            self.send_json(
                409,
                {
                    "detail":
                        str(exc)
                },
            )

        except Exception as exc:

            self.send_json(
                500,
                {
                    "detail":
                        str(exc)
                },
            )

    def log_message(
        self,
        format,
        *args,
    ):
        return


def run_http_server():

    server = ThreadingHTTPServer(
        (
            COMMAND_HOST,
            COMMAND_PORT,
        ),
        CommandHandler,
    )

    controller.get_logger().info(
        (
            "Patrol command server: "
            f"{COMMAND_HOST}:"
            f"{COMMAND_PORT}"
        )
    )

    server.serve_forever()


def main(args=None):

    global controller

    rclpy.init(
        args=args
    )

    controller = (
        PatrolController()
    )

    server_thread = threading.Thread(
        target=run_http_server,
        daemon=True,
    )

    server_thread.start()

    try:
        rclpy.spin(
            controller
        )

    except KeyboardInterrupt:
        pass

    finally:
        controller.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

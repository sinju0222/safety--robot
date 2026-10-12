import json
import math
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.duration import Duration
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
    qos_profile_sensor_data,
)
from rclpy.time import Time

from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import Image, LaserScan
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener

from baseline_image_manager import BaselineImageManager
from baseline_manager import BaselineManager
from camera_manager import CameraManager
from config import (
    BASE_FRAME,
    MAP_FRAME,
    MAP_TOPIC,
    RGB_TOPIC,
    SCAN_TOPIC,
    YOLO_CONFIDENCE,
    YOLO_IMAGE_SIZE,
    YOLO_MAX_DET,
    YOLO_MODEL_PATH,
)
from server_sender import ServerSender
from telemetry_sender import TelemetrySender
from yolo_detector import YoloDetector


# =========================================================
# Configuration
# =========================================================

WAYPOINT_CAPTURE_TIMEOUT = 5.0

WAYPOINT_DEMO_MODE = True


class ChangeDetectorNode(Node):

    def __init__(self):
        super().__init__(
            "robot_change_detector"
        )

        # =================================================
        # Output directories
        # =================================================

        self.output_dir = Path(
            os.environ.get(
                "SAFETY_OUTPUT_DIR",
                str(
                    Path.home()
                    / "robot_change_output"
                ),
            )
        ).expanduser()

        self.capture_dir = (
            self.output_dir / "captures"
        )

        self.current_image_dir = (
            self.output_dir / "current_images"
        )

        self.baseline_image_dir = (
            self.output_dir / "baseline_images"
        )

        self.event_dir = (
            self.output_dir / "events"
        )

        self.baseline_image_metadata = (
            self.output_dir / "baseline_images.json"
        )

        for directory in (
            self.capture_dir,
            self.current_image_dir,
            self.baseline_image_dir,
            self.event_dir,
        ):
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

        # =================================================
        # Backend
        # =================================================

        backend_url = os.environ.get(
            "SAFETY_BACKEND_URL",
            "",
        ).strip()

        self.server_sender = ServerSender(
            backend_url=backend_url,
        )

        self.workplace_id = int(
            os.environ.get(
                "SAFETY_WORKPLACE_ID",
                "1",
            )
        )

        self.telemetry_sender = TelemetrySender(
            backend_url=backend_url,
            workplace_id=self.workplace_id,
        )

        if self.server_sender.enabled:
            self.get_logger().info(
                f"Backend server: {backend_url}"
            )
        else:
            self.get_logger().warning(
                "Backend URL is not configured."
            )

        # =================================================
        # Patrol mode
        # =================================================

        self.patrol_mode_file = Path(
            os.environ.get(
                "SAFETY_PATROL_MODE_FILE",
                str(
                    self.output_dir
                    / "patrol_mode.json"
                ),
            )
        ).expanduser()

        self.patrol_mode = "IDLE"
        self.baseline_patrol = False

        self.refresh_patrol_mode()

        # =================================================
        # Baseline
        # =================================================

        self.baseline = BaselineManager()

        self.baseline_images = BaselineImageManager(
            save_dir=self.baseline_image_dir,
            metadata_file=(
                self.baseline_image_metadata
            ),
        )

        # =================================================
        # TF
        # =================================================

        self.tf_buffer = Buffer()

        self.tf_listener = TransformListener(
            self.tf_buffer,
            self,
        )

        self.last_scan_stamp = None

        # =================================================
        # Camera
        # =================================================

        self.camera = CameraManager(
            save_dir=self.capture_dir
        )

        # =================================================
        # YOLO
        # =================================================

        self.yolo = YoloDetector(
            model_path=YOLO_MODEL_PATH,
            confidence=YOLO_CONFIDENCE,
            image_size=YOLO_IMAGE_SIZE,
            max_det=YOLO_MAX_DET,
        )

        # =================================================
        # Waypoint processing
        # =================================================

        self.waypoint_lock = threading.Lock()

        self.processed_requests = set()

        self.current_session_id = None

        # =================================================
        # QoS
        # =================================================

        map_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        # =================================================
        # ROS subscriptions
        # =================================================

        self.map_subscription = (
            self.create_subscription(
                OccupancyGrid,
                MAP_TOPIC,
                self.map_callback,
                map_qos,
            )
        )

        self.scan_subscription = (
            self.create_subscription(
                LaserScan,
                SCAN_TOPIC,
                self.scan_callback,
                qos_profile_sensor_data,
            )
        )

        self.camera_subscription = (
            self.create_subscription(
                Image,
                RGB_TOPIC,
                self.camera_callback,
                qos_profile_sensor_data,
            )
        )

        self.waypoint_subscription = (
            self.create_subscription(
                String,
                "/patrol/waypoint_arrived",
                self.waypoint_arrived_callback,
                10,
            )
        )

        # =================================================
        # ROS publishers
        # =================================================

        self.capture_done_publisher = (
            self.create_publisher(
                String,
                "/patrol/waypoint_capture_done",
                10,
            )
        )

        # =================================================
        # Timers
        # =================================================

        self.pose_timer = self.create_timer(
            1.0,
            self.publish_robot_pose,
        )

        self.get_logger().info(
            "Robot Change Detector started."
        )

        self.get_logger().info(
            "Waypoint image comparison mode enabled."
        )

        self.get_logger().info(
            f"Output directory: {self.output_dir}"
        )

    # =====================================================
    # Patrol mode
    # =====================================================

    def refresh_patrol_mode(self):

        mode = "IDLE"

        try:
            if self.patrol_mode_file.exists():

                data = json.loads(
                    self.patrol_mode_file.read_text(
                        encoding="utf-8"
                    )
                )

                mode = str(
                    data.get("mode", "IDLE")
                ).upper()

        except Exception as exc:
            self.get_logger().warning(
                f"Patrol mode read failed: {exc}"
            )
            return

        if mode != self.patrol_mode:
            self.patrol_mode = mode

            self.get_logger().info(
                f"Patrol mode: {mode}"
            )

        self.baseline_patrol = (
            mode == "BASELINE"
        )

    # =====================================================
    # TF
    # =====================================================

    def lookup_transform(
        self,
        target,
        source,
        stamp=None,
    ):

        if stamp is not None:
            try:
                return self.tf_buffer.lookup_transform(
                    target,
                    source,
                    Time.from_msg(stamp),
                    timeout=Duration(seconds=0.15),
                )
            except Exception:
                pass

        try:
            return self.tf_buffer.lookup_transform(
                target,
                source,
                Time(),
                timeout=Duration(seconds=0.15),
            )

        except Exception:
            return None

    # =====================================================
    # Robot pose
    # =====================================================

    def get_robot_pose(self):

        transform = self.lookup_transform(
            MAP_FRAME,
            BASE_FRAME,
        )

        if transform is None:
            return None

        translation = (
            transform.transform.translation
        )

        rotation = (
            transform.transform.rotation
        )

        yaw = math.atan2(
            2.0 * (
                rotation.w * rotation.z
                + rotation.x * rotation.y
            ),
            1.0 - 2.0 * (
                rotation.y ** 2
                + rotation.z ** 2
            ),
        )

        return {
            "x": float(translation.x),
            "y": float(translation.y),
            "yaw": float(yaw),
        }

    def publish_robot_pose(self):

        pose = self.get_robot_pose()

        if pose is None:
            return

        if self.telemetry_sender.enabled:
            self.telemetry_sender.update_pose(
                pose
            )

    # =====================================================
    # Map
    # =====================================================

    def map_callback(self, msg):

        if self.telemetry_sender.enabled:
            self.telemetry_sender.update_map(msg)

        if self.baseline.map_ready:
            return

        self.baseline.set_baseline_map(msg)

        self.get_logger().info(
            "Baseline map saved."
        )

    # =====================================================
    # Camera
    # =====================================================

    def camera_callback(self, msg):

        self.camera.update_frame(msg)

    # =====================================================
    # LiDAR
    # =====================================================

    def scan_callback(self, scan_msg):

        self.last_scan_stamp = (
            scan_msg.header.stamp
        )

        if WAYPOINT_DEMO_MODE:
            return

        # Waypoint 시연 모드에서는 LiDAR 기반
        # 변화 이벤트를 생성하지 않는다.
        #
        # 기존 LiDAR 변화 감지 파이프라인은
        # 별도 모드로 복구할 수 있도록
        # 관련 모듈을 유지한다.

    # =====================================================
    # Waypoint arrival
    # =====================================================

    def waypoint_arrived_callback(self, msg):

        try:
            data = json.loads(
                msg.data
            )

            request_id = str(
                data["request_id"]
            )

            session_id = str(
                data["session_id"]
            )

            waypoint_id = int(
                data["waypoint_id"]
            )

            mode = str(
                data["mode"]
            ).upper()

            if waypoint_id < 1:
                raise ValueError(
                    "Invalid waypoint ID."
                )

            if mode not in (
                "BASELINE",
                "MONITORING",
            ):
                raise ValueError(
                    "Invalid patrol mode."
                )

            if not request_id or not session_id:
                raise ValueError(
                    "Missing request or session ID."
                )

            self.refresh_patrol_mode()

            if mode != self.patrol_mode:
                self.get_logger().warning(
                    "Waypoint mode mismatch. "
                    f"Received={mode}, "
                    f"Current={self.patrol_mode}"
                )
                return

            if session_id != self.current_session_id:
                self.current_session_id = session_id
                self.processed_requests.clear()

            if request_id in self.processed_requests:
                return

            self.processed_requests.add(
                request_id
            )

            self.get_logger().info(
                f"Waypoint {waypoint_id} arrived."
            )

            worker = threading.Thread(
                target=self.process_waypoint,
                args=(data,),
                daemon=True,
            )

            worker.start()

        except Exception as exc:
            self.get_logger().error(
                f"Waypoint message error: {exc}"
            )

    # =====================================================
    # Waypoint processing
    # =====================================================

    def process_waypoint(self, data):

        request_id = data["request_id"]
        session_id = data["session_id"]
        waypoint_id = int(data["waypoint_id"])
        mode = data["mode"].upper()

        success = False
        error = None
        image_path = None

        try:
            with self.waypoint_lock:

                self.get_logger().info(
                    f"Processing WP{waypoint_id} "
                    f"mode={mode}"
                )

                # -----------------------------------------
                # 1. Capture
                # -----------------------------------------

                image_path = (
                    self.camera.capture_waypoint(
                        waypoint_id=waypoint_id,
                        mode=mode,
                        timeout=(
                            WAYPOINT_CAPTURE_TIMEOUT
                        ),
                    )
                )

                if image_path is None:
                    raise RuntimeError(
                        "Camera capture failed."
                    )

                self.get_logger().info(
                    f"WP{waypoint_id} image saved: "
                    f"{image_path}"
                )

                # -----------------------------------------
                # 2. Robot pose
                # -----------------------------------------

                robot_pose = (
                    self.get_robot_pose()
                )

                if robot_pose is None:
                    robot_pose = {
                        "x": float(data["x"]),
                        "y": float(data["y"]),
                        "yaw": float(data["yaw"]),
                    }

                # -----------------------------------------
                # 3. BASELINE
                # -----------------------------------------

                if mode == "BASELINE":

                    item = (
                        self.baseline_images
                        .add_waypoint_baseline(
                            waypoint_id=waypoint_id,
                            image_path=image_path,
                            x=robot_pose["x"],
                            y=robot_pose["y"],
                            yaw=robot_pose["yaw"],
                        )
                    )

                    self.get_logger().info(
                        "BASELINE SAVED: "
                        f"WP{waypoint_id}, "
                        f'image={item["image"]}'
                    )

                    success = True

                # -----------------------------------------
                # 4. MONITORING
                # -----------------------------------------

                elif mode == "MONITORING":

                    baseline_image_path = (
                        self.baseline_images
                        .get_waypoint_baseline(
                            waypoint_id
                        )
                    )

                    if baseline_image_path is None:
                        raise RuntimeError(
                            "Baseline image missing "
                            f"for WP{waypoint_id}"
                        )

                    self.get_logger().info(
                        "BASELINE MATCHED: "
                        f"WP{waypoint_id}"
                    )

                    # -------------------------------------
                    # YOLO
                    # -------------------------------------

                    try:
                        detected_objects = (
                            self.yolo.detect(
                                image_path
                            )
                        )

                    except Exception as exc:
                        self.get_logger().error(
                            f"YOLO error: {exc}"
                        )
                        detected_objects = []

                    # -------------------------------------
                    # Event
                    # -------------------------------------

                    event = (
                        self.create_waypoint_event(
                            waypoint_id=waypoint_id,
                            image_path=image_path,
                            robot_pose=robot_pose,
                            detected_objects=(
                                detected_objects
                            ),
                        )
                    )

                    # -------------------------------------
                    # Server
                    # -------------------------------------

                    if self.server_sender.enabled:

                        self.server_sender.send_event(
                            event=event,
                            baseline_image_path=(
                                baseline_image_path
                            ),
                            current_image_path=(
                                image_path
                            ),
                        )

                        self.get_logger().info(
                            "VLM analysis queued: "
                            f"WP{waypoint_id}"
                        )

                    else:
                        self.get_logger().warning(
                            "Server upload disabled."
                        )

                    success = True

        except Exception as exc:

            error = str(exc)

            self.get_logger().error(
                "Waypoint processing failed: "
                f"WP{waypoint_id}: {error}"
            )

        finally:

            self.publish_capture_result(
                request_id=request_id,
                session_id=session_id,
                waypoint_id=waypoint_id,
                success=success,
                error=error,
                image_path=image_path,
            )

    # =====================================================
    # Waypoint event
    # =====================================================

    def create_waypoint_event(
        self,
        waypoint_id,
        image_path,
        robot_pose,
        detected_objects,
    ):

        now = datetime.now().astimezone()

        event_id = (
            "evt_"
            + now.strftime(
                "%Y%m%d_%H%M%S_%f"
            )
        )

        event = {
            "event_id": event_id,
            "timestamp": now.isoformat(),

            "source": "WAYPOINT_VLM",

            "waypoint_id": waypoint_id,

            "change": {
                "type": "UNKNOWN",
                "x": round(
                    robot_pose["x"], 3
                ),
                "y": round(
                    robot_pose["y"], 3
                ),
            },

            "robot": {
                "x": round(
                    robot_pose["x"], 3
                ),
                "y": round(
                    robot_pose["y"], 3
                ),
                "yaw": round(
                    robot_pose["yaw"], 3
                ),
            },

            "image": Path(
                image_path
            ).name,

            "objects": (
                detected_objects or []
            ),

            "workplace_id": (
                self.workplace_id
            ),
        }

        json_path = (
            self.event_dir
            / f"{event_id}.json"
        )

        json_path.write_text(
            json.dumps(
                event,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return event

    # =====================================================
    # Capture result
    # =====================================================

    def publish_capture_result(
        self,
        request_id,
        session_id,
        waypoint_id,
        success,
        error=None,
        image_path=None,
    ):

        result = {
            "request_id": request_id,
            "session_id": session_id,
            "waypoint_id": waypoint_id,
            "success": bool(success),
            "error": error,
            "image_path": image_path,
        }

        msg = String()

        msg.data = json.dumps(
            result,
            ensure_ascii=False,
        )

        self.capture_done_publisher.publish(
            msg
        )

        self.get_logger().info(
            "Capture result published: "
            f"WP{waypoint_id}, "
            f"success={success}"
        )


# =========================================================
# Main
# =========================================================

def main(args=None):

    rclpy.init(args=args)

    node = ChangeDetectorNode()

    executor = MultiThreadedExecutor(
        num_threads=4
    )

    executor.add_node(node)

    try:
        executor.spin()

    except KeyboardInterrupt:
        pass

    finally:
        executor.shutdown()

        node.telemetry_sender.close()

        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
import json
import math
import os
from pathlib import Path

import rclpy
from rclpy.duration import Duration
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
from tf2_ros import Buffer, TransformListener

from baseline_image_manager import (
    BaselineImageManager,
)
from baseline_manager import BaselineManager
from camera_manager import CameraManager
from change_detector import detect_change
from cluster_manager import (
    cluster_points,
    distance,
    get_center,
)
from config import (
    ADDED_CONFIRM_COUNT,
    ADDED_MIN_CLUSTER_POINTS,
    BASELINE_PADDING_CELLS,
    BASE_FRAME,
    MAP_FRAME,
    MAP_TOPIC,
    POSITION_TOLERANCE,
    REMOVED_CONFIRM_COUNT,
    REMOVED_MIN_CLUSTER_POINTS,
    RGB_TOPIC,
    SCAN_TOPIC,
    YOLO_CONFIDENCE,
    YOLO_IMAGE_SIZE,
    YOLO_MAX_DET,
    YOLO_MODEL_PATH,
)
from event_manager import create_event
from scan_observer import (
    build_scan_observation,
)
from server_sender import ServerSender
from state_machine import (
    DetectionState,
    DetectionStateMachine,
)
from telemetry_sender import TelemetrySender
from yolo_detector import YoloDetector


BASELINE_CAPTURE_DISTANCE = 0.35
BASELINE_CAPTURE_YAW = math.radians(30.0)


class ChangeDetectorNode(Node):
    def __init__(self):
        super().__init__(
            "robot_change_detector"
        )

        # ==================================================
        # Output
        # ==================================================

        self.output_dir = (
            Path.home()
            / "robot_change_output"
        )
        self.capture_dir = (
            self.output_dir
            / "captures"
        )
        self.event_dir = (
            self.output_dir
            / "events"
        )
        self.baseline_image_dir = (
            self.output_dir
            / "baseline_images"
        )
        self.baseline_image_metadata = (
            self.output_dir
            / "baseline_images.json"
        )

        self.capture_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.event_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        backend_url = (
            os.environ.get(
                "SAFETY_BACKEND_URL",
                "",
            ).strip()
        )

        self.server_sender = (
            ServerSender(
                backend_url=backend_url,
            )
        )

        self.workplace_id = int(
            os.environ.get(
                "SAFETY_WORKPLACE_ID",
                "1",
            )
        )

        self.telemetry_sender = (
            TelemetrySender(
                backend_url=backend_url,
                workplace_id=(
                    self.workplace_id
                ),
            )
        )

        if self.server_sender.enabled:
            self.get_logger().info(
                f"Backend server: "
                f"{backend_url}"
            )
        else:
            self.get_logger().warning(
                "SAFETY_BACKEND_URL "
                "is not set. "
                "Server upload disabled."
            )

        # ==================================================
        # Patrol mode
        # ==================================================

        self.baseline_patrol = (
            os.environ.get(
                "SAFETY_BASELINE_PATROL",
                "0",
            ).strip()
            == "1"
        )

        self.last_baseline_pose = None

        # ==================================================
        # Baseline
        # ==================================================

        self.baseline = (
            BaselineManager()
        )

        self.baseline_images = (
            BaselineImageManager(
                save_dir=(
                    self.baseline_image_dir
                ),
                metadata_file=(
                    self.baseline_image_metadata
                ),
            )
        )

        # ==================================================
        # TF
        # ==================================================

        self.tf_buffer = Buffer()
        self.tf_listener = (
            TransformListener(
                self.tf_buffer,
                self,
            )
        )

        self.last_scan_stamp = None

        # ==================================================
        # Camera / YOLO
        # ==================================================

        self.camera = CameraManager(
            save_dir=self.capture_dir
        )

        self.yolo = YoloDetector(
            model_path=YOLO_MODEL_PATH,
            confidence=YOLO_CONFIDENCE,
            image_size=YOLO_IMAGE_SIZE,
            max_det=YOLO_MAX_DET,
        )

        # ==================================================
        # Detection
        # ==================================================

        self.state_machine = (
            DetectionStateMachine(
                position_threshold=(
                    POSITION_TOLERANCE
                )
            )
        )

        self.current_change = None
        self.current_cluster_points = set()

        # ==================================================
        # QoS
        # ==================================================

        map_qos = QoSProfile(
            reliability=(
                ReliabilityPolicy.RELIABLE
            ),
            durability=(
                DurabilityPolicy.TRANSIENT_LOCAL
            ),
            history=(
                HistoryPolicy.KEEP_LAST
            ),
            depth=1,
        )

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

        self.pose_timer = (
            self.create_timer(
                1.0,
                self.publish_robot_pose,
            )
        )

        if self.baseline_patrol:
            self.baseline_capture_timer = (
                self.create_timer(
                    1.0,
                    self.capture_baseline_if_needed,
                )
            )
        else:
            self.baseline_capture_timer = None

        self.get_logger().info(
            "Robot Change Detector started"
        )

        if self.baseline_patrol:
            self.get_logger().info(
                "Patrol mode: BASELINE"
            )
            self.get_logger().info(
                "RGB baseline images will "
                "be recorded during patrol."
            )
        else:
            self.get_logger().info(
                "Patrol mode: MONITORING"
            )
            self.get_logger().info(
                "RGB is saved only after "
                "a confirmed change."
            )

        self.get_logger().info(
            f"Output: {self.output_dir}"
        )

    # ======================================================
    # TF
    # ======================================================

    def lookup_transform(
        self,
        target,
        source,
        stamp=None,
    ):
        if stamp is not None:
            try:
                return (
                    self.tf_buffer
                    .lookup_transform(
                        target,
                        source,
                        Time.from_msg(stamp),
                        timeout=Duration(
                            seconds=0.15
                        ),
                    )
                )
            except Exception:
                pass

        try:
            return (
                self.tf_buffer
                .lookup_transform(
                    target,
                    source,
                    Time(),
                    timeout=Duration(
                        seconds=0.15
                    ),
                )
            )
        except Exception as exc:
            self.get_logger().warning(
                f"TF unavailable "
                f"{target} <- {source}: "
                f"{exc}"
            )
            return None

    # ======================================================
    # Baseline map
    # ======================================================

    def map_callback(self, msg):
        if self.baseline.map_ready:
            return

        self.baseline.set_baseline_map(
            msg
        )

        if self.telemetry_sender.enabled:
            self.telemetry_sender.update_map(
                msg
            )

        self.get_logger().info(
            "Baseline map saved: "
            f"{self.baseline.width}x"
            f"{self.baseline.height}, "
            f"{self.baseline.resolution:.4f} "
            "m/cell"
        )

    # ======================================================
    # RealSense
    # ======================================================

    def camera_callback(self, msg):
        self.camera.update_frame(
            msg
        )

    # ======================================================
    # Robot pose
    # ======================================================

    def get_robot_pose(self):
        transform = (
            self.lookup_transform(
                MAP_FRAME,
                BASE_FRAME,
                self.last_scan_stamp,
            )
        )

        if transform is None:
            return None

        translation = (
            transform
            .transform
            .translation
        )
        rotation = (
            transform
            .transform
            .rotation
        )

        yaw = math.atan2(
            2.0
            * (
                rotation.w
                * rotation.z
                + rotation.x
                * rotation.y
            ),
            1.0
            - 2.0
            * (
                rotation.y
                * rotation.y
                + rotation.z
                * rotation.z
            ),
        )

        return {
            "x": float(
                translation.x
            ),
            "y": float(
                translation.y
            ),
            "yaw": float(
                yaw
            ),
        }

    def publish_robot_pose(self):
        pose = self.get_robot_pose()

        if pose is None:
            return

        if self.telemetry_sender.enabled:
            self.telemetry_sender.update_pose(
                pose
            )

    # ======================================================
    # RGB baseline patrol
    # ======================================================

    def should_capture_baseline(
        self,
        pose,
    ):
        if self.last_baseline_pose is None:
            return True

        movement = math.hypot(
            pose["x"]
            - self.last_baseline_pose["x"],
            pose["y"]
            - self.last_baseline_pose["y"],
        )

        yaw_difference = (
            BaselineImageManager
            .angle_difference(
                pose["yaw"],
                self.last_baseline_pose[
                    "yaw"
                ],
            )
        )

        return (
            movement
            >= BASELINE_CAPTURE_DISTANCE
            or yaw_difference
            >= BASELINE_CAPTURE_YAW
        )

    def capture_baseline_if_needed(
        self
    ):
        if not self.baseline_patrol:
            return

        if not self.baseline.map_ready:
            return

        pose = self.get_robot_pose()

        if pose is None:
            return

        if not self.should_capture_baseline(
            pose
        ):
            return

        image_path = (
            self.camera.capture()
        )

        if image_path is None:
            self.get_logger().warning(
                "Baseline RGB capture "
                "failed: camera frame "
                "unavailable."
            )
            return

        try:
            item = (
                self.baseline_images
                .add_baseline(
                    image_path=image_path,
                    x=pose["x"],
                    y=pose["y"],
                    yaw=pose["yaw"],
                )
            )
        except Exception as exc:
            self.get_logger().error(
                "Baseline RGB save failed: "
                f"{exc}"
            )
            return

        self.last_baseline_pose = (
            pose.copy()
        )

        self.get_logger().info(
            "BASELINE RGB SAVED: "
            f'id={item["id"]}, '
            f'x={pose["x"]:.2f}, '
            f'y={pose["y"]:.2f}, '
            f'yaw={pose["yaw"]:.2f}'
        )

    # ======================================================
    # Candidate creation
    # ======================================================

    def build_candidates(
        self,
        scan_msg,
        transform,
    ):
        observation = (
            build_scan_observation(
                scan_msg,
                transform,
                self.baseline,
            )
        )

        candidates = []

        added_points = [
            point
            for point
            in observation["hit_points"]
            if self.baseline.is_free(
                point[0],
                point[1],
            )
        ]

        added_clusters = [
            cluster
            for cluster
            in cluster_points(
                added_points
            )
            if len(cluster)
            >= ADDED_MIN_CLUSTER_POINTS
        ]

        for cluster in added_clusters:
            center = get_center(
                cluster
            )

            if center is None:
                continue

            change = detect_change(
                position=center,
                past_state=0,
                current_state=1,
            )

            if change is None:
                continue

            candidates.append(
                {
                    "change": change,
                    "cluster": cluster,
                    "required_count":
                        ADDED_CONFIRM_COUNT,
                    "score": len(
                        cluster
                    ),
                }
            )

        removed_points = []

        for gx, gy in observation[
            "observed_free_cells"
        ]:
            if not (
                self.baseline
                .is_occupied_grid(
                    gx,
                    gy,
                )
            ):
                continue

            world = (
                self.baseline
                .grid_to_world(
                    gx,
                    gy,
                )
            )

            if world is not None:
                removed_points.append(
                    world
                )

        removed_clusters = [
            cluster
            for cluster
            in cluster_points(
                removed_points
            )
            if len(cluster)
            >= REMOVED_MIN_CLUSTER_POINTS
        ]

        for cluster in removed_clusters:
            center = get_center(
                cluster
            )

            if center is None:
                continue

            change = detect_change(
                position=center,
                past_state=1,
                current_state=0,
            )

            if change is None:
                continue

            candidates.append(
                {
                    "change": change,
                    "cluster": cluster,
                    "required_count":
                        REMOVED_CONFIRM_COUNT,
                    "score": len(
                        cluster
                    ),
                }
            )

        return candidates

    def choose_candidate(
        self,
        candidates,
    ):
        if not candidates:
            return None

        state = (
            self.state_machine
            .get_state()
        )

        if (
            state
            == DetectionState.CONFIRMING
        ):
            target_type = (
                self.state_machine
                .candidate_event_type
            )
            target_position = (
                self.state_machine
                .candidate_position
            )

            matching = []

            for candidate in candidates:
                change = candidate[
                    "change"
                ]

                if (
                    change["event_type"]
                    != target_type
                ):
                    continue

                position = (
                    change[
                        "position"
                    ]["x"],
                    change[
                        "position"
                    ]["y"],
                )

                d = distance(
                    position,
                    target_position,
                )

                if (
                    d
                    <= POSITION_TOLERANCE
                ):
                    matching.append(
                        (
                            d,
                            candidate,
                        )
                    )

            if not matching:
                return None

            matching.sort(
                key=lambda item: item[0]
            )

            return matching[0][1]

        return max(
            candidates,
            key=lambda item: item[
                "score"
            ],
        )

    # ======================================================
    # Main scan callback
    # ======================================================

    def scan_callback(
        self,
        scan_msg,
    ):
        self.last_scan_stamp = (
            scan_msg.header.stamp
        )

        # 첫 번째 기준 순찰에서는
        # 변화 이벤트를 생성하지 않는다.
        if self.baseline_patrol:
            return

        state = (
            self.state_machine
            .get_state()
        )

        if state in (
            DetectionState.CAPTURING,
            DetectionState.ANALYZING,
            DetectionState.PROCESSING,
        ):
            return

        if not self.baseline.map_ready:
            return

        transform = (
            self.lookup_transform(
                MAP_FRAME,
                scan_msg.header.frame_id,
                scan_msg.header.stamp,
            )
        )

        if transform is None:
            return

        candidates = (
            self.build_candidates(
                scan_msg,
                transform,
            )
        )

        candidate = (
            self.choose_candidate(
                candidates
            )
        )

        if candidate is None:
            self.cancel_pending_change_if_needed()
            return

        change = candidate["change"]
        cluster = candidate["cluster"]
        required_count = candidate[
            "required_count"
        ]

        position = (
            change["position"]["x"],
            change["position"]["y"],
        )

        event_type = (
            change["event_type"]
        )

        state = (
            self.state_machine
            .get_state()
        )

        if (
            state
            == DetectionState.MONITORING
        ):
            self.current_change = (
                change
            )

            self.current_cluster_points = (
                set(
                    cluster
                )
            )

            self.state_machine.start_confirmation(
                position=position,
                event_type=event_type,
                required_count=(
                    required_count
                ),
            )

            self.get_logger().info(
                "CHANGE CANDIDATE: "
                f"{event_type} "
                f"{position} "
                f"1/{required_count}"
            )

            return

        if (
            state
            == DetectionState.CONFIRMING
        ):
            confirmed = (
                self.state_machine
                .confirm_detection(
                    position=position,
                    event_type=event_type,
                )
            )

            if not confirmed:
                if (
                    self.state_machine
                    .get_state()
                    == DetectionState.MONITORING
                ):
                    self.clear_current_change()

                return

            self.current_change = (
                change
            )

            self.current_cluster_points.update(
                cluster
            )

            self.get_logger().info(
                "CHANGE CONFIRMED: "
                f"{event_type} "
                f"{position}"
            )

            self.process_confirmed_change()

    def cancel_pending_change_if_needed(
        self
    ):
        if (
            self.state_machine
            .get_state()
            == DetectionState.CONFIRMING
        ):
            self.state_machine.cancel_confirmation()
            self.clear_current_change()

    def clear_current_change(self):
        self.current_change = None
        self.current_cluster_points = set()

    # ======================================================
    # Confirmed change
    # ======================================================

    def process_confirmed_change(self):
        if (
            self.state_machine
            .get_state()
            != DetectionState.CAPTURING
        ):
            return

        if self.current_change is None:
            self.reset_current_event()
            return

        # 1. 현재 로봇 위치
        robot_pose = (
            self.get_robot_pose()
        )

        if robot_pose is None:
            self.get_logger().warning(
                "Robot pose unavailable. "
                "Event not saved."
            )
            self.reset_current_event()
            return

        # 2. 1회차 순찰에서 저장한
        # 가장 가까운 RGB baseline 검색
        baseline_image_path = (
            self.baseline_images
            .get_image_path(
                x=robot_pose["x"],
                y=robot_pose["y"],
                yaw=robot_pose["yaw"],
            )
        )

        if baseline_image_path is None:
            self.get_logger().warning(
                "No matching RGB baseline "
                "for current pose. "
                "VLM event skipped."
            )
            self.reset_current_event()
            return

        # 3. 변화가 확정됐을 때만
        # 현재 RGB 저장
        current_image_path = (
            self.camera.capture()
        )

        if current_image_path is None:
            self.get_logger().warning(
                "Confirmed change, but "
                "RGB frame unavailable. "
                "Event not saved."
            )
            self.reset_current_event()
            return

        self.get_logger().info(
            "Current RGB captured: "
            f"{current_image_path}"
        )

        self.get_logger().info(
            "Matched baseline RGB: "
            f"{baseline_image_path}"
        )

        self.state_machine.capture_completed()

        # 4. YOLO
        try:
            detected_objects = (
                self.yolo.detect(
                    current_image_path
                )
            )
        except Exception as exc:
            self.get_logger().error(
                f"YOLO error: {exc}"
            )
            detected_objects = []

        if detected_objects:
            labels = ", ".join(
                f'{obj["label"]}'
                f'({obj["confidence"]:.2f})'
                for obj
                in detected_objects
            )

            self.get_logger().info(
                f"YOLO: {labels}"
            )
        else:
            self.get_logger().info(
                "YOLO: no recognized object"
            )

        self.state_machine.analysis_completed()

        # 5. Event JSON
        try:
            event = create_event(
                change=self.current_change,
                detected_objects=(
                    detected_objects
                ),
                image_path=(
                    current_image_path
                ),
                robot_pose=robot_pose,
                save_dir=self.event_dir,
                workplace_id=(
                    self.workplace_id
                ),
            )
        except Exception as exc:
            self.get_logger().error(
                "Event save failed: "
                f"{exc}"
            )
            self.reset_current_event()
            return

        self.get_logger().info(
            "EVENT CREATED:\n"
            + json.dumps(
                event,
                ensure_ascii=False,
                indent=2,
            )
        )

        # 6. Backend 전송
        if self.server_sender.enabled:
            self.server_sender.send_event(
                event=event,
                baseline_image_path=(
                    baseline_image_path
                ),
                current_image_path=(
                    current_image_path
                ),
            )

        # 중요:
        # 이후 순찰도 최초 baseline과 비교해야 하므로
        # 변화가 생겼다고 baseline map/RGB를
        # 자동 갱신하지 않는다.

        self.state_machine.processing_completed()
        self.clear_current_change()

    def reset_current_event(self):
        self.state_machine.reset()
        self.clear_current_change()


def main(args=None):
    rclpy.init(
        args=args
    )

    node = ChangeDetectorNode()

    try:
        rclpy.spin(
            node
        )
    except KeyboardInterrupt:
        pass
    finally:
        node.telemetry_sender.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
import json
import math
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
from scan_observer import build_scan_observation
from state_machine import (
    DetectionState,
    DetectionStateMachine,
)
from yolo_detector import YoloDetector


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

        self.capture_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.event_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ==================================================
        # Baseline
        # ==================================================

        self.baseline = (
            BaselineManager()
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

        # 여러 confirmation scan에서 본 영역을 합쳐서
        # baseline 갱신에 사용
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

        self.get_logger().info(
            "Robot Change Detector started"
        )
        self.get_logger().info(
            "ADDED + REMOVED enabled"
        )
        self.get_logger().info(
            "No confirmed change = "
            "no JPG / no JSON / no YOLO"
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
    # Baseline
    # ======================================================

    def map_callback(self, msg):
        if self.baseline.map_ready:
            return

        self.baseline.set_baseline_map(
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
        # 평소에는 저장하지 않음.
        # 변화 확정 때 사용할 최신 frame만 보관.
        self.camera.update_frame(msg)

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
            "yaw": float(yaw),
        }

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

        # --------------------------------------------------
        # ADDED
        #
        # 이전 FREE
        # 현재 LiDAR endpoint 존재
        # --------------------------------------------------

        added_points = [
            point
            for point in observation[
                "hit_points"
            ]
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
                    "required_count": (
                        ADDED_CONFIRM_COUNT
                    ),
                    "score": len(cluster),
                }
            )

        # --------------------------------------------------
        # REMOVED
        #
        # 이전 OCCUPIED
        # 현재 LiDAR ray가 그 cell을 통과해서
        # 더 뒤쪽 endpoint까지 실제로 관측함
        #
        # "점이 안 찍혔다"만으로 제거 판정하지 않음.
        # --------------------------------------------------

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
                    "required_count": (
                        REMOVED_CONFIRM_COUNT
                    ),
                    "score": len(cluster),
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

        # 확인 중에는 같은 종류 + 같은 위치 후보만 이어감.
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
                    change["position"]["x"],
                    change["position"]["y"],
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
                        (d, candidate)
                    )

            if not matching:
                return None

            matching.sort(
                key=lambda item: item[0]
            )

            return matching[0][1]

        # 새 감시 상태에서는 가장 강한 cluster부터.
        return max(
            candidates,
            key=lambda item: item[
                "score"
            ],
        )

    # ======================================================
    # Main scan callback
    # ======================================================

    def scan_callback(self, scan_msg):
        self.last_scan_stamp = (
            scan_msg.header.stamp
        )

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

        # --------------------------------------------------
        # 첫 발견
        # --------------------------------------------------

        if (
            state
            == DetectionState.MONITORING
        ):
            self.current_change = (
                change
            )
            self.current_cluster_points = (
                set(cluster)
            )

            self.state_machine.start_confirmation(
                position=position,
                event_type=event_type,
                required_count=(
                    required_count
                ),
            )

            self.get_logger().info(
                f"CHANGE CANDIDATE: "
                f"{event_type} "
                f"{position} "
                f"1/{required_count}"
            )

            return

        # --------------------------------------------------
        # 연속 확인
        # --------------------------------------------------

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

            # 여기까지 왔으면 확정
            self.current_change = (
                change
            )

            # 여러 scan에서 관측된 변화 영역을 합침
            self.current_cluster_points.update(
                cluster
            )

            self.get_logger().info(
                f"CHANGE CONFIRMED: "
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
    # Confirmed:
    # RealSense -> YOLO -> pose -> JSON -> baseline update
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

        # 1. 변화가 확정된 경우에만 RealSense 저장
        image_path = (
            self.camera.capture()
        )

        if image_path is None:
            self.get_logger().warning(
                "Confirmed change, "
                "but RGB frame unavailable. "
                "Event not saved."
            )
            self.reset_current_event()
            return

        self.get_logger().info(
            f"Captured: {image_path}"
        )

        self.state_machine.capture_completed()

        # 2. 변화가 확정된 경우에만 YOLO 1회
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

        # 3. Robot pose
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

        # 4. JSON
        try:
            event = create_event(
                change=self.current_change,
                detected_objects=(
                    detected_objects
                ),
                image_path=image_path,
                robot_pose=robot_pose,
                save_dir=self.event_dir,
            )
        except Exception as exc:
            self.get_logger().error(
                f"Event save failed: {exc}"
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

        # 5. 새 상황을 baseline에 반영
        cluster_points_for_update = list(
            self.current_cluster_points
        )

        event_type = (
            self.current_change[
                "event_type"
            ]
        )

        if event_type == "ADDED":
            updated_cells = (
                self.baseline
                .mark_points_occupied(
                    cluster_points_for_update,
                    padding_cells=(
                        BASELINE_PADDING_CELLS
                    ),
                )
            )

        elif event_type == "REMOVED":
            updated_cells = (
                self.baseline
                .mark_points_free(
                    cluster_points_for_update,
                    padding_cells=(
                        BASELINE_PADDING_CELLS
                    ),
                )
            )

        else:
            updated_cells = 0

        self.get_logger().info(
            f"Baseline updated after "
            f"{event_type}: "
            f"{updated_cells} cells"
        )

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
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

import math

import rclpy
from rclpy.qos import (
    QoSProfile,
    ReliabilityPolicy,
    DurabilityPolicy,
    HistoryPolicy,
    qos_profile_sensor_data,
)
from rclpy.node import Node
from rclpy.time import Time

from sensor_msgs.msg import LaserScan, Image
from nav_msgs.msg import OccupancyGrid
from tf2_ros import Buffer, TransformListener

from coordinate_converter import scan_to_map_points
from config import CONFIRM_COUNT, POSITION_TOLERANCE
from baseline_manager import BaselineManager
from cluster_manager import cluster_points, get_center
from change_detector import detect_change
from camera_manager import CameraManager
from yolo_detector import YoloDetector
from event_manager import create_event

from state_machine import (
    DetectionState,
    DetectionStateMachine,
)


class ChangeDetectorNode(Node):

    def __init__(self):

        super().__init__(
            "robot_change_detector"
        )

        # ==================================================
        # 기준 데이터
        # ==================================================

        self.baseline = BaselineManager(
           
        )

        # ==================================================
        # TF
        # ==================================================

        self.tf_buffer = Buffer()

        self.tf_listener = TransformListener(
            self.tf_buffer,
            self
        )

        # ==================================================
        # Camera
        # ==================================================

        self.camera = CameraManager(
            save_dir="captures"
        )

        # ==================================================
        # YOLO
        # ==================================================

        self.yolo = YoloDetector(
            model_path="yolo11n.pt",
            confidence=0.40
        )

        # ==================================================
        # Detection State Machine
        # ==================================================

        self.state_machine = DetectionStateMachine(
            confirm_count=CONFIRM_COUNT,
            position_threshold=POSITION_TOLERANCE
        )

        # ==================================================
        # 현재 확인 중인 Change
        # ==================================================

        self.current_change = None

        # ==================================================
        # /map 구독
        # ==================================================
        map_qos = QoSProfile(  
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.map_subscription = (
            self.create_subscription(
                OccupancyGrid,
                "/map",
                self.map_callback,
                map_qos
            )
        )

        # ==================================================
        # /scan 구독
        # ==================================================

        self.scan_subscription = (
            self.create_subscription(
                LaserScan,
                "/scan",
                self.scan_callback,
                qos_profile_sensor_data
            )
        )

        # ==================================================
        # RealSense RGB 구독
        # ==================================================

        self.camera_subscription = (
            self.create_subscription(
                Image,
                "/camera/camera/color/image_raw",
                self.camera_callback,
                qos_profile_sensor_data
            )
        )

        self.get_logger().info(
            "Robot Change Detector started"
        )

    # ======================================================
    # 기준 지도
    # ======================================================

    def map_callback(self, msg):

        if self.baseline.map_ready:
            return

        self.baseline.set_baseline_map(
            msg
        )

        self.get_logger().info(
            "Baseline map saved"
        )

        self.get_logger().info(
            f"Map size: "
            f"{self.baseline.width} x "
            f"{self.baseline.height}"
        )

        self.get_logger().info(
            f"Resolution: "
            f"{self.baseline.resolution} m/cell"
        )

    # ======================================================
    # RealSense Camera
    # ======================================================

    def camera_callback(self, msg):

        self.camera.update_frame(
            msg
        )

    # ======================================================
    # Robot Pose
    # ======================================================

    def get_robot_pose(self):
        """
        TF에서 map 기준 로봇의
        x, y, yaw를 가져옵니다.
        """

        try:

            transform = (
                self.tf_buffer.lookup_transform(
                    "map",
                    "base_link",
                    Time()
                )
            )

        except Exception as e:

            self.get_logger().warning(
                f"Robot pose unavailable: {e}"
            )

            return None

        # -----------------------------------------
        # 위치
        # -----------------------------------------

        translation = (
            transform.transform.translation
        )

        x = float(
            translation.x
        )

        y = float(
            translation.y
        )

        # -----------------------------------------
        # 방향
        # -----------------------------------------

        rotation = (
            transform.transform.rotation
        )

        qx = rotation.x
        qy = rotation.y
        qz = rotation.z
        qw = rotation.w

        # Quaternion -> Yaw
        yaw = math.atan2(
            2.0 * (
                qw * qz
                + qx * qy
            ),
            1.0 - 2.0 * (
                qy * qy
                + qz * qz
            )
        )

        return {
            "x": x,
            "y": y,
            "yaw": yaw
        }

    # ======================================================
    # LiDAR
    # ======================================================

    def scan_callback(self, scan_msg):

        # --------------------------------------------------
        # 처리 중이면 새로운 Scan 처리 안 함
        # --------------------------------------------------

        state = (
            self.state_machine.get_state()
        )

        if state in (
            DetectionState.CAPTURING,
            DetectionState.ANALYZING,
            DetectionState.PROCESSING,
        ):
            return

        # --------------------------------------------------
        # 기준 지도 확인
        # --------------------------------------------------

        if not self.baseline.map_ready:

            self.get_logger().warning(
                "Waiting for baseline map..."
            )

            return

        # --------------------------------------------------
        # LiDAR frame
        # --------------------------------------------------

        lidar_frame = (
            scan_msg.header.frame_id
        )

        # --------------------------------------------------
        # TF 조회
        # --------------------------------------------------

        try:

            transform = (
                self.tf_buffer.lookup_transform(
                    "map",
                    lidar_frame,
                    Time()
                )
            )

        except Exception as e:

            self.get_logger().warning(
                f"TF unavailable: {e}"
            )

            return

        # --------------------------------------------------
        # LaserScan -> map 좌표
        # --------------------------------------------------

        lidar_points = (
            scan_to_map_points(
                scan_msg,
                transform
            )
        )

        if not lidar_points:
            return

        # --------------------------------------------------
        # 기준 지도와 비교
        #
        # 기준 지도에서 FREE였던 위치에
        # 현재 LiDAR 장애물이 나타났는지 확인
        # --------------------------------------------------

        changed_points = []

        for x, y in lidar_points:

            if self.baseline.is_free(
                x,
                y
            ):

                changed_points.append(
                    (x, y)
                )

        # --------------------------------------------------
        # 변화 없음
        # --------------------------------------------------

        if not changed_points:

            if (
                self.state_machine.get_state()
                == DetectionState.CONFIRMING
            ):

                self.get_logger().info(
                    "Change disappeared "
                    "during confirmation"
                )

                self.state_machine.cancel_confirmation()

                self.current_change = None

            return

        # --------------------------------------------------
        # 가까운 변화 좌표 묶기
        # --------------------------------------------------

        clusters = cluster_points(
            changed_points
        )

        # --------------------------------------------------
        # 너무 작은 Cluster 제거
        # --------------------------------------------------

        valid_clusters = []

        for cluster in clusters:

            if len(cluster) >= 3:

                valid_clusters.append(
                    cluster
                )

        # --------------------------------------------------
        # 유효한 변화 없음
        # --------------------------------------------------

        if not valid_clusters:

            if (
                self.state_machine.get_state()
                == DetectionState.CONFIRMING
            ):

                self.state_machine.cancel_confirmation()

                self.current_change = None

            return

        # --------------------------------------------------
        # 가장 큰 변화 영역 선택
        # --------------------------------------------------

        largest_cluster = max(
            valid_clusters,
            key=len
        )

        center = get_center(
            largest_cluster
        )

        self.get_logger().info(
            f"CHANGE CANDIDATE: "
            f"{center} "
            f"({len(largest_cluster)} points)"
        )

        # --------------------------------------------------
        # Change Detector
        # --------------------------------------------------

        change = detect_change(
            position=center,
            past_state=0,
            current_state=1
        )

        if change is None:
            return

        position = (
            change["position"]["x"],
            change["position"]["y"],
        )

        event_type = (
            change["event_type"]
        )

        # ==================================================
        # State Machine
        # ==================================================

        state = (
            self.state_machine.get_state()
        )

        # --------------------------------------------------
        # 최초 변화 발견
        # --------------------------------------------------

        if state == DetectionState.MONITORING:

            self.current_change = change

            self.get_logger().info(
                f"New change candidate: "
                f"{event_type} "
                f"{position}"
            )

            self.state_machine.start_confirmation(
                position=position,
                event_type=event_type
            )

            return

        # --------------------------------------------------
        # 변화 확인 중
        # --------------------------------------------------

        if state == DetectionState.CONFIRMING:

            confirmed = (
                self.state_machine.confirm_detection(
                    position=position,
                    event_type=event_type
                )
            )

            # ----------------------------------------------
            # 아직 확정되지 않음
            # ----------------------------------------------

            if not confirmed:

                if (
                    self.state_machine.get_state()
                    == DetectionState.MONITORING
                ):

                    self.get_logger().info(
                        "Change candidate rejected"
                    )

                    self.current_change = None

                return

            # ----------------------------------------------
            # 변화 확정
            # ----------------------------------------------

            self.current_change = change

            self.get_logger().info(
                f"CHANGE CONFIRMED: "
                f"{event_type} "
                f"{position}"
            )

            self.process_confirmed_change()

    # ======================================================
    # 확정된 변화 처리
    # ======================================================

    def process_confirmed_change(self):

        # --------------------------------------------------
        # CAPTURING 상태 확인
        # --------------------------------------------------

        if (
            self.state_machine.get_state()
            != DetectionState.CAPTURING
        ):
            return

        if self.current_change is None:

            self.get_logger().warning(
                "Confirmed change data unavailable"
            )

            self.state_machine.reset()

            return

        # ==================================================
        # Camera Capture
        # ==================================================

        image_path = (
            self.camera.capture()
        )

        if image_path is None:

            self.get_logger().warning(
                "Camera frame unavailable"
            )

            self.state_machine.reset()

            self.current_change = None

            return

        self.get_logger().info(
            f"Captured: {image_path}"
        )

        # --------------------------------------------------
        # CAPTURING -> ANALYZING
        # --------------------------------------------------

        self.state_machine.capture_completed()

        # ==================================================
        # YOLO
        # ==================================================

        try:

            detected_objects = (
                self.yolo.detect(
                    image_path
                )
            )

        except Exception as e:

            self.get_logger().error(
                f"YOLO error: {e}"
            )

            self.state_machine.reset()

            self.current_change = None

            return

        # ==================================================
        # YOLO 결과
        # ==================================================

        if detected_objects:

            self.get_logger().info(
                f"YOLO detected "
                f"{len(detected_objects)} object(s)"
            )

            for obj in detected_objects:

                label = obj["label"]

                confidence = (
                    obj["confidence"]
                )

                self.get_logger().info(
                    f"  - {label} "
                    f"(confidence={confidence})"
                )

        else:

            position = (
                self.current_change[
                    "position"
                ]
            )

            self.get_logger().info(
                f"Change detected at "
                f"{position}, "
                f"but YOLO found no object"
            )

        # --------------------------------------------------
        # ANALYZING -> PROCESSING
        # --------------------------------------------------

        self.state_machine.analysis_completed()

        # ==================================================
        # Robot Pose
        # ==================================================

        robot_pose = (
            self.get_robot_pose()
        )

        if robot_pose is None:

            self.get_logger().warning(
                "Robot pose unavailable. "
                "Event will not be created."
            )

            self.state_machine.reset()

            self.current_change = None

            return

        self.get_logger().info(
            f"Robot pose: "
            f"x={robot_pose['x']:.3f}, "
            f"y={robot_pose['y']:.3f}, "
            f"yaw={robot_pose['yaw']:.3f}"
        )

        # ==================================================
        # Event 생성
        # ==================================================

        try:

            event = create_event(
                self.current_change,
                detected_objects,
                image_path,
                robot_pose,
            )

        except Exception as e:

            self.get_logger().error(
                f"Event creation failed: {e}"
            )

            self.state_machine.reset()

            self.current_change = None

            return

        self.get_logger().info(
            f"EVENT CREATED: {event}"
        )

        # ==================================================
        # TODO
        #
        # 다음 단계에서 FastAPI 서버 전송 연결
        # ==================================================

        # --------------------------------------------------
        # PROCESSING -> MONITORING
        # --------------------------------------------------

        self.state_machine.processing_completed()

        self.current_change = None


# ==========================================================
# 실행
# ==========================================================

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
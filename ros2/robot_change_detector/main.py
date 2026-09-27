import rclpy

from rclpy.node import Node
from rclpy.time import Time

from sensor_msgs.msg import LaserScan, Image
from nav_msgs.msg import OccupancyGrid
from tf2_ros import Buffer, TransformListener

from coordinate_converter import scan_to_map_points
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
            "data/baseline.json"
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
        #
        # 같은 위치의 변화가 3번 연속 감지되어야
        # 실제 변화로 확정
        # ==================================================

        self.state_machine = (
            DetectionStateMachine(
                confirm_count=3,
                position_threshold=0.3
            )
        )

        # ==================================================
        # 현재 확인 중인 Change
        # ==================================================

        self.current_change = None

        # ==================================================
        # /map 구독
        # ==================================================

        self.map_subscription = (
            self.create_subscription(
                OccupancyGrid,
                "/map",
                self.map_callback,
                10
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
                10
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
                10
            )
        )

        self.get_logger().info(
            "Robot Change Detector started"
        )

    # ======================================================
    # 기준 지도
    # ======================================================

    def map_callback(self, msg):

        # 이미 기준 지도를 저장했다면
        # 이후 /map 업데이트는 무시
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
    # LiDAR
    # ======================================================

    def scan_callback(self, scan_msg):

        # --------------------------------------------------
        # 처리 중이면 새로운 Scan 이벤트 처리 안 함
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

        lidar_frame = (
            scan_msg.header.frame_id
        )

        # --------------------------------------------------
        # TF 조회
        #
        # LiDAR 좌표계 → map 좌표계
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
        # LaserScan → map 좌표
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
        # 기준 지도 = FREE
        # 현재 LiDAR = 물체 있음
        #
        # 0 → 1
        #
        # 현재 단계에서는 ADDED 변화 탐지
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

            # 확인 중이던 변화가 있었는데
            # 다음 Scan에서 사라졌다면 취소
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

        # 유효한 변화 없음
        if not valid_clusters:

            if (
                self.state_machine.get_state()
                == DetectionState.CONFIRMING
            ):

                self.state_machine.cancel_confirmation()

                self.current_change = None

            return

        # --------------------------------------------------
        # 현재 버전에서는 한 번에
        # 하나의 변화 영역만 추적
        #
        # 가장 큰 Cluster를 우선 처리
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
        #
        # 기준 FREE(0)
        # 현재 물체 존재(1)
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

            # ------------------------------------------------
            # 같은 변화가 아니라면
            # State Machine이 MONITORING으로 복귀
            # ------------------------------------------------

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

            # ------------------------------------------------
            # 3회 연속 확인 완료
            # ------------------------------------------------

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

            # 촬영 실패 시
            # 현재 이벤트 처리 취소
            self.state_machine.reset()

            self.current_change = None

            return

        self.get_logger().info(
            f"Captured: {image_path}"
        )

        # --------------------------------------------------
        # CAPTURING → ANALYZING
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
        # ANALYZING → PROCESSING
        # --------------------------------------------------

        self.state_machine.analysis_completed()

        # ==================================================
        # Event 생성
        # ==================================================

        event = create_event(
            self.current_change,
            detected_objects
        )

        self.get_logger().info(
            f"EVENT CREATED: {event}"
        )

        # ==================================================
        # TODO
        #
        # 다음 단계에서 여기에
        # FastAPI 서버 전송을 연결
        #
        # Pi → Mac AI Server
        #
        # 예:
        #
        # send_event(event, image_path)
        #
        # ==================================================

        # --------------------------------------------------
        # PROCESSING → MONITORING
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
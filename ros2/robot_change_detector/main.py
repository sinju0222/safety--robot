import rclpy

from rclpy.node import Node
from rclpy.time import Time

from sensor_msgs.msg import LaserScan, Image
from nav_msgs.msg import OccupancyGrid
from tf2_ros import Buffer, TransformListener

from coordinate_converter import scan_to_map_points
from baseline_manager import BaselineManager
from cluster_manager import cluster_points, get_center
from camera_manager import CameraManager
from yolo_detector import YoloDetector


class ChangeDetectorNode(Node):

    def __init__(self):

        super().__init__("robot_change_detector")

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
        # /map 구독
        # ==================================================

        self.map_subscription = self.create_subscription(
            OccupancyGrid,
            "/map",
            self.map_callback,
            10
        )

        # ==================================================
        # /scan 구독
        # ==================================================

        self.scan_subscription = self.create_subscription(
            LaserScan,
            "/scan",
            self.scan_callback,
            10
        )

        # ==================================================
        # RealSense RGB 구독
        # ==================================================

        self.camera_subscription = self.create_subscription(
            Image,
            "/camera/camera/color/image_raw",
            self.camera_callback,
            10
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

        self.baseline.set_baseline_map(msg)

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

        self.camera.update_frame(msg)

    # ======================================================
    # LiDAR
    # ======================================================

    def scan_callback(self, scan_msg):

        # --------------------------------------------------
        # 기준 지도 확인
        # --------------------------------------------------

        if not self.baseline.map_ready:

            self.get_logger().warning(
                "Waiting for baseline map..."
            )

            return

        lidar_frame = scan_msg.header.frame_id

        # --------------------------------------------------
        # TF 조회
        #
        # LiDAR 좌표계 → map 좌표계
        # --------------------------------------------------

        try:

            transform = self.tf_buffer.lookup_transform(
                "map",
                lidar_frame,
                Time()
            )

        except Exception as e:

            self.get_logger().warning(
                f"TF unavailable: {e}"
            )

            return

        # --------------------------------------------------
        # LaserScan → map 좌표
        # --------------------------------------------------

        lidar_points = scan_to_map_points(
            scan_msg,
            transform
        )

        if not lidar_points:
            return

        # --------------------------------------------------
        # 기준 지도와 비교
        #
        # 과거 지도 = FREE
        # 현재 LiDAR = 물체 있음
        #
        # 즉,
        #
        # 0 → 1
        #
        # 후보 좌표 추출
        # --------------------------------------------------

        changed_points = []

        for x, y in lidar_points:

            if self.baseline.is_free(x, y):

                changed_points.append(
                    (x, y)
                )

        # --------------------------------------------------
        # 변화 없음
        # --------------------------------------------------

        if not changed_points:
            return

        # --------------------------------------------------
        # 가까운 변화 좌표 묶기
        # --------------------------------------------------

        clusters = cluster_points(
            changed_points
        )

        # --------------------------------------------------
        # 각 Change Region 처리
        # --------------------------------------------------

        for cluster in clusters:

            # 너무 작은 cluster는 일단 무시
            #
            # LiDAR 점 1~2개 때문에
            # 이벤트가 발생하는 것을 어느 정도 방지
            if len(cluster) < 3:
                continue

            # Cluster 대표 좌표
            center = get_center(
                cluster
            )

            self.get_logger().info(
                f"NEW CHANGE REGION: "
                f"{center} "
                f"({len(cluster)} points)"
            )

            # ==================================================
            # RealSense 캡처
            # ==================================================

            image_path = (
                self.camera.capture()
            )

            if image_path is None:

                self.get_logger().warning(
                    "Camera frame unavailable"
                )

                continue

            self.get_logger().info(
                f"Captured: {image_path}"
            )

            # ==================================================
            # YOLO 객체 탐지
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

                continue

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
                    confidence = obj["confidence"]

                    self.get_logger().info(
                        f"  - {label} "
                        f"(confidence={confidence})"
                    )

            else:

                self.get_logger().info(
                    f"Change detected at {center}, "
                    f"but YOLO found no object"
                )


# ==========================================================
# 실행
# ==========================================================

def main(args=None):

    rclpy.init(args=args)

    node = ChangeDetectorNode()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:

        pass

    finally:

        node.destroy_node()

        rclpy.shutdown()


if __name__ == "__main__":
    main()
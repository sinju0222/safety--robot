import rclpy

from rclpy.node import Node
from rclpy.time import Time

from sensor_msgs.msg import LaserScan

from tf2_ros import (
    Buffer,
    TransformListener
)

from coordinate_converter import (
    scan_to_map_points
)


class LidarNode(Node):

    def __init__(self):

        super().__init__(
            "change_detector_lidar"
        )

        # 가장 최근 LiDAR 좌표
        self.latest_points = []

        # -------------------------
        # TF
        # -------------------------

        self.tf_buffer = Buffer()

        self.tf_listener = TransformListener(
            self.tf_buffer,
            self
        )

        # -------------------------
        # /scan 구독
        # -------------------------

        self.scan_subscription = (
            self.create_subscription(
                LaserScan,
                "/scan",
                self.scan_callback,
                10
            )
        )

        self.get_logger().info(
            "LiDAR Node started"
        )

    def scan_callback(self, scan_msg):

        lidar_frame = (
            scan_msg.header.frame_id
        )

        # -------------------------
        # map <- LiDAR TF 조회
        # -------------------------

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

        # -------------------------
        # LaserScan → map 좌표
        # -------------------------

        points = scan_to_map_points(
            scan_msg,
            transform
        )

        self.latest_points = points

        self.get_logger().info(
            f"LiDAR points: {len(points)}"
        )


def main(args=None):

    rclpy.init(args=args)

    node = LidarNode()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:

        pass

    finally:

        node.destroy_node()

        rclpy.shutdown()


if __name__ == "__main__":
    main()
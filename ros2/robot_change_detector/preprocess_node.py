
#!/usr/bin/env python3

import json
import math
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import cv2
from cv_bridge import CvBridge

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.duration import Duration
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan, Image
from tf2_ros import Buffer, TransformListener


MAP_TOPIC = "/map"
SCAN_TOPIC = "/scan"
RGB_TOPIC = "/camera/camera/color/image_raw"

MAP_FRAME = "map"
BASE_FRAME = "base_link"

CLUSTER_DISTANCE = 0.20
CONFIRM_COUNT = 3
POSITION_TOLERANCE = 0.30
MIN_CLUSTER_POINTS = 3
MIN_LIDAR_RANGE = 0.35

KST = timezone(timedelta(hours=9))


def yaw_from_quaternion(q):
    return math.atan2(
        2.0 * (q.w * q.z + q.x * q.y),
        1.0 - 2.0 * (q.y * q.y + q.z * q.z),
    )


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def cluster_points(points):
    clusters = []
    for point in points:
        found = None
        for cluster in clusters:
            if any(dist(point, p) <= CLUSTER_DISTANCE for p in cluster):
                found = cluster
                break
        if found is None:
            clusters.append([point])
        else:
            found.append(point)
    return clusters


class Baseline:
    def __init__(self):
        self.ready = False

    def set(self, msg):
        self.width = int(msg.info.width)
        self.height = int(msg.info.height)
        self.resolution = float(msg.info.resolution)
        self.ox = float(msg.info.origin.position.x)
        self.oy = float(msg.info.origin.position.y)
        self.oyaw = yaw_from_quaternion(msg.info.origin.orientation)
        self.data = list(msg.data)
        self.ready = True

    def is_free(self, x, y):
        dx = x - self.ox
        dy = y - self.oy
        c = math.cos(self.oyaw)
        s = math.sin(self.oyaw)
        local_x = c * dx + s * dy
        local_y = -s * dx + c * dy
        gx = int(math.floor(local_x / self.resolution))
        gy = int(math.floor(local_y / self.resolution))

        if not (0 <= gx < self.width and 0 <= gy < self.height):
            return False

        return self.data[gy * self.width + gx] == 0


class RobotChangePreprocess(Node):
    def __init__(self):
        super().__init__("robot_change_preprocess")

        self.declare_parameter("use_sim_time", False)

        self.output = Path("robot_change_output")
        self.captures = self.output / "captures"
        self.events = self.output / "events"
        self.captures.mkdir(parents=True, exist_ok=True)
        self.events.mkdir(parents=True, exist_ok=True)

        self.baseline = Baseline()
        self.bridge = CvBridge()
        self.latest_rgb = None
        self.last_scan_stamp = None

        self.pending_position = None
        self.confirm_count = 0
        self.reported_positions = []
        self.event_number = self.next_event_number()

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        map_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        scan_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        camera_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.create_subscription(
            OccupancyGrid, MAP_TOPIC, self.map_callback, map_qos
        )
        self.create_subscription(
            LaserScan, SCAN_TOPIC, self.scan_callback, scan_qos
        )
        self.create_subscription(
            Image, RGB_TOPIC, self.rgb_callback, camera_qos
        )

        self.get_logger().info("Robot Change Preprocess started")

    def next_event_number(self):
        maximum = 0
        for path in self.events.glob("event_*.json"):
            match = re.search(r"event_(\d+)\.json$", path.name)
            if match:
                maximum = max(maximum, int(match.group(1)))
        return maximum + 1

    def map_callback(self, msg):
        if self.baseline.ready:
            return
        self.baseline.set(msg)
        self.get_logger().info(
            f"BASELINE MAP SAVED: "
            f"{self.baseline.width}x{self.baseline.height}, "
            f"{self.baseline.resolution:.4f} m/cell"
        )

    def rgb_callback(self, msg):
        try:
            self.latest_rgb = self.bridge.imgmsg_to_cv2(
                msg, desired_encoding="bgr8"
            )
        except Exception as exc:
            self.get_logger().error(f"RGB error: {exc}")

    def lookup(self, target, source, stamp):
        try:
            return self.tf_buffer.lookup_transform(
                target, source, Time.from_msg(stamp),
                timeout=Duration(seconds=0.15)
            )
        except Exception:
            try:
                return self.tf_buffer.lookup_transform(
                    target, source, Time()
                )
            except Exception:
                return None

    def scan_callback(self, msg):
        self.last_scan_stamp = msg.header.stamp

        if not self.baseline.ready:
            return

        tf = self.lookup(
            MAP_FRAME,
            msg.header.frame_id,
            msg.header.stamp
        )
        if tf is None:
            return

        tx = tf.transform.translation.x
        ty = tf.transform.translation.y
        yaw = yaw_from_quaternion(tf.transform.rotation)
        c = math.cos(yaw)
        s = math.sin(yaw)

        candidates = []

        for i, r in enumerate(msg.ranges):
            if not math.isfinite(r):
                continue
            if r < max(msg.range_min, MIN_LIDAR_RANGE):
                continue
            if r > msg.range_max:
                continue

            angle = msg.angle_min + i * msg.angle_increment
            lx = r * math.cos(angle)
            ly = r * math.sin(angle)
            x = tx + lx * c - ly * s
            y = ty + lx * s + ly * c

            if self.baseline.is_free(x, y):
                candidates.append((x, y))

        clusters = [
            c for c in cluster_points(candidates)
            if len(c) >= MIN_CLUSTER_POINTS
        ]

        if not clusters:
            self.reset_confirmation()
            return

        cluster = max(clusters, key=len)
        center = (
            sum(p[0] for p in cluster) / len(cluster),
            sum(p[1] for p in cluster) / len(cluster),
        )

        center = (round(center[0], 3), round(center[1], 3))

        if any(
            dist(center, old) <= POSITION_TOLERANCE
            for old in self.reported_positions
        ):
            return

        if self.pending_position is None:
            self.pending_position = center
            self.confirm_count = 1
        elif dist(self.pending_position, center) <= POSITION_TOLERANCE:
            self.confirm_count += 1
        else:
            self.pending_position = center
            self.confirm_count = 1

        self.get_logger().info(
            f"CHANGE CANDIDATE {center} "
            f"{self.confirm_count}/{CONFIRM_COUNT}"
        )

        if self.confirm_count >= CONFIRM_COUNT:
            position = self.pending_position
            self.reset_confirmation()
            self.create_event(position)

    def reset_confirmation(self):
        self.pending_position = None
        self.confirm_count = 0

    def robot_pose(self):
        if self.last_scan_stamp is None:
            return None

        tf = self.lookup(
            MAP_FRAME,
            BASE_FRAME,
            self.last_scan_stamp
        )
        if tf is None:
            return None

        t = tf.transform.translation
        q = tf.transform.rotation

        return {
            "x": round(float(t.x), 3),
            "y": round(float(t.y), 3),
            "yaw": round(float(yaw_from_quaternion(q)), 3),
        }

    def create_event(self, position):
        pose = self.robot_pose()

        # 실제 값이 없는데 0.0 같은 가짜 값을 넣지 않는다.
        if pose is None:
            self.get_logger().warning(
                "Event skipped: robot pose unavailable"
            )
            return

        if self.latest_rgb is None:
            self.get_logger().warning(
                "Event skipped: RGB frame unavailable"
            )
            return

        number = self.event_number
        event_id = f"evt_{number:03d}"
        image_name = f"change_{number:03d}.jpg"

        image_path = self.captures / image_name
        if not cv2.imwrite(str(image_path), self.latest_rgb):
            self.get_logger().error("Image save failed")
            return

        stamp = self.last_scan_stamp
        seconds = stamp.sec + stamp.nanosec / 1e9
        timestamp = datetime.fromtimestamp(
            seconds, tz=timezone.utc
        ).astimezone(KST).isoformat()

        event = {
            "event_id": event_id,
            "timestamp": timestamp,
            "change": {
                "type": "ADDED",
                "x": round(float(position[0]), 3),
                "y": round(float(position[1]), 3),
            },
            "robot": pose,
            "image": image_name,
        }

        json_path = self.events / f"event_{number:03d}.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(event, f, ensure_ascii=False, indent=2)

        self.reported_positions.append(position)
        self.event_number += 1

        self.get_logger().info(
            "EVENT CREATED:\n"
            + json.dumps(event, ensure_ascii=False, indent=2)
        )


def main(args=None):
    rclpy.init(args=args)
    node = RobotChangePreprocess()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

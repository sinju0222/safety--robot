# ==========================================================
# Change detection settings
# ==========================================================

CLUSTER_DISTANCE = 0.20
POSITION_TOLERANCE = 0.30

# ADDED는 LiDAR hit가 직접 있으므로 3회 확인
ADDED_CONFIRM_COUNT = 3
ADDED_MIN_CLUSTER_POINTS = 3

# REMOVED는 오탐을 더 줄이기 위해 더 보수적으로 확인
REMOVED_CONFIRM_COUNT = 5
REMOVED_MIN_CLUSTER_POINTS = 4

MIN_LIDAR_RANGE = 0.35

# baseline 업데이트 범위
BASELINE_PADDING_CELLS = 2

# REMOVED 판정용 안전장치
# 현재 LiDAR endpoint 바로 앞의 셀은 map/TF 오차로 인해
# 잘못 FREE로 보일 수 있으므로 제거 판정에서 제외
REMOVED_RAY_END_MARGIN_CELLS = 3

# 다른 빔의 현재 hit 주변도 제거 후보에서 제외
REMOVED_HIT_GUARD_CELLS = 2

# range_max에 거의 붙은 측정은 확실한 endpoint로 보지 않음
REMOVED_MAX_RANGE_RATIO = 0.98

# ==========================================================
# Raspberry Pi 4 / 4GB YOLO settings
# ==========================================================

YOLO_MODEL_PATH = "yolo11n.pt"
YOLO_CONFIDENCE = 0.40
YOLO_IMAGE_SIZE = 320
YOLO_MAX_DET = 10

# ==========================================================
# ROS2
# ==========================================================

MAP_TOPIC = "/map"
SCAN_TOPIC = "/scan"
RGB_TOPIC = "/camera/camera/color/image_raw"

MAP_FRAME = "map"
BASE_FRAME = "base_link"

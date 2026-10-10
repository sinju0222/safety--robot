from setuptools import setup

package_name = "robot_change_detector"

setup(
    name=package_name,
    version="0.2.0",
    packages=[],
    py_modules=[
        "main",
        "baseline_manager",
        "camera_manager",
        "change_detector",
        "cluster_manager",
        "config",
        "coordinate_converter",
        "event_manager",
        "scan_observer",
        "state_machine",
        "yolo_detector",
        "server_sender",
        "telemetry_sender",
        "patrol_controller",
    ],
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        (
            "share/" + package_name,
            ["package.xml"],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="robot_team",
    maintainer_email="team@example.com",
    description=(
        "TurtleBot ADDED/REMOVED change detection, "
        "RealSense capture, YOLO and event generation"
    ),
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "robot_change_detector = main:main",
            "patrol_controller = patrol_controller:main",
        ],
    },
)

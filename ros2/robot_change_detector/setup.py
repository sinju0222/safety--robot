from setuptools import setup


package_name = "robot_change_detector"


setup(
    name=package_name,
    version="0.0.1",

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
        "state_machine",
        "yolo_detector",
    ],

    data_files=[
        (
            "share/ament_index/resource_index/packages",
            [
                "resource/" + package_name
            ],
        ),
        (
            "share/" + package_name,
            [
                "package.xml"
            ],
        ),
    ],

    install_requires=[
        "setuptools",
    ],

    zip_safe=True,

    entry_points={
        "console_scripts": [
            "robot_change_detector = main:main",
        ],
    },
)
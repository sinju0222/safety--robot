import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(BASE_DIR),
)

from risk_engine import RiskEngine


def main():
    engine = RiskEngine()

    test_cases = [
        {
            "name": "안전구역 작은 변화",
            "object_size": 0.05,
            "in_robot_path": 0,
            "distance_to_path": 3.0,
            "change_type": "moved",
            "zone_type": "safe",
        },
        {
            "name": "작업구역 변화",
            "object_size": 0.40,
            "in_robot_path": 0,
            "distance_to_path": 1.0,
            "change_type": "added",
            "zone_type": "work",
        },
        {
            "name": "통로 근처 장애물",
            "object_size": 0.60,
            "in_robot_path": 0,
            "distance_to_path": 0.30,
            "change_type": "added",
            "zone_type": "aisle",
        },
        {
            "name": "통로 직접 차단",
            "object_size": 0.80,
            "in_robot_path": 1,
            "distance_to_path": 0.05,
            "change_type": "added",
            "zone_type": "aisle",
        },
        {
            "name": "접근제한구역 변화",
            "object_size": 0.50,
            "in_robot_path": 0,
            "distance_to_path": 1.0,
            "change_type": "moved",
            "zone_type": "restricted",
        },
    ]

    print("=" * 60)
    print("RISK ENGINE TEST")
    print("=" * 60)

    for case in test_cases:
        result = engine.predict(
            object_size=case["object_size"],
            in_robot_path=case["in_robot_path"],
            distance_to_path=case["distance_to_path"],
            change_type=case["change_type"],
            zone_type=case["zone_type"],
        )

        print(
            f"\n[{case['name']}]"
        )

        print(
            f"Risk Score : "
            f"{result['risk_score']}"
        )

        print(
            f"Risk Level : "
            f"{result['risk_level']}"
        )


if __name__ == "__main__":
    main()

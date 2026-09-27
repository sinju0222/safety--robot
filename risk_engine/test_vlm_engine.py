import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(BASE_DIR),
)

from vlm_engine import VLMEngine


def main():
    engine = VLMEngine()

    image_path = (
        BASE_DIR
        / "test_images"
        / "aisle_box.jpg"
    )

    print("=" * 60)
    print("VLM RISK ANALYSIS TEST")
    print("=" * 60)

    result = engine.analyze(
        image_path=image_path,
        object_class="box",
        bbox=[210, 160, 470, 420],
        change_type="added",
        zone_type="aisle",
    )

    print(
        f"\nContext Risk Score : "
        f"{result['context_risk_score']}"
    )

    print(
        f"Hazard Type        : "
        f"{result['hazard_type']}"
    )

    print(
        f"Reason             : "
        f"{result['reason']}"
    )


if __name__ == "__main__":
    main()


import copy
import json
from pathlib import Path

import cv2
import numpy as np


# =========================================================
# 경로
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

IMAGE_DIR = (
    BASE_DIR
    / "rosbag_data"
    / "datasets"
)

OUTPUT_DIR = (
    BASE_DIR
    / "augmented"
)

GROUND_TRUTH_PATH = (
    BASE_DIR
    / "pair_ground_truth.json"
)

OUTPUT_GT_PATH = (
    BASE_DIR
    / "augmented_pair_ground_truth.json"
)


# =========================================================
# 증강 설정
# =========================================================

AUGMENTATIONS = [
    "dark",
    "bright",
    "blur",
    "noise",
]

RANDOM_SEED = 20261006

rng = np.random.default_rng(
    RANDOM_SEED
)


# =========================================================
# 이미지 저장
# =========================================================

def save_image(path, image):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    success = cv2.imwrite(
        str(path),
        image,
    )

    if not success:
        raise RuntimeError(
            f"이미지 저장 실패: {path}"
        )


# =========================================================
# 증강 함수
# =========================================================

def create_variants(image):

    # -----------------------------------------
    # 1. 어두운 환경
    # -----------------------------------------

    dark = cv2.convertScaleAbs(
        image,
        alpha=0.65,
        beta=0,
    )

    # -----------------------------------------
    # 2. 밝은 환경
    # -----------------------------------------

    bright = cv2.convertScaleAbs(
        image,
        alpha=1.0,
        beta=45,
    )

    # -----------------------------------------
    # 3. Blur
    # -----------------------------------------

    blur = cv2.GaussianBlur(
        image,
        (7, 7),
        0,
    )

    # -----------------------------------------
    # 4. Camera Noise
    # -----------------------------------------

    noise = rng.normal(
        0,
        10,
        image.shape,
    )

    noisy = (
        image.astype(np.float32)
        + noise
    )

    noisy = np.clip(
        noisy,
        0,
        255,
    ).astype(np.uint8)

    return {
        "dark": dark,
        "bright": bright,
        "blur": blur,
        "noise": noisy,
    }


# =========================================================
# 원본 이미지 목록
# =========================================================

def get_source_images():

    images = sorted(
        IMAGE_DIR.glob("*.jpg")
    )

    if not images:
        raise FileNotFoundError(
            f"JPG 이미지가 없습니다: "
            f"{IMAGE_DIR}"
        )

    return images


# =========================================================
# 이미지 증강
# =========================================================

def augment_images():

    images = get_source_images()

    print()
    print("=" * 60)
    print("실제 TurtleBot 이미지 증강 시작")
    print("=" * 60)

    print(
        f"원본 이미지 수: {len(images)}"
    )

    print(
        f"증강 종류: {len(AUGMENTATIONS)}"
    )

    expected_count = (
        len(images)
        * len(AUGMENTATIONS)
    )

    print(
        f"생성 예정 이미지: "
        f"{expected_count}"
    )

    print()

    generated = 0

    for index, image_path in enumerate(
        images,
        start=1,
    ):

        image = cv2.imread(
            str(image_path)
        )

        if image is None:
            raise RuntimeError(
                f"이미지 읽기 실패: "
                f"{image_path}"
            )

        variants = create_variants(
            image
        )

        for augmentation, result in (
            variants.items()
        ):

            output_path = (
                OUTPUT_DIR
                / augmentation
                / image_path.name
            )

            save_image(
                output_path,
                result,
            )

            generated += 1

        print(
            f"[{index}/{len(images)}] "
            f"{image_path.name} 완료"
        )

    print()
    print(
        f"생성 이미지 수: {generated}"
    )

    return generated


# =========================================================
# Ground Truth 로드
# =========================================================

def load_ground_truth():

    if not GROUND_TRUTH_PATH.exists():
        raise FileNotFoundError(
            f"Ground Truth 없음: "
            f"{GROUND_TRUTH_PATH}"
        )

    with open(
        GROUND_TRUTH_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


# =========================================================
# 증강용 Ground Truth 생성
# =========================================================

def create_augmented_ground_truth():

    original_gt = load_ground_truth()

    original_pairs = original_gt[
        "pairs"
    ]

    augmented_pairs = []

    new_id = 1

    for augmentation in AUGMENTATIONS:

        for pair in original_pairs:

            new_pair = copy.deepcopy(
                pair
            )

            original_pair_id = pair[
                "id"
            ]

            new_pair[
                "id"
            ] = new_id

            new_pair[
                "original_pair_id"
            ] = original_pair_id

            new_pair[
                "augmentation"
            ] = augmentation

            # 이미지 이름은 동일.
            # 실제 폴더만 augmentation별로 다름.
            new_pair[
                "baseline"
            ] = pair[
                "baseline"
            ]

            new_pair[
                "current"
            ] = pair[
                "current"
            ]

            augmented_pairs.append(
                new_pair
            )

            new_id += 1

    output_data = {
        "dataset": {
            "name":
                "real_turtlebot_robustness_evaluation",

            "version":
                "augmented_v1",

            "source":
                "real_turtlebot_images",

            "original_image_count":
                len(
                    get_source_images()
                ),

            "original_pair_count":
                len(
                    original_pairs
                ),

            "augmentations":
                AUGMENTATIONS,

            "augmented_pair_count":
                len(
                    augmented_pairs
                ),

            "pairing_rule":
                (
                    "Baseline and Current use "
                    "the same augmentation. "
                    "Only same-scene pairs are used."
                ),

            "note":
                (
                    "Augmentation changes camera "
                    "conditions only. Ground Truth "
                    "labels remain identical to "
                    "the original pairs."
                ),
        },

        "pairs":
            augmented_pairs,
    }

    with open(
        OUTPUT_GT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    return output_data


# =========================================================
# 이미지 검증
# =========================================================

def validate_images():

    source_images = get_source_images()

    print()
    print("=" * 60)
    print("증강 이미지 검증")
    print("=" * 60)

    missing = []

    for augmentation in AUGMENTATIONS:

        directory = (
            OUTPUT_DIR
            / augmentation
        )

        files = list(
            directory.glob(
                "*.jpg"
            )
        )

        print(
            f"{augmentation}: "
            f"{len(files)}장"
        )

        for source in source_images:

            expected = (
                directory
                / source.name
            )

            if not expected.exists():
                missing.append(
                    str(expected)
                )

    if missing:

        print()
        print(
            "누락 이미지 발견:"
        )

        for path in missing:
            print(path)

        raise RuntimeError(
            "증강 이미지 검증 실패"
        )

    expected_total = (
        len(source_images)
        * len(AUGMENTATIONS)
    )

    actual_total = sum(
        len(
            list(
                (
                    OUTPUT_DIR
                    / augmentation
                ).glob("*.jpg")
            )
        )
        for augmentation
        in AUGMENTATIONS
    )

    if actual_total != expected_total:
        raise RuntimeError(
            "생성 이미지 개수가 "
            "예상값과 다릅니다. "
            f"예상={expected_total}, "
            f"실제={actual_total}"
        )

    print()
    print(
        "모든 증강 이미지 정상"
    )


# =========================================================
# Pair ↔ 이미지 연결 검증
# =========================================================

def validate_pairs(
    augmented_gt,
):

    print()
    print("=" * 60)
    print("Ground Truth ↔ 이미지 검증")
    print("=" * 60)

    pairs = augmented_gt[
        "pairs"
    ]

    missing = []

    for pair in pairs:

        augmentation = pair[
            "augmentation"
        ]

        directory = (
            OUTPUT_DIR
            / augmentation
        )

        baseline = (
            directory
            / pair[
                "baseline"
            ]
        )

        current = (
            directory
            / pair[
                "current"
            ]
        )

        if not baseline.exists():
            missing.append(
                str(baseline)
            )

        if not current.exists():
            missing.append(
                str(current)
            )

    if missing:

        print()
        print(
            "Pair 연결 누락 발견:"
        )

        for path in sorted(
            set(missing)
        ):
            print(path)

        raise RuntimeError(
            "Ground Truth 연결 검증 실패"
        )

    print(
        f"검증 Pair: {len(pairs)}"
    )

    print(
        "모든 Pair ↔ 이미지 연결 정상"
    )


# =========================================================
# Main
# =========================================================

def main():

    if not IMAGE_DIR.exists():
        raise FileNotFoundError(
            f"원본 이미지 폴더 없음: "
            f"{IMAGE_DIR}"
        )

    if not GROUND_TRUTH_PATH.exists():
        raise FileNotFoundError(
            f"Ground Truth 없음: "
            f"{GROUND_TRUTH_PATH}"
        )

    generated = augment_images()

    augmented_gt = (
        create_augmented_ground_truth()
    )

    validate_images()

    validate_pairs(
        augmented_gt
    )

    original_image_count = len(
        get_source_images()
    )

    original_pair_count = len(
        load_ground_truth()[
            "pairs"
        ]
    )

    augmented_pair_count = len(
        augmented_gt[
            "pairs"
        ]
    )

    print()
    print("=" * 60)
    print("증강 데이터셋 생성 완료")
    print("=" * 60)

    print(
        f"원본 이미지: "
        f"{original_image_count}장"
    )

    print(
        f"증강 종류: "
        f"{len(AUGMENTATIONS)}종"
    )

    print(
        f"생성된 증강 이미지: "
        f"{generated}장"
    )

    print(
        f"원본 평가 Pair: "
        f"{original_pair_count}개"
    )

    print(
        f"증강 평가 Pair: "
        f"{augmented_pair_count}개"
    )

    print()
    print(
        "증강 이미지 폴더:"
    )

    print(
        OUTPUT_DIR
    )

    print()
    print(
        "증강 Ground Truth:"
    )

    print(
        OUTPUT_GT_PATH
    )


if __name__ == "__main__":
    main()
import base64
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


# =========================================================
# 경로
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
AI_SERVER_DIR = BASE_DIR.parent

AUGMENTED_DIR = BASE_DIR / "augmented"

GROUND_TRUTH_PATH = (
    BASE_DIR
    / "augmented_pair_ground_truth.json"
)

RESULT_DIR = BASE_DIR / "results"

RESULT_PATH = (
    RESULT_DIR
    / "robustness_results.json"
)

SUMMARY_PATH = (
    RESULT_DIR
    / "robustness_summary.json"
)


# =========================================================
# 환경 변수
# =========================================================

load_dotenv(AI_SERVER_DIR / ".env")

OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY"
)

OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)


# =========================================================
# 최종 후보 모델 2개
# =========================================================

MODELS = {
    "qwen3_vl_32b":
        "qwen/qwen3-vl-32b-instruct",

    "gemini_2_5_flash":
        "google/gemini-2.5-flash",
}


# =========================================================
# 평가 지표
# =========================================================

METRICS = [
    "change_detected",
    "change_type",
    "change_degree",
    "path_occupancy",
    "dangerous_object",
    "policy_A",
    "policy_B",
    "policy_C",
    "all_correct",
]


# =========================================================
# 이미지 인코딩
# =========================================================

def encode_image(path):

    with open(path, "rb") as file:
        return base64.b64encode(
            file.read()
        ).decode("utf-8")


# =========================================================
# JSON 로드
# =========================================================

def load_json(path):

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


# =========================================================
# 기존 결과 로드
# =========================================================

def load_existing_results():

    if not RESULT_PATH.exists():
        return []

    try:
        data = load_json(
            RESULT_PATH
        )

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


# =========================================================
# 결과 저장
# =========================================================

def save_results(results):

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        RESULT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            results,
            file,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# JSON 응답 정리
# =========================================================

def clean_json_response(text):

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# =========================================================
# 프롬프트
# =========================================================

def build_prompt():

    return """
You are a visual safety analysis system for a mobile robot.

You will receive TWO images of the SAME physical scene.

IMAGE 1 = BASELINE
IMAGE 2 = CURRENT

Compare CURRENT against BASELINE.

Do NOT evaluate CURRENT independently.

All judgments must be based on environmental differences
between BASELINE and CURRENT.

--------------------------------------------------
CHANGE TYPE
--------------------------------------------------

NO_CHANGE:
No meaningful environmental change.

ADDED:
An object exists in CURRENT but not in BASELINE.

REMOVED:
An object exists in BASELINE but not in CURRENT.

MOVED:
The same object changed location.

STATE_CHANGED:
The same object changed state, orientation,
posture, or condition.

Examples:
- upright bottle -> fallen bottle
- object orientation changed
- closed box -> opened box

MIXED:
Two or more different change types occurred.

--------------------------------------------------
CHANGE DEGREE
--------------------------------------------------

NONE:
No meaningful change.

SMALL:
One small object is added or removed,
or an object undergoes a small position change.

MEDIUM:
A clear object state change,
a substantial position change,
or multiple small changes occurred.

LARGE:
A large object is added or removed,
multiple substantial changes occurred,
or the change has a major effect on passage.

--------------------------------------------------
PATH OCCUPANCY
--------------------------------------------------

Judge occupancy based on the USABLE WALKING PATH,
not simply on how large the object appears in the image.

UNCHANGED:
No path occupancy change.

UNDER_50:
Changed objects occupy less than approximately
50 percent of the usable walking path.

OVER_50:
Changed objects occupy approximately 50 percent
or more of the usable walking path and
substantially obstruct passage.

--------------------------------------------------
DANGEROUS OBJECT
--------------------------------------------------

dangerous_object is true if a changed object itself
can create a physical hazard.

Examples:
- hand tool
- sharp tool
- hazardous object

A normal bottle or cardboard box is not automatically
a dangerous object.

If the exact tool identity is unclear,
use "hand_tool".

--------------------------------------------------
POLICY A
HUMAN WALKING PASSAGE
--------------------------------------------------

NORMAL:
No meaningful change.

LOW:
Change exists, path occupancy is UNDER_50,
and no dangerous object is involved.

MEDIUM:
A dangerous object appears or changes,
but the path is not substantially blocked.

HIGH:
Changed objects occupy approximately 50 percent
or more of the usable walking path.

HIGH takes priority if the passage is substantially blocked.

--------------------------------------------------
POLICY B
CHANGE MAGNITUDE
--------------------------------------------------

NONE -> NORMAL
SMALL -> LOW
MEDIUM -> MEDIUM
LARGE -> HIGH

--------------------------------------------------
POLICY C
NO CHANGE ALLOWED
--------------------------------------------------

No change -> NORMAL
Any change -> HIGH

--------------------------------------------------
OUTPUT
--------------------------------------------------

Return ONLY valid JSON.

Use exactly this structure:

{
  "change": {
    "change_detected": true,
    "change_type": "ADDED",
    "added_objects": [],
    "removed_objects": [],
    "moved_objects": [],
    "state_changed_objects": [],
    "change_degree": "SMALL",
    "path_occupancy": "UNDER_50",
    "dangerous_object": false
  },
  "policy_results": {
    "A": {
      "risk_level": "LOW",
      "reason": ""
    },
    "B": {
      "risk_level": "LOW",
      "reason": ""
    },
    "C": {
      "risk_level": "HIGH",
      "reason": ""
    }
  }
}
""".strip()


# =========================================================
# API 1회 호출
# =========================================================

def request_model(
    model_id,
    baseline_path,
    current_path,
):

    baseline_b64 = encode_image(
        baseline_path
    )

    current_b64 = encode_image(
        current_path
    )

    headers = {
        "Authorization":
            f"Bearer {OPENROUTER_API_KEY}",

        "Content-Type":
            "application/json",
    }

    content = [
        {
            "type": "text",
            "text": build_prompt(),
        },
        {
            "type": "text",
            "text": "IMAGE 1: BASELINE",
        },
        {
            "type": "image_url",
            "image_url": {
                "url":
                    "data:image/jpeg;base64,"
                    + baseline_b64
            },
        },
        {
            "type": "text",
            "text": "IMAGE 2: CURRENT",
        },
        {
            "type": "image_url",
            "image_url": {
                "url":
                    "data:image/jpeg;base64,"
                    + current_b64
            },
        },
    ]

    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": content,
            }
        ],
        "temperature": 0,
    }

    start = time.time()

    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=180,
    )

    elapsed = time.time() - start

    # 재시도할 수 있는 오류
    if (
        response.status_code == 429
        or 500 <= response.status_code < 600
    ):
        raise ConnectionError(
            f"Retryable HTTP "
            f"{response.status_code}: "
            f"{response.text}"
        )

    # 인증/잔액/모델 오류 등
    if response.status_code != 200:
        raise RuntimeError(
            f"HTTP {response.status_code}: "
            f"{response.text}"
        )

    response_json = response.json()

    raw = (
        response_json["choices"][0]
        ["message"]["content"]
    )

    parsed = json.loads(
        clean_json_response(raw)
    )

    return {
        "prediction": parsed,
        "raw_response": raw,
        "elapsed_seconds": elapsed,
        "usage": response_json.get(
            "usage",
            {},
        ),
    }


# =========================================================
# 재시도 포함 API 호출
# =========================================================

def call_model(
    model_id,
    baseline_path,
    current_path,
    max_retries=3,
):

    for attempt in range(
        1,
        max_retries + 1,
    ):

        try:

            return request_model(
                model_id,
                baseline_path,
                current_path,
            )

        except ConnectionError as error:

            if attempt == max_retries:
                raise

            wait_seconds = (
                2 ** attempt
            )

            print(
                f"일시적 API 오류: {error}"
            )

            print(
                f"{wait_seconds}초 후 "
                f"재시도 "
                f"({attempt}/{max_retries})"
            )

            time.sleep(
                wait_seconds
            )


# =========================================================
# 결과 채점
# =========================================================

def score_result(
    prediction,
    ground_truth,
):

    pred_change = prediction.get(
        "change",
        {},
    )

    gt_change = ground_truth.get(
        "change",
        {},
    )

    pred_policy = prediction.get(
        "policy_results",
        {},
    )

    gt_policy = ground_truth.get(
        "policy_results",
        {},
    )

    scores = {
        "change_detected":
            pred_change.get(
                "change_detected"
            )
            == gt_change.get(
                "change_detected"
            ),

        "change_type":
            pred_change.get(
                "change_type"
            )
            == gt_change.get(
                "change_type"
            ),

        "change_degree":
            pred_change.get(
                "change_degree"
            )
            == gt_change.get(
                "change_degree"
            ),

        "path_occupancy":
            pred_change.get(
                "path_occupancy"
            )
            == gt_change.get(
                "path_occupancy"
            ),

        "dangerous_object":
            pred_change.get(
                "dangerous_object"
            )
            == gt_change.get(
                "dangerous_object"
            ),

        "policy_A":
            pred_policy.get(
                "A",
                {},
            ).get(
                "risk_level"
            )
            == gt_policy.get(
                "A",
                {},
            ).get(
                "risk_level"
            ),

        "policy_B":
            pred_policy.get(
                "B",
                {},
            ).get(
                "risk_level"
            )
            == gt_policy.get(
                "B",
                {},
            ).get(
                "risk_level"
            ),

        "policy_C":
            pred_policy.get(
                "C",
                {},
            ).get(
                "risk_level"
            )
            == gt_policy.get(
                "C",
                {},
            ).get(
                "risk_level"
            ),
    }

    scores["all_correct"] = all(
        scores.values()
    )

    return scores


# =========================================================
# Resume 키
# =========================================================

def result_key(
    pair,
    model_name,
):

    return (
        str(
            pair["original_pair_id"]
        ),
        pair["augmentation"],
        model_name,
    )


def existing_result_keys(
    results,
):

    keys = set()

    for result in results:

        if (
            result.get("status")
            != "success"
        ):
            continue

        key = (
            str(
                result.get(
                    "original_pair_id"
                )
            ),
            result.get(
                "augmentation"
            ),
            result.get(
                "model_name"
            ),
        )

        keys.add(key)

    return keys


# =========================================================
# 요약 생성
# =========================================================

def calculate_group_summary(
    records,
):

    successful = [
        record
        for record in records
        if record.get("status")
        == "success"
    ]

    errors = [
        record
        for record in records
        if record.get("status")
        == "error"
    ]

    result = {
        "success_count":
            len(successful),

        "error_count":
            len(errors),
    }

    for metric in METRICS:

        if not successful:

            result[
                f"{metric}_accuracy"
            ] = 0.0

            continue

        correct = sum(
            1
            for record in successful
            if record[
                "scores"
            ].get(
                metric,
                False,
            )
        )

        result[
            f"{metric}_accuracy"
        ] = (
            correct
            / len(successful)
        )

    if successful:

        total_time = sum(
            record[
                "elapsed_seconds"
            ]
            for record in successful
        )

        result[
            "average_time_seconds"
        ] = (
            total_time
            / len(successful)
        )

        result[
            "total_time_seconds"
        ] = total_time

        result[
            "total_cost_usd"
        ] = sum(
            (
                record.get(
                    "usage",
                    {},
                ).get(
                    "cost",
                    0,
                )
                or 0
            )
            for record in successful
        )

    else:

        result[
            "average_time_seconds"
        ] = 0.0

        result[
            "total_time_seconds"
        ] = 0.0

        result[
            "total_cost_usd"
        ] = 0.0

    return result


def build_summary(results):

    summary = {
        "overall_by_model": {},
        "by_augmentation": {},
    }

    # 모델 전체
    for model_name in MODELS:

        records = [
            result
            for result in results
            if result.get(
                "model_name"
            ) == model_name
        ]

        summary[
            "overall_by_model"
        ][
            model_name
        ] = calculate_group_summary(
            records
        )

    # 증강 종류별
    augmentations = sorted(
        {
            result.get(
                "augmentation"
            )
            for result in results
            if result.get(
                "augmentation"
            )
        }
    )

    for augmentation in augmentations:

        summary[
            "by_augmentation"
        ][augmentation] = {}

        for model_name in MODELS:

            records = [
                result
                for result in results
                if (
                    result.get(
                        "model_name"
                    ) == model_name
                    and result.get(
                        "augmentation"
                    ) == augmentation
                )
            ]

            summary[
                "by_augmentation"
            ][augmentation][
                model_name
            ] = calculate_group_summary(
                records
            )

    return summary


# =========================================================
# Summary 저장
# =========================================================

def save_summary(summary):

    with open(
        SUMMARY_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# Summary 출력
# =========================================================

def print_model_summary(
    model_name,
    data,
):

    print()
    print(model_name)
    print("-" * 70)

    print(
        f"Success: "
        f"{data['success_count']}"
    )

    print(
        f"Errors: "
        f"{data['error_count']}"
    )

    for metric in METRICS:

        accuracy = (
            data[
                f"{metric}_accuracy"
            ]
            * 100
        )

        print(
            f"{metric}: "
            f"{accuracy:.1f}%"
        )

    print(
        "Average time:",
        f"{data['average_time_seconds']:.3f}s",
    )

    print(
        "Total cost:",
        f"${data['total_cost_usd']:.6f}",
    )


def print_summary(summary):

    print()
    print("=" * 70)
    print("ROBUSTNESS TEST SUMMARY")
    print("=" * 70)

    print()
    print("[전체 증강 결과]")

    for model_name, data in (
        summary[
            "overall_by_model"
        ].items()
    ):

        print_model_summary(
            model_name,
            data,
        )

    print()
    print("=" * 70)
    print("[증강 종류별 All Correct]")
    print("=" * 70)

    for augmentation, models in (
        summary[
            "by_augmentation"
        ].items()
    ):

        print()
        print(
            f"{augmentation}"
        )

        for model_name, data in (
            models.items()
        ):

            accuracy = (
                data[
                    "all_correct_accuracy"
                ]
                * 100
            )

            print(
                f"  {model_name}: "
                f"{accuracy:.1f}%"
            )


# =========================================================
# Main
# =========================================================

def main():

    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY가 없습니다."
        )

    if not GROUND_TRUTH_PATH.exists():
        raise FileNotFoundError(
            f"증강 Ground Truth 없음: "
            f"{GROUND_TRUTH_PATH}"
        )

    if not AUGMENTED_DIR.exists():
        raise FileNotFoundError(
            f"증강 이미지 폴더 없음: "
            f"{AUGMENTED_DIR}"
        )

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    gt_data = load_json(
        GROUND_TRUTH_PATH
    )

    pairs = gt_data[
        "pairs"
    ]

    total_expected = (
        len(pairs)
        * len(MODELS)
    )

    # 이전 결과 불러오기
    results = (
        load_existing_results()
    )

    completed_keys = (
        existing_result_keys(
            results
        )
    )

    completed_count = len(
        completed_keys
    )

    print()
    print("=" * 70)
    print(
        "VLM ROBUSTNESS TEST"
    )
    print("=" * 70)

    print(
        f"Augmented pairs: "
        f"{len(pairs)}"
    )

    print(
        f"Models: "
        f"{len(MODELS)}"
    )

    print(
        f"Total evaluations: "
        f"{total_expected}"
    )

    print(
        f"Already completed: "
        f"{completed_count}"
    )

    print(
        f"Remaining: "
        f"{total_expected - completed_count}"
    )

    print("=" * 70)

    progress = completed_count

    for pair in pairs:

        augmentation = pair[
            "augmentation"
        ]

        image_dir = (
            AUGMENTED_DIR
            / augmentation
        )

        baseline_path = (
            image_dir
            / pair["baseline"]
        )

        current_path = (
            image_dir
            / pair["current"]
        )

        if not baseline_path.exists():
            raise FileNotFoundError(
                baseline_path
            )

        if not current_path.exists():
            raise FileNotFoundError(
                current_path
            )

        for (
            model_name,
            model_id,
        ) in MODELS.items():

            key = result_key(
                pair,
                model_name,
            )

            # 이미 성공한 결과는 재호출하지 않음
            if key in completed_keys:

                print(
                    f"[SKIP] "
                    f"Pair "
                    f"{pair['original_pair_id']} "
                    f"| {augmentation} "
                    f"| {model_name}"
                )

                continue

            progress += 1

            print()
            print("=" * 70)

            print(
                f"[{progress}/{total_expected}] "
                f"Pair "
                f"{pair['original_pair_id']} "
                f"| {augmentation} "
                f"| {model_name}"
            )

            print(
                f"{pair['baseline']} "
                f"-> "
                f"{pair['current']}"
            )

            print("=" * 70)

            try:

                response = call_model(
                    model_id,
                    baseline_path,
                    current_path,
                )

                prediction = response[
                    "prediction"
                ]

                scores = score_result(
                    prediction,
                    pair,
                )

                result = {
                    "augmented_pair_id":
                        pair["id"],

                    "original_pair_id":
                        pair[
                            "original_pair_id"
                        ],

                    "augmentation":
                        augmentation,

                    "baseline":
                        pair["baseline"],

                    "current":
                        pair["current"],

                    "model_name":
                        model_name,

                    "model_id":
                        model_id,

                    "status":
                        "success",

                    "ground_truth": {
                        "change":
                            pair["change"],

                        "policy_results":
                            pair[
                                "policy_results"
                            ],
                    },

                    "prediction":
                        prediction,

                    "scores":
                        scores,

                    "elapsed_seconds":
                        response[
                            "elapsed_seconds"
                        ],

                    "usage":
                        response[
                            "usage"
                        ],
                }

                results.append(
                    result
                )

                completed_keys.add(
                    key
                )

                print(
                    "Change type:",
                    prediction.get(
                        "change",
                        {},
                    ).get(
                        "change_type"
                    ),
                )

                print(
                    "Degree:",
                    prediction.get(
                        "change",
                        {},
                    ).get(
                        "change_degree"
                    ),
                )

                print(
                    "Path:",
                    prediction.get(
                        "change",
                        {},
                    ).get(
                        "path_occupancy"
                    ),
                )

                print(
                    "Scores:",
                    scores,
                )

                print(
                    "Elapsed:",
                    f"{response['elapsed_seconds']:.3f}s",
                )

                print(
                    "Cost:",
                    response.get(
                        "usage",
                        {},
                    ).get(
                        "cost"
                    ),
                )

            except Exception as error:

                print(
                    "[ERROR]",
                    str(error),
                )

                results.append(
                    {
                        "augmented_pair_id":
                            pair["id"],

                        "original_pair_id":
                            pair[
                                "original_pair_id"
                            ],

                        "augmentation":
                            augmentation,

                        "baseline":
                            pair["baseline"],

                        "current":
                            pair["current"],

                        "model_name":
                            model_name,

                        "model_id":
                            model_id,

                        "status":
                            "error",

                        "error":
                            str(error),
                    }
                )

            # 매 호출마다 저장
            save_results(
                results
            )

    summary = build_summary(
        results
    )

    save_summary(
        summary
    )

    print_summary(
        summary
    )

    print()
    print("=" * 70)
    print("ROBUSTNESS TEST COMPLETE")
    print("=" * 70)

    print()
    print(
        "Raw results:"
    )
    print(
        RESULT_PATH
    )

    print()
    print(
        "Summary:"
    )
    print(
        SUMMARY_PATH
    )


if __name__ == "__main__":
    main()
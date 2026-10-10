import base64
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


# =========================================================
# 경로 설정
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
AI_SERVER_DIR = BASE_DIR.parent

DATASET_DIR = (
    BASE_DIR
    / "rosbag_data"
    / "datasets"
)

GROUND_TRUTH_PATH = (
    BASE_DIR
    / "pair_ground_truth.json"
)

RESULT_DIR = BASE_DIR / "results"

RAW_RESULT_PATH = (
    RESULT_DIR
    / "glm_evaluation_results.json"
)

SUMMARY_PATH = (
    RESULT_DIR
    / "glm_evaluation_summary.json"
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
# 비교할 모델
# =========================================================

MODELS = {
    "glm_5_3_flash":
        "z-ai/glm-5.3-flash",
}


# =========================================================
# 이미지 Base64 변환
# =========================================================

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(
            f.read()
        ).decode("utf-8")


# =========================================================
# Ground Truth 로드
# =========================================================

def load_ground_truth():
    with open(
        GROUND_TRUTH_PATH,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


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
# Prompt
# =========================================================

def build_prompt():
    return """
You are a visual safety analysis system for a mobile robot.

You will receive TWO images of the SAME physical scene.

IMAGE 1 = BASELINE
IMAGE 2 = CURRENT

Compare CURRENT against BASELINE.

Your task is to identify environmental changes and evaluate
the resulting risk under three different safety policies.

Do NOT evaluate the CURRENT image independently.
All judgments must be based on the difference between
BASELINE and CURRENT.

--------------------------------------------------
CHANGE ANALYSIS
--------------------------------------------------

change_detected:
- true if any meaningful environmental change occurred
- false if no meaningful change occurred

change_type:
- NO_CHANGE
- ADDED
- REMOVED
- MOVED
- STATE_CHANGED
- MIXED

Definitions:

ADDED:
An object exists in CURRENT but not in BASELINE.

REMOVED:
An object exists in BASELINE but not in CURRENT.

MOVED:
The same object exists in both images but changed location.

STATE_CHANGED:
The same object exists in both images but its state,
orientation, posture, or condition changed.

Examples:
- upright bottle -> fallen bottle
- closed box -> opened box
- object orientation changed

MIXED:
Two or more different types of change occurred together.

--------------------------------------------------
CHANGE DEGREE
--------------------------------------------------

NONE:
No meaningful environmental change.

SMALL:
Minor change such as one small object being added,
removed, or slightly moved.

MEDIUM:
Clearly noticeable movement, state change,
or multiple smaller changes.

LARGE:
Major environmental change such as a large object
appearing, major obstruction, or multiple substantial
changes.

--------------------------------------------------
PATH OCCUPANCY
--------------------------------------------------

UNCHANGED:
No change affecting the path.

UNDER_50:
Changed objects occupy less than approximately
50 percent of the usable walking path.

OVER_50:
Changed objects occupy approximately 50 percent
or more of the usable walking path and substantially
obstruct passage.

--------------------------------------------------
DANGEROUS OBJECT
--------------------------------------------------

dangerous_object = true when a changed or newly appearing
object itself may create a physical hazard.

Examples include hand tools or sharp / hazardous objects.

A normal bottle or cardboard box is not automatically
a dangerous object.

--------------------------------------------------
POLICY A - HUMAN WALKING PASSAGE
--------------------------------------------------

NORMAL:
No meaningful environmental change.

LOW:
Change exists but:
- path occupancy is UNDER_50
- no dangerous object is involved

MEDIUM:
A dangerous object such as a hand tool appears or changes,
while the path is not substantially blocked.

HIGH:
Changed objects occupy approximately 50 percent or more
of the usable path and substantially obstruct passage.

If HIGH conditions are met, HIGH takes priority.

--------------------------------------------------
POLICY B - CHANGE MAGNITUDE
--------------------------------------------------

NONE -> NORMAL
SMALL -> LOW
MEDIUM -> MEDIUM
LARGE -> HIGH

--------------------------------------------------
POLICY C - NO CHANGE ALLOWED
--------------------------------------------------

No environmental change -> NORMAL
Any environmental change -> HIGH

--------------------------------------------------
IMPORTANT
--------------------------------------------------

Do not invent a specific tool identity if it is unclear.

If you can only determine that an object is a hand tool,
use "hand_tool".

Use simple object names such as:
- bottle
- box
- hand_tool

Return ONLY valid JSON.

Use exactly this structure:

{
  "change": {
    "change_detected": true,
    "change_type": "MIXED",
    "added_objects": [],
    "removed_objects": [],
    "moved_objects": [],
    "state_changed_objects": [],
    "change_degree": "MEDIUM",
    "path_occupancy": "UNDER_50",
    "dangerous_object": false
  },
  "policy_results": {
    "A": {
      "risk_level": "LOW",
      "reason": ""
    },
    "B": {
      "risk_level": "MEDIUM",
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
# OpenRouter 호출
# =========================================================

def call_model(
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

    prompt = build_prompt()

    headers = {
        "Authorization":
            f"Bearer {OPENROUTER_API_KEY}",

        "Content-Type":
            "application/json",
    }

    content = [
        {
            "type": "text",
            "text": prompt,
        },
        {
            "type": "text",
            "text": (
                "IMAGE 1: BASELINE"
            ),
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
            "text": (
                "IMAGE 2: CURRENT"
            ),
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

    start_time = time.time()

    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=180,
    )

    elapsed = (
        time.time()
        - start_time
    )

    if response.status_code != 200:
        raise RuntimeError(
            "OpenRouter Error "
            f"{response.status_code}: "
            f"{response.text}"
        )

    response_json = response.json()

    raw_text = (
        response_json[
            "choices"
        ][0][
            "message"
        ][
            "content"
        ]
    )

    clean_text = clean_json_response(
        raw_text
    )

    parsed = json.loads(
        clean_text
    )

    usage = response_json.get(
        "usage",
        {},
    )

    return {
        "response": parsed,
        "raw_response": raw_text,
        "elapsed_seconds": elapsed,
        "usage": usage,
    }


# =========================================================
# 개별 항목 비교
# =========================================================

def compare_field(
    predicted,
    expected,
):
    return predicted == expected


# =========================================================
# 한 결과 평가
# =========================================================

def score_result(
    prediction,
    ground_truth,
):
    pred_change = prediction[
        "change"
    ]

    gt_change = ground_truth[
        "change"
    ]

    pred_policy = prediction[
        "policy_results"
    ]

    gt_policy = ground_truth[
        "policy_results"
    ]

    scores = {
        "change_detected":
            compare_field(
                pred_change.get(
                    "change_detected"
                ),
                gt_change.get(
                    "change_detected"
                ),
            ),

        "change_type":
            compare_field(
                pred_change.get(
                    "change_type"
                ),
                gt_change.get(
                    "change_type"
                ),
            ),

        "change_degree":
            compare_field(
                pred_change.get(
                    "change_degree"
                ),
                gt_change.get(
                    "change_degree"
                ),
            ),

        "path_occupancy":
            compare_field(
                pred_change.get(
                    "path_occupancy"
                ),
                gt_change.get(
                    "path_occupancy"
                ),
            ),

        "dangerous_object":
            compare_field(
                pred_change.get(
                    "dangerous_object"
                ),
                gt_change.get(
                    "dangerous_object"
                ),
            ),

        "policy_A":
            compare_field(
                pred_policy.get(
                    "A",
                    {},
                ).get(
                    "risk_level"
                ),
                gt_policy.get(
                    "A",
                    {},
                ).get(
                    "risk_level"
                ),
            ),

        "policy_B":
            compare_field(
                pred_policy.get(
                    "B",
                    {},
                ).get(
                    "risk_level"
                ),
                gt_policy.get(
                    "B",
                    {},
                ).get(
                    "risk_level"
                ),
            ),

        "policy_C":
            compare_field(
                pred_policy.get(
                    "C",
                    {},
                ).get(
                    "risk_level"
                ),
                gt_policy.get(
                    "C",
                    {},
                ).get(
                    "risk_level"
                ),
            ),
    }

    scores["all_correct"] = all(
        scores.values()
    )

    return scores


# =========================================================
# 중간 결과 저장
# =========================================================

def save_results(results):
    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        RAW_RESULT_PATH,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# 모델별 요약
# =========================================================

def build_summary(results):
    metrics = [
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

    summary = {}

    for model_name in MODELS:
        model_results = [
            r
            for r in results
            if (
                r["model_name"]
                == model_name
                and r["status"]
                == "success"
            )
        ]

        failed_results = [
            r
            for r in results
            if (
                r["model_name"]
                == model_name
                and r["status"]
                == "error"
            )
        ]

        model_summary = {
            "success_count":
                len(model_results),

            "error_count":
                len(failed_results),
        }

        for metric in metrics:
            if not model_results:
                model_summary[
                    f"{metric}_accuracy"
                ] = 0.0
                continue

            correct = sum(
                1
                for r in model_results
                if r["scores"].get(
                    metric,
                    False,
                )
            )

            model_summary[
                f"{metric}_accuracy"
            ] = (
                correct
                / len(model_results)
            )

        if model_results:
            total_time = sum(
                r[
                    "elapsed_seconds"
                ]
                for r in model_results
            )

            average_time = (
                total_time
                / len(model_results)
            )

            total_cost = sum(
                (
                    r.get(
                        "usage",
                        {},
                    ).get(
                        "cost",
                        0,
                    )
                    or 0
                )
                for r in model_results
            )

        else:
            total_time = 0
            average_time = 0
            total_cost = 0

        model_summary[
            "total_time_seconds"
        ] = total_time

        model_summary[
            "average_time_seconds"
        ] = average_time

        model_summary[
            "total_cost_usd"
        ] = total_cost

        summary[
            model_name
        ] = model_summary

    return summary


# =========================================================
# Summary 저장
# =========================================================

def save_summary(summary):
    with open(
        SUMMARY_PATH,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# 진행상황 출력
# =========================================================

def print_summary(summary):
    print()
    print("=" * 70)
    print("FINAL MODEL EVALUATION SUMMARY")
    print("=" * 70)

    for model_name, data in summary.items():

        print()
        print(model_name)
        print("-" * 70)

        print(
            "Success:",
            data["success_count"],
        )

        print(
            "Errors:",
            data["error_count"],
        )

        print(
            "Change detected:",
            f"{data['change_detected_accuracy'] * 100:.1f}%",
        )

        print(
            "Change type:",
            f"{data['change_type_accuracy'] * 100:.1f}%",
        )

        print(
            "Change degree:",
            f"{data['change_degree_accuracy'] * 100:.1f}%",
        )

        print(
            "Path occupancy:",
            f"{data['path_occupancy_accuracy'] * 100:.1f}%",
        )

        print(
            "Dangerous object:",
            f"{data['dangerous_object_accuracy'] * 100:.1f}%",
        )

        print(
            "Policy A:",
            f"{data['policy_A_accuracy'] * 100:.1f}%",
        )

        print(
            "Policy B:",
            f"{data['policy_B_accuracy'] * 100:.1f}%",
        )

        print(
            "Policy C:",
            f"{data['policy_C_accuracy'] * 100:.1f}%",
        )

        print(
            "All correct:",
            f"{data['all_correct_accuracy'] * 100:.1f}%",
        )

        print(
            "Average time:",
            f"{data['average_time_seconds']:.3f}s",
        )

        print(
            "Total cost:",
            f"${data['total_cost_usd']:.6f}",
        )

    print()
    print("=" * 70)


# =========================================================
# MAIN
# =========================================================

def main():

    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing."
        )

    if not GROUND_TRUTH_PATH.exists():
        raise FileNotFoundError(
            f"Ground truth not found: "
            f"{GROUND_TRUTH_PATH}"
        )

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ground_truth_data = (
        load_ground_truth()
    )

    pairs = ground_truth_data[
        "pairs"
    ]

    total_calls = (
        len(pairs)
        * len(MODELS)
    )

    print()
    print(
        "VLM FULL MODEL EVALUATION"
    )

    print("=" * 70)

    print(
        f"Pairs: {len(pairs)}"
    )

    print(
        f"Models: {len(MODELS)}"
    )

    print(
        f"Total API calls: {total_calls}"
    )

    print("=" * 70)

    results = []

    call_number = 0

    for pair in pairs:

        baseline_name = pair[
            "baseline"
        ]

        current_name = pair[
            "current"
        ]

        baseline_path = (
            DATASET_DIR
            / baseline_name
        )

        current_path = (
            DATASET_DIR
            / current_name
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

            call_number += 1

            print()
            print("=" * 70)

            print(
                f"[{call_number}/{total_calls}] "
                f"Pair {pair['id']} | "
                f"{model_name}"
            )

            print(
                f"{baseline_name} "
                f"-> {current_name}"
            )

            print("=" * 70)

            try:
                model_result = (
                    call_model(
                        model_id,
                        baseline_path,
                        current_path,
                    )
                )

                prediction = (
                    model_result[
                        "response"
                    ]
                )

                scores = score_result(
                    prediction,
                    pair,
                )

                result = {
                    "pair_id":
                        pair["id"],

                    "scene":
                        pair.get(
                            "scene"
                        ),

                    "baseline":
                        baseline_name,

                    "current":
                        current_name,

                    "model_name":
                        model_name,

                    "model_id":
                        model_id,

                    "status":
                        "success",

                    "ground_truth": {
                        "change":
                            pair[
                                "change"
                            ],

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
                        model_result[
                            "elapsed_seconds"
                        ],

                    "usage":
                        model_result[
                            "usage"
                        ],
                }

                results.append(
                    result
                )

                print(
                    "Change type:",
                    prediction[
                        "change"
                    ].get(
                        "change_type"
                    ),
                )

                print(
                    "Degree:",
                    prediction[
                        "change"
                    ].get(
                        "change_degree"
                    ),
                )

                print(
                    "Policy:",
                    "A=",
                    prediction[
                        "policy_results"
                    ][
                        "A"
                    ].get(
                        "risk_level"
                    ),
                    "B=",
                    prediction[
                        "policy_results"
                    ][
                        "B"
                    ].get(
                        "risk_level"
                    ),
                    "C=",
                    prediction[
                        "policy_results"
                    ][
                        "C"
                    ].get(
                        "risk_level"
                    ),
                )

                print(
                    "Elapsed:",
                    f"{model_result['elapsed_seconds']:.3f}s",
                )

                print(
                    "Cost:",
                    model_result[
                        "usage"
                    ].get(
                        "cost"
                    ),
                )

                print(
                    "Scores:",
                    scores,
                )

            except Exception as e:

                print(
                    "[ERROR]",
                    str(e),
                )

                results.append(
                    {
                        "pair_id":
                            pair["id"],

                        "scene":
                            pair.get(
                                "scene"
                            ),

                        "baseline":
                            baseline_name,

                        "current":
                            current_name,

                        "model_name":
                            model_name,

                        "model_id":
                            model_id,

                        "status":
                            "error",

                        "error":
                            str(e),
                    }
                )

            # 호출 하나 끝날 때마다 저장
            # 중간에 종료되어도 결과 보존
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
    print(
        "Raw results:"
    )
    print(
        RAW_RESULT_PATH
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
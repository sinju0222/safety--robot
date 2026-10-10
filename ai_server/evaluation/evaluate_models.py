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
    / "situation_evaluation_results.json"
)

SUMMARY_PATH = (
    RESULT_DIR
    / "situation_evaluation_summary.json"
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
    "gpt5_mini":
        "openai/gpt-5-mini",

    "gemini_2_5_flash":
        "google/gemini-2.5-flash",

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
You are a visual safety analysis system for a mobile
patrol robot.

You will receive TWO images of the SAME physical scene.

IMAGE 1 = BASELINE
IMAGE 2 = CURRENT

Compare CURRENT against BASELINE.

Do NOT analyze CURRENT independently.

Your job is to:

1. Detect environmental changes.
2. Identify which objects changed.
3. Understand the current safety situation.
4. Identify hazards caused by the change.
5. Assess the overall risk level.
6. Generate appropriate safety actions for the
   current situation.

The safety actions must be generated according to
the actual situation.

Do NOT select from predefined safety policies.

--------------------------------------------------
CHANGE ANALYSIS
--------------------------------------------------

change_detected:

true:
A meaningful environmental change occurred.

false:
No meaningful environmental change occurred.


change_type must be ONE of:

NO_CHANGE
ADDED
REMOVED
MOVED
STATE_CHANGED
MIXED


ADDED:
An object exists in CURRENT but did not exist
in BASELINE.

REMOVED:
An object existed in BASELINE but does not exist
in CURRENT.

MOVED:
The same object exists in both images but changed
location.

STATE_CHANGED:
The same object exists in both images but its state,
orientation, posture, or physical condition changed.

Examples:
- upright bottle -> fallen bottle
- closed box -> opened box
- object orientation changed

MIXED:
Two or more different change types occurred together.


--------------------------------------------------
OBJECT NAMES
--------------------------------------------------

Use simple generic object names.

Use names such as:

bottle
box
bag
hand_tool

Do not invent a specific tool identity when the exact
tool cannot be confidently determined.

If an object is clearly a tool but its exact type is
uncertain, use:

hand_tool


--------------------------------------------------
HAZARD ANALYSIS
--------------------------------------------------

hazard_present:

true:
The environmental change creates or introduces a
meaningful physical safety hazard.

false:
The change does not create a meaningful physical
safety hazard.


hazard_types is an array.

Use ONLY the following hazard types:


trip_hazard:

A changed object may cause a person to trip.


object_on_path:

A changed object is located on the normal walking or
movement path.


path_obstruction:

A changed object significantly obstructs or blocks
the usable path.


sharp_tool_hazard:

A changed hand tool or sharp tool may cause physical
injury.


rolling_object_hazard:

An object such as a bottle may roll or move
unexpectedly on the floor.


unstable_object:

An object is in an unstable position or state and may
move, tip, or fall.


falling_object_hazard:

An object's changed state or position creates a risk
of falling.


Multiple hazard types may be returned when more than
one condition applies.

If no meaningful hazard exists, return an empty array.

Do NOT create any hazard type outside this list.

Do not classify an object as hazardous merely because
it exists.

Consider its location, state, obstruction, and the
change from BASELINE.


--------------------------------------------------
RISK LEVEL
--------------------------------------------------

Return exactly ONE:

NORMAL
LOW
MEDIUM
HIGH


NORMAL:

No meaningful environmental change occurred,
or the current situation does not require a
safety response.


LOW:

A change occurred but immediate physical safety
risk is low.

The situation may require observation or simple
housekeeping.


MEDIUM:

A meaningful safety hazard exists.

Worker attention, inspection, object removal,
or another corrective action is required.


HIGH:

The situation presents a serious safety hazard.

Immediate corrective action, temporary access
restriction, or removal of a major obstruction
may be required before normal operation continues.


Assess the complete situation.

Do NOT determine risk only from the object category.


--------------------------------------------------
SITUATION SUMMARY
--------------------------------------------------

Describe:

- what changed
- which objects were involved
- why the current situation matters for safety

The description must be based only on visible evidence.

Do not invent invisible causes or events.

Keep the summary concise and practical.


--------------------------------------------------
RECOMMENDED ACTIONS
--------------------------------------------------

Generate actions appropriate for the actual situation.

Possible actions may include:

- removing an obstacle from a passage
- returning an object to a safe location
- inspecting a changed object
- temporarily restricting access
- clearing a passage before operation continues
- monitoring an area when immediate intervention
  is unnecessary

These are examples only.

Do NOT mechanically copy these examples.

Generate actions that fit the observed situation.

Do NOT automatically recommend access restriction
only because the risk level is HIGH.

Access restriction should be recommended only when
the actual situation justifies it.

If there is no meaningful change and no safety action
is required, return an empty array.


--------------------------------------------------
IMPORTANT RULES
--------------------------------------------------

All judgments must be based on the difference between
BASELINE and CURRENT.

Do NOT invent hazards that cannot reasonably be inferred
from the images.

Do NOT invent objects that are not visible.

Do NOT evaluate an unchanged object as a newly introduced
hazard unless its state or position changed.

Use only the defined change types.

Use only the defined hazard types.

Return ONLY valid JSON.

Do not include Markdown.

Do not include explanations outside JSON.


Use exactly this structure:

{
  "change": {
    "change_detected": true,
    "change_type": "ADDED",
    "added_objects": [],
    "removed_objects": [],
    "moved_objects": [],
    "state_changed_objects": []
  },
  "risk_assessment": {
    "hazard_present": true,
    "hazard_types": [],
    "risk_level": "MEDIUM"
  },
  "situation": {
    "summary": ""
  },
  "recommended_actions": []
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

    parsed = json.loads(
        clean_json_response(
            raw_text
        )
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
# 기본 비교
# =========================================================

def compare_field(
    predicted,
    expected,
):
    return predicted == expected


# =========================================================
# 리스트 정규화
# =========================================================

def normalize_list(values):
    if not isinstance(values, list):
        return set()

    return {
        str(value).strip().lower()
        for value in values
    }


# =========================================================
# Precision / Recall / F1
# =========================================================

def calculate_set_metrics(
    predicted,
    expected,
):
    pred_set = normalize_list(
        predicted
    )

    expected_set = normalize_list(
        expected
    )

    true_positive = len(
        pred_set & expected_set
    )

    false_positive = len(
        pred_set - expected_set
    )

    false_negative = len(
        expected_set - pred_set
    )

    # 둘 다 비어 있으면 완전 정답
    if (
        len(pred_set) == 0
        and len(expected_set) == 0
    ):
        return {
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "tp": 0,
            "fp": 0,
            "fn": 0,
        }

    if (
        true_positive
        + false_positive
        > 0
    ):
        precision = (
            true_positive
            / (
                true_positive
                + false_positive
            )
        )
    else:
        precision = 0.0

    if (
        true_positive
        + false_negative
        > 0
    ):
        recall = (
            true_positive
            / (
                true_positive
                + false_negative
            )
        )
    else:
        recall = 0.0

    if precision + recall > 0:
        f1 = (
            2
            * precision
            * recall
            / (
                precision
                + recall
            )
        )
    else:
        f1 = 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
    }


# =========================================================
# 한 결과 평가
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

    pred_risk = prediction.get(
        "risk_assessment",
        {},
    )

    gt_risk = ground_truth.get(
        "risk_assessment",
        {},
    )

    exact_scores = {
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

        "hazard_present":
            compare_field(
                pred_risk.get(
                    "hazard_present"
                ),
                gt_risk.get(
                    "hazard_present"
                ),
            ),

        "risk_level":
            compare_field(
                pred_risk.get(
                    "risk_level"
                ),
                gt_risk.get(
                    "risk_level"
                ),
            ),
    }

    set_scores = {
        "added_objects":
            calculate_set_metrics(
                pred_change.get(
                    "added_objects",
                    [],
                ),
                gt_change.get(
                    "added_objects",
                    [],
                ),
            ),

        "removed_objects":
            calculate_set_metrics(
                pred_change.get(
                    "removed_objects",
                    [],
                ),
                gt_change.get(
                    "removed_objects",
                    [],
                ),
            ),

        "moved_objects":
            calculate_set_metrics(
                pred_change.get(
                    "moved_objects",
                    [],
                ),
                gt_change.get(
                    "moved_objects",
                    [],
                ),
            ),

        "state_changed_objects":
            calculate_set_metrics(
                pred_change.get(
                    "state_changed_objects",
                    [],
                ),
                gt_change.get(
                    "state_changed_objects",
                    [],
                ),
            ),

        "hazard_types":
            calculate_set_metrics(
                pred_risk.get(
                    "hazard_types",
                    [],
                ),
                gt_risk.get(
                    "hazard_types",
                    [],
                ),
            ),
    }

    object_f1_values = [
        set_scores[
            "added_objects"
        ]["f1"],

        set_scores[
            "removed_objects"
        ]["f1"],

        set_scores[
            "moved_objects"
        ]["f1"],

        set_scores[
            "state_changed_objects"
        ]["f1"],
    ]

    object_change_f1 = (
        sum(object_f1_values)
        / len(object_f1_values)
    )

    structured_score = (
        (
            1.0
            if exact_scores[
                "change_detected"
            ]
            else 0.0
        )
        +
        (
            1.0
            if exact_scores[
                "change_type"
            ]
            else 0.0
        )
        +
        object_change_f1
        +
        (
            1.0
            if exact_scores[
                "hazard_present"
            ]
            else 0.0
        )
        +
        set_scores[
            "hazard_types"
        ]["f1"]
        +
        (
            1.0
            if exact_scores[
                "risk_level"
            ]
            else 0.0
        )
    ) / 6.0

    return {
        "exact": exact_scores,
        "sets": set_scores,
        "object_change_f1":
            object_change_f1,
        "structured_score":
            structured_score,
    }


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
# 평균 계산
# =========================================================

def average(values):
    if not values:
        return 0.0

    return sum(values) / len(values)


# =========================================================
# 모델별 요약
# =========================================================

def build_summary(results):

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

        # ---------------------------------------------
        # Exact accuracy
        # ---------------------------------------------

        exact_metrics = [
            "change_detected",
            "change_type",
            "hazard_present",
            "risk_level",
        ]

        for metric in exact_metrics:

            values = [
                1.0
                if r[
                    "scores"
                ][
                    "exact"
                ][
                    metric
                ]
                else 0.0
                for r in model_results
            ]

            model_summary[
                f"{metric}_accuracy"
            ] = average(
                values
            )

        # ---------------------------------------------
        # Set F1
        # ---------------------------------------------

        set_metrics = [
            "added_objects",
            "removed_objects",
            "moved_objects",
            "state_changed_objects",
            "hazard_types",
        ]

        for metric in set_metrics:

            precision_values = [
                r[
                    "scores"
                ][
                    "sets"
                ][
                    metric
                ][
                    "precision"
                ]
                for r in model_results
            ]

            recall_values = [
                r[
                    "scores"
                ][
                    "sets"
                ][
                    metric
                ][
                    "recall"
                ]
                for r in model_results
            ]

            f1_values = [
                r[
                    "scores"
                ][
                    "sets"
                ][
                    metric
                ][
                    "f1"
                ]
                for r in model_results
            ]

            model_summary[
                f"{metric}_precision"
            ] = average(
                precision_values
            )

            model_summary[
                f"{metric}_recall"
            ] = average(
                recall_values
            )

            model_summary[
                f"{metric}_f1"
            ] = average(
                f1_values
            )

        model_summary[
            "object_change_f1"
        ] = average(
            [
                r[
                    "scores"
                ][
                    "object_change_f1"
                ]
                for r in model_results
            ]
        )

        model_summary[
            "structured_score"
        ] = average(
            [
                r[
                    "scores"
                ][
                    "structured_score"
                ]
                for r in model_results
            ]
        )

        # ---------------------------------------------
        # 시간 / 비용
        # ---------------------------------------------

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
# Summary 출력
# =========================================================

def print_summary(summary):

    print()
    print("=" * 70)
    print(
        "SITUATION-AWARE VLM EVALUATION SUMMARY"
    )
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
            "Change detected accuracy:",
            f"{data['change_detected_accuracy'] * 100:.1f}%",
        )

        print(
            "Change type accuracy:",
            f"{data['change_type_accuracy'] * 100:.1f}%",
        )

        print(
            "Object change F1:",
            f"{data['object_change_f1'] * 100:.1f}%",
        )

        print(
            "Hazard present accuracy:",
            f"{data['hazard_present_accuracy'] * 100:.1f}%",
        )

        print(
            "Hazard types F1:",
            f"{data['hazard_types_f1'] * 100:.1f}%",
        )

        print(
            "Risk level accuracy:",
            f"{data['risk_level_accuracy'] * 100:.1f}%",
        )

        print(
            "Structured score:",
            f"{data['structured_score'] * 100:.1f}%",
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
        "SITUATION-AWARE VLM MODEL EVALUATION"
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

                model_result = call_model(
                    model_id,
                    baseline_path,
                    current_path,
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
                            pair.get(
                                "change",
                                {},
                            ),

                        "risk_assessment":
                            pair.get(
                                "risk_assessment",
                                {},
                            ),

                        "situation":
                            pair.get(
                                "situation",
                                {},
                            ),

                        "recommended_actions":
                            pair.get(
                                "recommended_actions",
                                [],
                            ),
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

                pred_change = (
                    prediction.get(
                        "change",
                        {},
                    )
                )

                pred_risk = (
                    prediction.get(
                        "risk_assessment",
                        {},
                    )
                )

                print(
                    "Change type:",
                    pred_change.get(
                        "change_type"
                    ),
                )

                print(
                    "Risk:",
                    pred_risk.get(
                        "risk_level"
                    ),
                )

                print(
                    "Hazards:",
                    pred_risk.get(
                        "hazard_types"
                    ),
                )

                print(
                    "Object change F1:",
                    f"{scores['object_change_f1']:.3f}",
                )

                print(
                    "Hazard F1:",
                    f"{scores['sets']['hazard_types']['f1']:.3f}",
                )

                print(
                    "Structured score:",
                    f"{scores['structured_score']:.3f}",
                )

                print(
                    "Situation:",
                    prediction.get(
                        "situation",
                        {},
                    ).get(
                        "summary"
                    ),
                )

                print(
                    "Actions:",
                    prediction.get(
                        "recommended_actions",
                        [],
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
    print("Raw results:")
    print(
        RAW_RESULT_PATH
    )

    print()
    print("Summary:")
    print(
        SUMMARY_PATH
    )


if __name__ == "__main__":
    main()
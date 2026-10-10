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

INPUT_PATH = (
    BASE_DIR
    / "results"
    / "situation_evaluation_results.json"
)

OUTPUT_PATH = (
    BASE_DIR
    / "results"
    / "generated_output_evaluation.json"
)

SUMMARY_PATH = (
    BASE_DIR
    / "results"
    / "generated_output_evaluation_summary.json"
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
# Judge 모델
# =========================================================
#
# 모든 후보 모델의 출력을 동일한 Judge가 평가합니다.
#
# 평가 대상 모델명은 Judge에게 전달하지 않습니다.
#
# 우선 GPT-5-mini를 Judge로 사용합니다.
# =========================================================

JUDGE_MODEL = "openai/gpt-5-mini"


# =========================================================
# 유틸
# =========================================================

def load_json(path):
    with open(
        path,
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


def save_json(
    path,
    data,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


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
# Judge Prompt
# =========================================================

def build_judge_prompt(
    ground_truth,
    prediction,
):

    gt_text = json.dumps(
        ground_truth,
        ensure_ascii=False,
        indent=2,
    )

    pred_text = json.dumps(
        {
            "situation":
                prediction.get(
                    "situation",
                    {},
                ),

            "recommended_actions":
                prediction.get(
                    "recommended_actions",
                    [],
                ),
        },
        ensure_ascii=False,
        indent=2,
    )

    return f"""
You are an impartial evaluator for a mobile robot
environmental safety analysis system.

You are NOT generating a new safety analysis.

You are evaluating the quality of an existing
prediction.

The identity of the model that generated the prediction
is intentionally hidden.

Use the provided ground truth as the primary reference,
but do NOT require exact wording.

Semantically equivalent descriptions and actions must
receive credit.

A prediction may contain reasonable additional detail
that is not explicitly written in the ground truth.

Do not penalize such detail unless it:

- contradicts the ground truth,
- invents unsupported facts,
- introduces an unreasonable hazard,
- recommends an inappropriate action,
- or exceeds the system's intended responsibility.


==================================================
SYSTEM SCOPE
==================================================

This system uses a mobile patrol robot to detect
environmental changes and provide safety information
to human operators.

The system may:

- detect changes,
- explain hazards,
- recommend removal of obstacles,
- recommend inspection,
- recommend cleanup,
- recommend temporary human access restriction,
- recommend monitoring or verification.

The system does NOT autonomously:

- slow down the robot as a safety response,
- reroute the robot as a safety response,
- command another robot,
- physically manipulate objects.

Recommendations should primarily be directed toward
human safety management and corrective action.

Statements such as autonomously slowing patrol,
automatically rerouting patrol, or commanding the robot
to perform unsupported control actions should be
considered unnecessary or out of scope.


==================================================
SCORING
==================================================

Score each category from 0 to 5.

Use integer scores only.


1. situation_factuality

5:
The situation description is fully consistent with
the reference and contains no meaningful unsupported
claims.

4:
Mostly accurate with only a minor unsupported or
over-specific detail.

3:
Generally correct but contains noticeable unsupported
or inaccurate details.

2:
Multiple important inaccuracies.

1:
Mostly incorrect.

0:
Contradicts the situation or is unusable.


2. situation_completeness

5:
Captures all important changes and safety-relevant
aspects.

4:
Captures almost everything important but misses one
minor aspect.

3:
Captures the main situation but misses a meaningful
detail.

2:
Several important changes or hazards are omitted.

1:
Only a small portion of the important situation is
captured.

0:
Does not meaningfully describe the situation.


3. action_relevance

5:
All recommended actions directly and appropriately
address the actual situation.

4:
Actions are strongly relevant with only a minor
unnecessary recommendation.

3:
Main actions are appropriate but some are unnecessary,
weak, or insufficiently connected to the situation.

2:
Several actions are inappropriate or important actions
are missing.

1:
Most actions do not appropriately address the problem.

0:
Actions are irrelevant or unusable.


4. action_safety

5:
All actions are safe, reasonable, and appropriate for
the system.

4:
Generally safe with a minor questionable instruction.

3:
Mostly safe but contains a meaningful concern.

2:
Contains potentially problematic recommendations.

1:
Contains substantially unsafe or inappropriate advice.

0:
Contains clearly dangerous advice.


5. action_efficiency

5:
Actions are concise, proportional to the risk, and do
not introduce unnecessary intervention.

4:
Mostly proportional with a small amount of unnecessary
action.

3:
Some overreaction, redundancy, or unnecessary action.

2:
Clearly excessive or poorly prioritized.

1:
Strongly disproportionate to the situation.

0:
Actions are fundamentally inappropriate in scope or
severity.


==================================================
SPECIAL CASE: NO ACTION REQUIRED
==================================================

If the ground truth indicates that no safety action is
required and the prediction correctly returns an empty
action list:

action_relevance = 5
action_safety = 5
action_efficiency = 5

Do not penalize the absence of actions in this case.


==================================================
OUTPUT
==================================================

Return ONLY valid JSON.

Do not return Markdown.

Use exactly this structure:

{{
  "situation_factuality": 0,
  "situation_completeness": 0,
  "action_relevance": 0,
  "action_safety": 0,
  "action_efficiency": 0,
  "reason": ""
}}


==================================================
GROUND TRUTH
==================================================

{gt_text}


==================================================
PREDICTION TO EVALUATE
==================================================

{pred_text}
""".strip()


# =========================================================
# Judge API 호출
# =========================================================

def call_judge(
    ground_truth,
    prediction,
):

    prompt = build_judge_prompt(
        ground_truth,
        prediction,
    )

    headers = {
        "Authorization":
            f"Bearer {OPENROUTER_API_KEY}",

        "Content-Type":
            "application/json",
    }

    payload = {
        "model": JUDGE_MODEL,

        "messages": [
            {
                "role": "user",
                "content": prompt,
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

    if response.status_code != 200:
        raise RuntimeError(
            f"Judge API error "
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

    result = json.loads(
        clean_json_response(
            raw_text
        )
    )

    required_fields = [
        "situation_factuality",
        "situation_completeness",
        "action_relevance",
        "action_safety",
        "action_efficiency",
    ]

    for field in required_fields:

        value = result.get(
            field
        )

        if not isinstance(
            value,
            int,
        ):
            raise ValueError(
                f"Invalid judge score "
                f"for {field}: {value}"
            )

        if value < 0 or value > 5:
            raise ValueError(
                f"Judge score out of range "
                f"for {field}: {value}"
            )

    return {
        "judge_result":
            result,

        "elapsed_seconds":
            elapsed,

        "usage":
            response_json.get(
                "usage",
                {},
            ),
    }


# =========================================================
# 평균
# =========================================================

def average(values):

    if not values:
        return 0.0

    return sum(values) / len(values)


# =========================================================
# Summary
# =========================================================

def build_summary(results):

    model_names = sorted(
        {
            result["model_name"]
            for result in results
        }
    )

    summary = {}

    metric_names = [
        "situation_factuality",
        "situation_completeness",
        "action_relevance",
        "action_safety",
        "action_efficiency",
    ]

    for model_name in model_names:

        model_results = [
            result
            for result in results
            if (
                result["model_name"]
                == model_name
                and result["status"]
                == "success"
            )
        ]

        errors = [
            result
            for result in results
            if (
                result["model_name"]
                == model_name
                and result["status"]
                == "error"
            )
        ]

        data = {
            "success_count":
                len(model_results),

            "error_count":
                len(errors),
        }

        for metric in metric_names:

            scores = [
                result[
                    "judge"
                ][
                    metric
                ]
                for result in model_results
            ]

            data[
                f"{metric}_average"
            ] = average(
                scores
            )

            data[
                f"{metric}_percentage"
            ] = (
                average(scores)
                / 5.0
                * 100.0
            )

        overall_scores = []

        for result in model_results:

            values = [
                result[
                    "judge"
                ][
                    metric
                ]
                for metric in metric_names
            ]

            overall_scores.append(
                average(values)
            )

        data[
            "generated_quality_average"
        ] = average(
            overall_scores
        )

        data[
            "generated_quality_percentage"
        ] = (
            average(
                overall_scores
            )
            / 5.0
            * 100.0
        )

        data[
            "judge_total_cost_usd"
        ] = sum(
            (
                result.get(
                    "usage",
                    {},
                ).get(
                    "cost",
                    0,
                )
                or 0
            )
            for result in model_results
        )

        summary[
            model_name
        ] = data

    return summary


# =========================================================
# 출력
# =========================================================

def print_summary(summary):

    print()
    print("=" * 70)
    print(
        "GENERATED OUTPUT EVALUATION SUMMARY"
    )
    print("=" * 70)

    for model_name, data in summary.items():

        print()
        print(model_name)
        print("-" * 70)

        print(
            "Situation factuality:",
            f"{data['situation_factuality_percentage']:.1f}%",
        )

        print(
            "Situation completeness:",
            f"{data['situation_completeness_percentage']:.1f}%",
        )

        print(
            "Action relevance:",
            f"{data['action_relevance_percentage']:.1f}%",
        )

        print(
            "Action safety:",
            f"{data['action_safety_percentage']:.1f}%",
        )

        print(
            "Action efficiency:",
            f"{data['action_efficiency_percentage']:.1f}%",
        )

        print(
            "Generated quality:",
            f"{data['generated_quality_percentage']:.1f}%",
        )

        print(
            "Judge cost:",
            f"${data['judge_total_cost_usd']:.6f}",
        )


# =========================================================
# MAIN
# =========================================================

def main():

    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing."
        )

    source_results = load_json(
        INPUT_PATH
    )

    source_results = [
        result
        for result in source_results
        if result.get(
            "status"
        ) == "success"
    ]

    print()
    print("=" * 70)
    print("GENERATED OUTPUT EVALUATION")
    print("=" * 70)

    print(
        "Judge:",
        JUDGE_MODEL,
    )

    print(
        "Predictions:",
        len(source_results),
    )

    print("=" * 70)

    evaluated = []

    total = len(
        source_results
    )

    for index, source in enumerate(
        source_results,
        start=1,
    ):

        print()
        print(
            f"[{index}/{total}] "
            f"Pair {source['pair_id']} | "
            f"{source['model_name']}"
        )

        try:

            judge_result = call_judge(
                source[
                    "ground_truth"
                ],
                source[
                    "prediction"
                ],
            )

            scores = (
                judge_result[
                    "judge_result"
                ]
            )

            generated_average = average(
                [
                    scores[
                        "situation_factuality"
                    ],
                    scores[
                        "situation_completeness"
                    ],
                    scores[
                        "action_relevance"
                    ],
                    scores[
                        "action_safety"
                    ],
                    scores[
                        "action_efficiency"
                    ],
                ]
            )

            result = {
                "pair_id":
                    source[
                        "pair_id"
                    ],

                "scene":
                    source.get(
                        "scene"
                    ),

                "model_name":
                    source[
                        "model_name"
                    ],

                "ground_truth":
                    source[
                        "ground_truth"
                    ],

                "prediction":
                    {
                        "situation":
                            source[
                                "prediction"
                            ].get(
                                "situation",
                                {},
                            ),

                        "recommended_actions":
                            source[
                                "prediction"
                            ].get(
                                "recommended_actions",
                                [],
                            ),
                    },

                "status":
                    "success",

                "judge":
                    scores,

                "generated_quality":
                    generated_average,

                "elapsed_seconds":
                    judge_result[
                        "elapsed_seconds"
                    ],

                "usage":
                    judge_result[
                        "usage"
                    ],
            }

            evaluated.append(
                result
            )

            print(
                "Factuality:",
                scores[
                    "situation_factuality"
                ],
                "/ 5",
            )

            print(
                "Completeness:",
                scores[
                    "situation_completeness"
                ],
                "/ 5",
            )

            print(
                "Action relevance:",
                scores[
                    "action_relevance"
                ],
                "/ 5",
            )

            print(
                "Action safety:",
                scores[
                    "action_safety"
                ],
                "/ 5",
            )

            print(
                "Action efficiency:",
                scores[
                    "action_efficiency"
                ],
                "/ 5",
            )

            print(
                "Generated quality:",
                f"{generated_average:.2f}/5",
            )

            print(
                "Reason:",
                scores.get(
                    "reason",
                    "",
                ),
            )

        except Exception as e:

            print(
                "[ERROR]",
                str(e),
            )

            evaluated.append(
                {
                    "pair_id":
                        source[
                            "pair_id"
                        ],

                    "scene":
                        source.get(
                            "scene"
                        ),

                    "model_name":
                        source[
                            "model_name"
                        ],

                    "status":
                        "error",

                    "error":
                        str(e),
                }
            )

        # 매 호출마다 저장
        save_json(
            OUTPUT_PATH,
            evaluated,
        )

    summary = build_summary(
        evaluated
    )

    save_json(
        SUMMARY_PATH,
        summary,
    )

    print_summary(
        summary
    )

    print()
    print(
        "Detailed results:",
        OUTPUT_PATH,
    )

    print(
        "Summary:",
        SUMMARY_PATH,
    )


if __name__ == "__main__":
    main()
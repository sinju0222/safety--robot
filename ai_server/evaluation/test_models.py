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

RESULT_DIR = (
    BASE_DIR
    / "results"
)

RESULT_PATH = (
    RESULT_DIR
    / "smoke_test_results.json"
)


# =========================================================
# 환경변수
# =========================================================

load_dotenv(AI_SERVER_DIR / ".env")

OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY"
)

OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)


# =========================================================
# 비교할 VLM
# =========================================================

MODELS = {
    "glm_5_3_flash": "z-ai/glm-5.3-flash",
}


# =========================================================
# 이미지 → Base64
# =========================================================

def encode_image(image_path):
    with open(image_path, "rb") as file:
        encoded = base64.b64encode(
            file.read()
        ).decode("utf-8")

    return encoded


# =========================================================
# Ground Truth 읽기
# =========================================================

def load_ground_truth():
    with open(
        GROUND_TRUTH_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# =========================================================
# Smoke Test Pair 선택
# =========================================================

def get_test_pair(ground_truth):
    pairs = ground_truth["pairs"]

    if not pairs:
        raise ValueError(
            "pair_ground_truth.json에 "
            "평가 pair가 없습니다."
        )

    # 첫 번째 pair만 사용
    return pairs[0]


# =========================================================
# Prompt
# =========================================================

def build_prompt():
    return """
You are a vision-language safety analysis system
for a mobile robot.

You will receive TWO images.

IMAGE 1 = BASELINE
IMAGE 2 = CURRENT

Compare CURRENT with BASELINE.

Your job is to determine:

1. Whether a meaningful environmental change occurred.
2. What objects were added, removed, moved,
   or changed state.
3. How large the environmental change is.
4. Whether the changed object occupies
   50% or more of the human walking path.
5. Whether a dangerous object such as
   pliers or another hazardous tool is present.
6. The risk level according to Policies A, B, and C.

IMPORTANT:
Judge the CHANGE between the two images.
Do not judge the current image independently.

POLICY A — HUMAN WALKING PATH

This policy is for a path used by people.

NORMAL:
No meaningful change occurred.

LOW:
A new object appeared or an existing object moved,
but the change is small and the object does NOT
occupy 50% or more of the walking path.

MEDIUM:
A dangerous object such as pliers or another
hazardous tool appears or moves in the path,
even if the object is small.

HIGH:
A changed or newly appeared object occupies
50% or more of the walking path and significantly
obstructs human passage.

POLICY B — CHANGE MAGNITUDE

NORMAL:
No meaningful change occurred.

LOW:
Only a small environmental change occurred.

MEDIUM:
A clearly noticeable but not large-scale
environmental change occurred.

HIGH:
The environmental change is large.

Consider object size, movement distance,
number of changed objects, and overall
scene difference.

POLICY C — NO CHANGE ALLOWED

NORMAL:
No change occurred.

HIGH:
ANY environmental change occurred,
regardless of whether it improves or worsens
the environment.

Allowed change_type values:

NO_CHANGE
ADDED
REMOVED
MOVED
STATE_CHANGED
MIXED

Allowed change_degree values:

NONE
SMALL
MEDIUM
LARGE

Allowed path_occupancy values:

UNCHANGED
UNDER_50
OVER_50

Allowed risk_level values:

NORMAL
LOW
MEDIUM
HIGH

Return ONLY one valid JSON object.

Do not use Markdown.
Do not use ```json.
Do not include any explanation outside the JSON.

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
# OpenRouter 호출
# =========================================================

def call_model(
    model_id,
    baseline_path,
    current_path,
):
    baseline_base64 = encode_image(
        baseline_path
    )

    current_base64 = encode_image(
        current_path
    )

    prompt = build_prompt()

    headers = {
        "Authorization": (
            f"Bearer {OPENROUTER_API_KEY}"
        ),
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_id,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            prompt
                            + "\n\n"
                            + "The following image is "
                            + "IMAGE 1: BASELINE."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/jpeg;base64,"
                                + baseline_base64
                            )
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "The following image is "
                            "IMAGE 2: CURRENT."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "data:image/jpeg;base64,"
                                + current_base64
                            )
                        },
                    },
                ],
            }
        ],
    }

    start_time = time.time()

    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=180,
    )

    elapsed = time.time() - start_time

    if response.status_code != 200:
        raise RuntimeError(
            f"OpenRouter Error "
            f"{response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    content = (
        data["choices"][0]["message"]["content"]
    )

    return {
        "raw_response": content,
        "usage": data.get("usage"),
        "elapsed_seconds": round(
            elapsed,
            3,
        ),
    }


# =========================================================
# JSON 응답 파싱
# =========================================================

def parse_model_json(raw_response):
    text = raw_response.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip().startswith("```")
        ):
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return json.loads(text)


# =========================================================
# 모델 하나 테스트
# =========================================================

def test_model(
    model_name,
    model_id,
    test_pair,
):
    baseline_name = (
        test_pair["baseline"]
    )

    current_name = (
        test_pair["current"]
    )

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
            f"Baseline 이미지 없음: "
            f"{baseline_path}"
        )

    if not current_path.exists():
        raise FileNotFoundError(
            f"Current 이미지 없음: "
            f"{current_path}"
        )

    print()
    print("=" * 60)
    print(f"MODEL: {model_name}")
    print(f"ID: {model_id}")
    print(f"Baseline: {baseline_name}")
    print(f"Current:  {current_name}")
    print("=" * 60)

    result = call_model(
        model_id=model_id,
        baseline_path=baseline_path,
        current_path=current_path,
    )

    raw_response = result[
        "raw_response"
    ]

    print()
    print("[RAW RESPONSE]")
    print(raw_response)

    try:
        parsed = parse_model_json(
            raw_response
        )

        json_valid = True

        print()
        print("[PARSED JSON]")
        print(
            json.dumps(
                parsed,
                ensure_ascii=False,
                indent=2,
            )
        )

    except Exception as error:
        parsed = None
        json_valid = False

        print()
        print("[JSON PARSE ERROR]")
        print(error)

    print()
    print(
        "Elapsed:",
        result["elapsed_seconds"],
        "seconds",
    )

    print(
        "Usage:",
        json.dumps(
            result["usage"],
            ensure_ascii=False,
        ),
    )

    return {
        "model_name": model_name,
        "model_id": model_id,
        "baseline_image": baseline_name,
        "current_image": current_name,
        "json_valid": json_valid,
        "prediction": parsed,
        "raw_response": raw_response,
        "usage": result["usage"],
        "elapsed_seconds": (
            result["elapsed_seconds"]
        ),
    }


# =========================================================
# Main
# =========================================================

def main():
    print()
    print("VLM MODEL SMOKE TEST")
    print("=" * 60)

    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY가 없습니다. "
            "ai_server/.env를 확인하세요."
        )

    if not GROUND_TRUTH_PATH.exists():
        raise FileNotFoundError(
            "pair_ground_truth.json이 없습니다: "
            f"{GROUND_TRUTH_PATH}"
        )

    ground_truth = load_ground_truth()

    test_pair = get_test_pair(
        ground_truth
    )

    print(
        "Test Pair ID:",
        test_pair["id"],
    )

    print(
        "Baseline:",
        test_pair["baseline"],
    )

    print(
        "Current:",
        test_pair["current"],
    )

    print()
    print("[GROUND TRUTH]")

    print(
        json.dumps(
            {
                "change": (
                    test_pair["change"]
                ),
                "policy_results": (
                    test_pair[
                        "policy_results"
                    ]
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    for model_name, model_id in (
        MODELS.items()
    ):
        try:
            result = test_model(
                model_name=model_name,
                model_id=model_id,
                test_pair=test_pair,
            )

        except Exception as error:
            print()
            print(
                f"[ERROR] {model_name}"
            )
            print(error)

            result = {
                "model_name": model_name,
                "model_id": model_id,
                "error": str(error),
            }

        results.append(result)

    output = {
        "test_type": "smoke_test",
        "pair_id": test_pair["id"],
        "ground_truth": {
            "change": test_pair["change"],
            "policy_results": (
                test_pair[
                    "policy_results"
                ]
            ),
        },
        "results": results,
    }

    with open(
        RESULT_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 60)
    print("SMOKE TEST FINISHED")
    print(
        "Result:",
        RESULT_PATH,
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
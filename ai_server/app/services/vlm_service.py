import base64
import json
import os
import re
import time

import requests
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.risk import (
    PerformanceInfo,
    VLMAnalysisResult,
)


OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)

DEFAULT_MODEL = (
    "z-ai/glm-5.3-flash"
)


# =========================================================
# 환경 설정
# =========================================================

def get_model():
    return os.getenv(
        "VLM_MODEL",
        DEFAULT_MODEL,
    )


def check_config():
    api_key = os.getenv(
        "OPENROUTER_API_KEY"
    )

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "OPENROUTER_API_KEY "
                "is not configured."
            ),
        )


def build_headers():
    check_config()

    return {
        "Authorization": (
            "Bearer "
            + os.getenv(
                "OPENROUTER_API_KEY"
            )
        ),
        "Content-Type":
            "application/json",
    }


# =========================================================
# 이미지 Base64 변환
# =========================================================

def encode_image(
    image_bytes: bytes,
    content_type: str,
):
    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Image is empty.",
        )

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPEG, PNG and WEBP "
                "images are supported."
            ),
        )

    encoded = base64.b64encode(
        image_bytes
    ).decode(
        "utf-8"
    )

    return (
        f"data:{content_type};base64,"
        f"{encoded}"
    )


# =========================================================
# GLM Prompt
#
# 최종 모델 평가에서 사용한 판단 구조를
# 실제 서비스에서도 동일하게 유지한다.
# =========================================================

def build_prompt():
    return """
You are a vision-language safety analysis system
for a mobile robot monitoring a human work environment.

You will receive TWO images.

IMAGE 1 = BASELINE
IMAGE 2 = CURRENT

Compare CURRENT with BASELINE.

IMPORTANT:
Judge the CHANGE between the two images.
Do not judge CURRENT independently.

Your tasks are:

1. Determine whether a meaningful environmental
   change occurred.

2. Identify objects that were:
   - added
   - removed
   - moved
   - changed state

3. Determine whether the detected change creates
   a safety hazard.

4. Identify the hazard types caused by the change.

5. Determine the overall risk level.

6. Briefly explain the current changed situation.

7. Generate practical safety actions appropriate
   for the detected situation.

The system is intended to support human safety
management.

The system may recommend actions such as:
- removing an object
- inspecting a changed object
- cleaning an affected area
- temporarily restricting human access
- monitoring the changed situation

Do NOT recommend that the robot autonomously:
- slow down
- reroute
- command another robot
- physically manipulate or remove objects

Safety actions should primarily describe what
a human operator should check or correct.

Use generic object names when possible.

Examples:

bottle
box
bag
hand_tool

If the exact type of a hand tool is uncertain,
use "hand_tool".

Allowed change_type values:

NO_CHANGE
ADDED
REMOVED
MOVED
STATE_CHANGED
MIXED

Use NO_CHANGE when there is no meaningful
environmental change.

Use MIXED when multiple different change types
occur together.

Allowed hazard_type values:

trip_hazard
object_on_path
path_obstruction
sharp_tool_hazard
rolling_object_hazard
unstable_object
falling_object_hazard

Hazard definitions:

trip_hazard:
A changed object creates a realistic risk that
a person could trip or stumble.

object_on_path:
A changed object is located on the normal
human walking path.

path_obstruction:
A changed object significantly blocks or reduces
the usable walking path.

sharp_tool_hazard:
A changed hand tool or sharp object creates
a realistic physical injury hazard.

rolling_object_hazard:
A changed object may roll or move unexpectedly,
creating a safety risk.

unstable_object:
A changed object is unstable or positioned
in a way that may lose balance.

falling_object_hazard:
A changed object may fall from its current
position and create a safety risk.

Do not add a hazard only because an object
belongs to a potentially dangerous category.
The hazard must be supported by the visible
change and current situation.

Allowed risk_level values:

NORMAL
LOW
MEDIUM
HIGH

Risk level guidelines:

NORMAL:
No meaningful environmental change exists,
or no safety response is required.

LOW:
A meaningful change exists, but it presents
little immediate physical danger.
Simple observation or minor correction may
be sufficient.

MEDIUM:
A meaningful safety hazard exists and requires
attention or corrective action such as inspection,
removal, cleanup, or caution.

HIGH:
A serious safety hazard exists and requires
prompt corrective action before normal use
of the affected area should continue.

Do not assign HIGH merely because a change exists.
Consider the actual severity of the changed
situation.

For NO_CHANGE:

- change_detected must be false
- change_type must be NO_CHANGE
- all object change lists must be empty
- hazard_present must be false
- hazard_types must be empty
- risk_level should normally be NORMAL
- recommended_actions may be empty

LANGUAGE REQUIREMENTS:

The "situation.summary" value must be written in Korean.

Every string inside "recommended_actions"
must be written in Korean.

Keep all JSON field names, change_type values,
hazard_type values, risk_level values,
and object names in English exactly as defined above.

Do not translate enum values or JSON keys into Korean.

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
# VLM JSON 응답 추출
# =========================================================

def extract_json(
    raw_response: str,
):
    if not isinstance(
        raw_response,
        str,
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "VLM response is not text."
            ),
        )

    text = raw_response.strip()

    if not text:
        raise HTTPException(
            status_code=502,
            detail=(
                "VLM returned an empty response."
            ),
        )

    # 정상 JSON
    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Markdown 코드블록 제거
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    ).strip()

    try:
        return json.loads(cleaned)

    except json.JSONDecodeError:
        pass

    # JSON 객체 부분 추출
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if (
        start != -1
        and end != -1
        and end > start
    ):
        try:
            return json.loads(
                cleaned[
                    start:
                    end + 1
                ]
            )

        except json.JSONDecodeError:
            pass

    raise HTTPException(
        status_code=502,
        detail={
            "message":
                "VLM returned invalid JSON.",

            "raw_response":
                raw_response,
        },
    )


# =========================================================
# OpenRouter 응답 텍스트 추출
# =========================================================

def extract_openrouter_content(
    result: dict,
):
    try:
        content = (
            result["choices"][0]
            ["message"]["content"]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ) as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Invalid OpenRouter response: "
                f"{error}"
            ),
        )

    if (
        not isinstance(content, str)
        or not content.strip()
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "OpenRouter returned "
                "empty VLM content."
            ),
        )

    return content


# =========================================================
# OpenRouter / GLM 연결 테스트
# =========================================================

def test_connection():
    check_config()

    payload = {
        "model":
            get_model(),

        "temperature":
            0,

        "max_tokens":
            300,

        "messages": [
            {
                "role":
                    "user",

                "content":
                    (
                        "Return exactly this JSON "
                        "and nothing else: "
                        '{"status":"ok"}'
                    ),
            }
        ],
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=build_headers(),
            json=payload,
            timeout=60,
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "OpenRouter request failed: "
                f"{error}"
            ),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "OpenRouter returned "
                "invalid JSON: "
                f"{error}"
            ),
        )

    return {
        "status":
            "success",

        "requested_model":
            get_model(),

        "actual_model":
            data.get(
                "model"
            ),

        "response":
            extract_openrouter_content(
                data
            ),
    }


# =========================================================
# 실제 환경 변화 분석
# =========================================================

def analyze_images(
    baseline_bytes: bytes,
    baseline_content_type: str,
    current_bytes: bytes,
    current_content_type: str,
):
    check_config()

    baseline_url = encode_image(
        baseline_bytes,
        baseline_content_type,
    )

    current_url = encode_image(
        current_bytes,
        current_content_type,
    )

    prompt = build_prompt()

    # -----------------------------------------------------
    # IMAGE 1 = BASELINE
    # IMAGE 2 = CURRENT
    # -----------------------------------------------------

    payload = {
        "model":
            get_model(),

        "temperature":
            0,

        "messages": [
            {
                "role":
                    "user",

                "content": [
                    {
                        "type":
                            "text",

                        "text": (
                            prompt
                            + "\n\n"
                            + "The following image is "
                            + "IMAGE 1: BASELINE."
                        ),
                    },
                    {
                        "type":
                            "image_url",

                        "image_url": {
                            "url":
                                baseline_url,
                        },
                    },
                    {
                        "type":
                            "text",

                        "text": (
                            "The following image is "
                            "IMAGE 2: CURRENT."
                        ),
                    },
                    {
                        "type":
                            "image_url",

                        "image_url": {
                            "url":
                                current_url,
                        },
                    },
                ],
            }
        ],
    }

    start_time = time.perf_counter()

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=build_headers(),
            json=payload,
            timeout=180,
        )

        response.raise_for_status()

    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "OpenRouter request failed: "
                f"{error}"
            ),
        )

    latency = (
        time.perf_counter()
        - start_time
    )

    try:
        data = response.json()

    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "OpenRouter returned "
                "invalid JSON: "
                f"{error}"
            ),
        )

    raw_response = (
        extract_openrouter_content(
            data
        )
    )

    parsed = extract_json(
        raw_response
    )

    if not isinstance(
        parsed,
        dict,
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "VLM result must be "
                "a JSON object."
            ),
        )

    # -----------------------------------------------------
    # Pydantic으로 GLM 출력 검증
    # -----------------------------------------------------

    try:
        analysis = (
            VLMAnalysisResult(
                **parsed
            )
        )

    except ValidationError as error:
        raise HTTPException(
            status_code=502,
            detail={
                "message":
                    "Invalid VLM analysis result.",

                "validation_error":
                    str(error),

                "raw_response":
                    raw_response,
            },
        )

    # -----------------------------------------------------
    # 성능 정보
    # -----------------------------------------------------

    usage = data.get(
        "usage",
        {},
    ) or {}

    performance = PerformanceInfo(
        requested_model=get_model(),

        actual_model=data.get(
            "model"
        ),

        latency_seconds=round(
            latency,
            3,
        ),

        prompt_tokens=usage.get(
            "prompt_tokens"
        ),

        completion_tokens=usage.get(
            "completion_tokens"
        ),

        total_tokens=usage.get(
            "total_tokens"
        ),
    )

    return {
        "analysis":
            analysis,

        "performance":
            performance,
    }

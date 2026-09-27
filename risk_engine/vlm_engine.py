import base64
import json
from pathlib import Path
from urllib import request
from urllib.error import URLError


OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "gemma3:4b"


class VLMEngine:
    def __init__(self):
        self.model = OLLAMA_MODEL
        self.url = OLLAMA_URL

    @staticmethod
    def _encode_image(image_path):
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(
                f"Image not found: {image_path}"
            )

        with open(image_path, "rb") as image_file:
            return base64.b64encode(
                image_file.read()
            ).decode("utf-8")

    @staticmethod
    def _build_prompt(
        object_class,
        bbox,
        change_type,
        zone_type,
    ):
        return f"""
You are a visual safety analysis module for an
autonomous industrial patrol robot.

A change has been detected in the environment.

Detected information:
- object class: {object_class}
- bounding box: {bbox}
- change type: {change_type}
- zone type: {zone_type}

Analyze the image and evaluate ONLY the visual and
contextual safety risk.

Another machine-learning model separately evaluates:
- object size
- path intrusion
- distance to robot path
- spatial risk

Therefore, focus on visual context such as:
- whether the object appears to obstruct movement
- unsafe placement
- unstable stacking
- fallen objects
- hazardous materials
- abnormal situations
- whether the scene appears safe

Risk score guideline:

0:
No meaningful visual safety hazard.

1-30:
Minor change with little safety impact.

31-70:
Potential safety issue requiring attention.

71-100:
Clearly hazardous situation requiring immediate
attention.

Return ONLY valid JSON.

Use exactly this structure:

{{
  "context_risk_score": 0,
  "hazard_type": "none",
  "reason": "short explanation"
}}

Rules:
- context_risk_score must be an integer from 0 to 100.
- hazard_type must be a short lowercase identifier.
- reason must be concise.
- Do not include markdown.
- Do not include text outside the JSON object.
"""

    @staticmethod
    def _validate_result(result):
        required_fields = {
            "context_risk_score",
            "hazard_type",
            "reason",
        }

        if not isinstance(result, dict):
            raise ValueError(
                "VLM response is not a JSON object."
            )

        missing = required_fields - result.keys()

        if missing:
            raise ValueError(
                f"Missing VLM fields: {missing}"
            )

        score = int(
            result["context_risk_score"]
        )

        score = max(
            0,
            min(
                100,
                score,
            ),
        )

        return {
            "context_risk_score": score,
            "hazard_type": str(
                result["hazard_type"]
            ),
            "reason": str(
                result["reason"]
            ),
        }

    def analyze(
        self,
        image_path,
        object_class,
        bbox,
        change_type,
        zone_type,
    ):
        image_base64 = self._encode_image(
            image_path
        )

        prompt = self._build_prompt(
            object_class=object_class,
            bbox=bbox,
            change_type=change_type,
            zone_type=zone_type,
        )

        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [
                        image_base64
                    ],
                }
            ],
            "options": {
                "temperature": 0.1,
            },
        }

        data = json.dumps(
            payload
        ).encode("utf-8")

        http_request = request.Request(
            self.url,
            data=data,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(
                http_request,
                timeout=120,
            ) as response:
                response_body = (
                    response
                    .read()
                    .decode("utf-8")
                )

        except URLError as error:
            raise RuntimeError(
                "Could not connect to Ollama. "
                "Make sure Ollama is running."
            ) from error

        ollama_response = json.loads(
            response_body
        )

        message = ollama_response.get(
            "message",
            {}
        )

        content = message.get(
            "content",
            ""
        )

        if not content:
            raise RuntimeError(
                "Ollama returned an empty response."
            )

        try:
            result = json.loads(
                content
            )

        except json.JSONDecodeError as error:
            raise RuntimeError(
                "VLM response was not valid JSON.\n"
                f"Response: {content}"
            ) from error

        return self._validate_result(
            result
        )
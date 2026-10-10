import os

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.schemas.risk import (
    RiskAnalysisResponse,
)
from app.services.vlm_service import (
    analyze_images,
    get_model,
    test_connection,
)


# =========================================================
# 환경 변수
# =========================================================

load_dotenv()


# =========================================================
# FastAPI
# =========================================================

app = FastAPI(
    title="Safety Robot AI Server",
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# 기본 API
# =========================================================

@app.get("/")
def root():
    return {
        "message":
            "Safety Robot AI Server",

        "status":
            "running",

        "model":
            get_model(),
    }


# =========================================================
# Health Check
# =========================================================

@app.get("/health")
def health():
    return {
        "status":
            "ok",

        "model":
            get_model(),

        "openrouter_key":
            bool(
                os.getenv(
                    "OPENROUTER_API_KEY"
                )
            ),
    }


# =========================================================
# OpenRouter / VLM 연결 테스트
# =========================================================

@app.get("/test-vlm")
def test_vlm():
    return test_connection()


# =========================================================
# 이미지 검증
# =========================================================

def validate_image(
    image: UploadFile,
):
    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPEG, PNG and WEBP "
                "images are supported."
            ),
        )


# =========================================================
# 실제 환경 변화 분석 API
#
# IMAGE 1 = BASELINE
# IMAGE 2 = CURRENT
# =========================================================

@app.post(
    "/analyze-risk",
    response_model=RiskAnalysisResponse,
)
async def analyze_risk(
    baseline_image: UploadFile = File(...),

    current_image: UploadFile = File(...),

    x: float = Form(...),

    y: float = Form(...),
):
    # -----------------------------------------------------
    # 이미지 형식 검증
    # -----------------------------------------------------

    validate_image(
        baseline_image
    )

    validate_image(
        current_image
    )

    # -----------------------------------------------------
    # 이미지 읽기
    # -----------------------------------------------------

    baseline_bytes = (
        await baseline_image.read()
    )

    current_bytes = (
        await current_image.read()
    )

    if not baseline_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                "Baseline image is empty."
            ),
        )

    if not current_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                "Current image is empty."
            ),
        )

    # -----------------------------------------------------
    # GLM 기반 환경 변화 / 위험 분석
    # -----------------------------------------------------

    result = analyze_images(
        baseline_bytes=(
            baseline_bytes
        ),

        baseline_content_type=(
            baseline_image.content_type
        ),

        current_bytes=(
            current_bytes
        ),

        current_content_type=(
            current_image.content_type
        ),
    )

    # -----------------------------------------------------
    # 최종 응답
    # -----------------------------------------------------

    return RiskAnalysisResponse(
        status="success",

        model=get_model(),

        x=x,

        y=y,

        analysis=result[
            "analysis"
        ],

        performance=result[
            "performance"
        ],
    )

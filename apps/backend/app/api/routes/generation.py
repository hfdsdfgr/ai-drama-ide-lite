"""Generation 测试接口（Phase 5 — Adapter 验证 + Phase 4 L3）。"""

import re
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.core.errors import AppError
from app.schemas.generation import GenerationJobCreate, GenerationJobOut

router = APIRouter(prefix="/api/generation", tags=["generation"])

_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


@router.post("/jobs", response_model=GenerationJobOut, status_code=201)
def create_generation_job(
    payload: GenerationJobCreate, request: Request
) -> dict:
    service = request.app.state.generation_service
    return service.create_job(
        model_id=payload.model_id,
        capability=payload.capability,
        prompt=payload.prompt,
        aspect_ratio=payload.aspect_ratio,
        duration=payload.duration,
        images=payload.images,
        negative_prompt=payload.negative_prompt,
    )


@router.get("/jobs/{job_id}", response_model=GenerationJobOut)
def get_generation_job(job_id: str, request: Request) -> dict:
    return request.app.state.generation_service.get_job(job_id)


@router.get("/files/{filename}")
def generation_file(filename: str, request: Request) -> FileResponse:
    if not _FILENAME_PATTERN.fullmatch(filename):
        raise AppError(
            400,
            "invalid_filename",
            "文件名不合法：仅允许字母、数字、点、下划线、短横线，最长 120 字符",
        )
    path = Path(request.app.state.settings.data_dir) / "generation_tests" / filename
    if not path.is_file():
        raise AppError(404, "file_not_found", "生成文件不存在")
    return FileResponse(path)

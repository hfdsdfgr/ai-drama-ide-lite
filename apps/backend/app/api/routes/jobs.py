"""Phase 10 — 统一任务中心接口：列表 / 详情 / 取消 / 暂停 / 恢复 / 重试。"""

from typing import Literal

from fastapi import APIRouter, Request

from app.core.errors import AppError
from app.schemas.job import JobOut
from app.services.job_store import JobRecord

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job_out(record: JobRecord) -> dict:
    return {
        "job_id": record.id,
        "project_id": record.project_id,
        "type": record.type,
        "status": record.status,
        "progress": record.progress,
        "model_id": record.model_id,
        "provider_id": record.provider_id,
        "capability": record.capability,
        "error": record.error or None,
        "error_category": record.error_category,
        "attempts": record.attempts,
        "result": record.result_payload if record.result_payload else None,
        "created_at": record.created_at,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "paused_at": record.paused_at,
        "cancelled_at": record.cancelled_at,
    }


def _store(request: Request):
    return request.app.state.job_store


@router.get("", response_model=list[JobOut])
def list_jobs(
    request: Request,
    project_id: str | None = None,
    status: Literal["queued", "running", "paused", "completed", "failed", "cancelled"]
    | None = None,
    limit: int = 50,
) -> list[dict]:
    if limit < 1 or limit > 200:
        raise AppError(422, "invalid_limit", "limit 必须在 1-200 之间")
    return [
        _job_out(job)
        for job in _store(request).list_jobs(
            project_id=project_id, status=status, limit=limit
        )
    ]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, request: Request) -> dict:
    return _job_out(_store(request).get(job_id))


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, request: Request) -> dict:
    return _job_out(_store(request).cancel(job_id))


@router.post("/{job_id}/pause", response_model=JobOut)
def pause_job(job_id: str, request: Request) -> dict:
    return _job_out(_store(request).pause(job_id))


@router.post("/{job_id}/resume", response_model=JobOut)
def resume_job(job_id: str, request: Request) -> dict:
    return _job_out(_store(request).resume(job_id))


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_job(job_id: str, request: Request) -> dict:
    return _job_out(_store(request).retry(job_id))

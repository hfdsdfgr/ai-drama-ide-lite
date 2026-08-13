"""Novel / Chapter endpoints（Phase 2 — Novel Studio）。"""

from pathlib import Path

from fastapi import APIRouter, Query, Request

from app.core.errors import AppError
from app.schemas.novel import (
    Chapter,
    ChapterCreate,
    ChapterUpdate,
    Novel,
    NovelCreate,
    NovelDetail,
    NovelUpdate,
)
from app.services.novel_repo import NovelRepository
from app.services.text_import import parse_novel_file

router = APIRouter(prefix="/api/projects/{project_id}/novels", tags=["novels"])


def _repo(request: Request) -> NovelRepository:
    return NovelRepository(request.app.state.settings.db_path)


@router.get("", response_model=list[Novel])
def list_novels(project_id: str, request: Request, q: str = "") -> list[Novel]:
    return _repo(request).list_novels(project_id, q=q)


@router.post("", response_model=Novel, status_code=201)
def create_novel(project_id: str, payload: NovelCreate, request: Request) -> Novel:
    return _repo(request).create(project_id, payload)


@router.post("/import", response_model=Novel, status_code=201)
async def import_novel(
    project_id: str, request: Request, filename: str = Query(...)
) -> Novel:
    raw = await request.body()
    if not raw:
        raise AppError(422, "import_empty", "文件内容为空")
    title, source_type, chapters = parse_novel_file(raw, filename)
    return _repo(request).create_with_chapters(project_id, title, source_type, chapters)


@router.get("/{novel_id}", response_model=NovelDetail)
def get_novel(project_id: str, novel_id: str, request: Request) -> NovelDetail:
    return _repo(request).get(project_id, novel_id)


@router.put("/{novel_id}", response_model=Novel)
def update_novel(
    project_id: str, novel_id: str, payload: NovelUpdate, request: Request
) -> Novel:
    return _repo(request).update_title(project_id, novel_id, payload)


@router.delete("/{novel_id}", status_code=204)
def delete_novel(project_id: str, novel_id: str, request: Request):
    _repo(request).soft_delete(project_id, novel_id)


@router.post("/{novel_id}/chapters", response_model=Chapter, status_code=201)
def create_chapter(
    project_id: str, novel_id: str, payload: ChapterCreate, request: Request
) -> Chapter:
    return _repo(request).create_chapter(project_id, novel_id, payload)


@router.put("/{novel_id}/chapters/{chapter_id}", response_model=Chapter)
def update_chapter(
    project_id: str,
    novel_id: str,
    chapter_id: str,
    payload: ChapterUpdate,
    request: Request,
) -> Chapter:
    return _repo(request).update_chapter(project_id, novel_id, chapter_id, payload)


@router.delete("/{novel_id}/chapters/{chapter_id}", status_code=204)
def delete_chapter(
    project_id: str, novel_id: str, chapter_id: str, request: Request
):
    _repo(request).soft_delete_chapter(project_id, novel_id, chapter_id)

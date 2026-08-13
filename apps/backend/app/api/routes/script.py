"""剧本引擎接口（Phase 7 — Script Engine）。"""

from fastapi import APIRouter, Query, Request

from app.schemas.script import (
    AiEpisodeScriptResult,
    AiShotsResult,
    Episode,
    EpisodeCreate,
    EpisodeDetail,
    Scene,
    SceneCreate,
    SceneDetail,
    SceneUpdate,
    ScriptGenerateRequest,
    Shot,
    ShotsGenerateRequest,
    ShotCreate,
    ShotUpdate,
)
from app.services.script_repo import ScriptRepository

router = APIRouter(prefix="/api/projects/{project_id}/script", tags=["script"])


def _repo(request: Request) -> ScriptRepository:
    return ScriptRepository(request.app.state.settings.db_path)


@router.get("/episodes", response_model=list[Episode])
def list_episodes(
    project_id: str, request: Request, novel_id: str | None = Query(default=None)
) -> list[Episode]:
    return _repo(request).list_episodes(project_id, novel_id)


@router.post("/episodes", response_model=Episode, status_code=201)
def create_episode(
    project_id: str,
    payload: EpisodeCreate,
    request: Request,
    novel_id: str | None = Query(default=None),
) -> Episode:
    return _repo(request).create_episode(project_id, payload, novel_id)


@router.post("/save-episode-script", response_model=EpisodeDetail, status_code=201)
def save_episode_script(
    project_id: str, payload: dict, request: Request
) -> EpisodeDetail:
    """保存 AI 生成的分集剧本（episode + scenes）。"""
    repo = _repo(request)
    episode = payload.get("episode") or {}
    scenes = payload.get("scenes") or []
    return repo.save_episode_script(
        project_id=project_id,
        novel_id=payload.get("novel_id"),
        source_chapter_index=payload.get("chapter_index"),
        episode_title=str(episode.get("title", "")),
        episode_summary=str(episode.get("summary", "")),
        scenes=[SceneCreate(**s) for s in scenes],
    )


@router.get("/episodes/{episode_id}", response_model=EpisodeDetail)
def get_episode(project_id: str, episode_id: str, request: Request) -> EpisodeDetail:
    return _repo(request).get_episode_detail(project_id, episode_id)


@router.delete("/episodes/{episode_id}", status_code=204)
def delete_episode(project_id: str, episode_id: str, request: Request):
    _repo(request).soft_delete_episode(project_id, episode_id)


@router.post("/generate-episode", response_model=AiEpisodeScriptResult)
def generate_episode(
    project_id: str, payload: ScriptGenerateRequest, request: Request
) -> AiEpisodeScriptResult:
    return request.app.state.ai_script_service.generate_episode_script(
        project_id,
        payload.novel_id,
        payload.model_id,
        payload.chapter_index,
        payload.user_instruction,
    )


@router.post("/scenes/{scene_id}/generate-shots", response_model=AiShotsResult)
def generate_shots(
    project_id: str, scene_id: str, payload: ShotsGenerateRequest, request: Request
) -> AiShotsResult:
    return request.app.state.ai_script_service.generate_shots(
        project_id, scene_id, payload.model_id, payload.user_instruction
    )


@router.get("/scenes/{scene_id}", response_model=SceneDetail)
def get_scene(project_id: str, scene_id: str, request: Request) -> SceneDetail:
    return _repo(request).get_scene_detail(project_id, scene_id)


@router.post("/scenes/{scene_id}/save-shots", response_model=SceneDetail, status_code=201)
def save_scene_shots(
    project_id: str, scene_id: str, payload: dict, request: Request
) -> SceneDetail:
    """保存 AI 生成的分镜（shots）。"""
    shots = payload.get("shots") or []
    return _repo(request).save_scene_shots(
        project_id, scene_id, [ShotCreate(**s) for s in shots]
    )


@router.delete("/scenes/{scene_id}", status_code=204)
def delete_scene(project_id: str, scene_id: str, request: Request):
    _repo(request).soft_delete_scene(project_id, scene_id)


@router.put("/scenes/{scene_id}", response_model=Scene)
def update_scene(
    project_id: str, scene_id: str, payload: SceneUpdate, request: Request
) -> Scene:
    return _repo(request).update_scene(project_id, scene_id, payload)


@router.put("/scenes/{scene_id}/shots/{shot_id}", response_model=Shot)
def update_shot(
    project_id: str,
    scene_id: str,
    shot_id: str,
    payload: ShotUpdate,
    request: Request,
) -> Shot:
    return _repo(request).update_shot(project_id, scene_id, shot_id, payload)


@router.delete("/scenes/{scene_id}/shots/{shot_id}", status_code=204)
def delete_shot(project_id: str, scene_id: str, shot_id: str, request: Request):
    _repo(request).soft_delete_shot(project_id, scene_id, shot_id)

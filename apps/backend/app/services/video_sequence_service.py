"""多分镜合成服务：把有序的分镜视频拼接为场景 / 分集成片。

纯本地 FFmpeg 操作，不调用任何 AI API，不产生费用；
结果写入 versions（scene_video / episode_video）并登记生产依赖边。
"""

from pathlib import Path

from app.core.errors import AppError
from app.services.asset_version_service import AssetVersionService
from app.services.job_store import JOB_TYPE_VIDEO_COMPOSE
from app.services.media_mix import concat_videos
from app.services.production_graph import ProductionGraphService
from app.services.script_repo import ScriptRepository


class VideoSequenceService:
    def __init__(
        self,
        db_path,
        asset_version_service: AssetVersionService,
        projects_dir,
    ) -> None:
        self.db_path = db_path
        self.versions = asset_version_service
        self.projects_dir = Path(projects_dir)
        self.graph = ProductionGraphService(db_path)

    def create_job(
        self,
        store,
        project_id: str,
        *,
        scene_id: str = "",
        episode_id: str = "",
    ) -> dict:
        if bool(scene_id) == bool(episode_id):
            raise AppError(
                422,
                "compose_target_required",
                "请指定要合成的场景或分集（二选一）",
            )
        repo = ScriptRepository(self.db_path)
        if scene_id:
            repo.get_scene(project_id, scene_id)
            entity_type, entity_id = "scene", scene_id
        else:
            repo.get_episode(project_id, episode_id)
            entity_type, entity_id = "episode", episode_id
        return store.create(
            JOB_TYPE_VIDEO_COMPOSE,
            project_id,
            model_id="",
            provider_id="",
            capability="video_compose",
            input_payload={"entity_type": entity_type, "entity_id": entity_id},
        )

    def get_job(self, store, job_id: str) -> dict:
        return store.get(job_id)

    def run(self, job, store) -> dict:
        payload = job.input_payload or {}
        entity_type = payload.get("entity_type")
        entity_id = payload.get("entity_id")
        project_id = job.project_id
        if entity_type not in ("scene", "episode") or not entity_id:
            raise AppError(422, "compose_invalid_payload", "合成任务参数不合法")

        repo = ScriptRepository(self.db_path)
        if entity_type == "scene":
            detail = repo.get_scene_detail(project_id, entity_id)
            items = detail.shots
            source_version_type = "shot_video"
            source_node_type = "shot"
        else:
            detail = repo.get_episode_detail(project_id, entity_id)
            items = detail.scenes
            source_version_type = "scene_video"
            source_node_type = "scene"

        video_paths: list[str] = []
        missing: list[str] = []
        sources: list[tuple[str, str, int]] = []
        for item in items:
            record = self.versions.get_current(
                project_id, source_version_type, item.id
            )
            if record is None:
                missing.append(item.id)
                continue
            video_paths.append(record.file_path)
            sources.append((item.id, record.id, record.version))

        if missing:
            label = "分镜" if entity_type == "scene" else "场景成片"
            raise AppError(
                422,
                "compose_source_missing",
                f"还有 {len(missing)} 个{label}未生成视频，无法合成",
            )
        if len(video_paths) < 1:
            raise AppError(422, "compose_empty", "没有可合成的视频")

        out_entity_type = "scene_video" if entity_type == "scene" else "episode_video"
        tmp_dir = self.projects_dir / project_id / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_output = tmp_dir / f"compose_{job.id}.mp4"
        try:
            concat_videos(video_paths, str(tmp_output))
            record = self.versions.add_version(
                project_id,
                out_entity_type,
                entity_id,
                source_path=tmp_output,
                file_ext="mp4",
                model_id="",
                provider_id="",
                job_id=job.id,
                payload={
                    "composed_from": [
                        {"type": source_node_type, "id": sid, "version": ver}
                        for sid, _rid, ver in sources
                    ],
                    "segment_count": len(video_paths),
                },
            )
            for source_id, _rid, _ver in sources:
                self.graph.add_edge(
                    project_id,
                    source_node_type,
                    source_id,
                    "video_version",
                    record.id,
                    relation="composed_from",
                )
        finally:
            try:
                tmp_output.unlink(missing_ok=True)
            except OSError:
                pass

        return {
            "version_id": record.id,
            "entity_type": out_entity_type,
            "entity_id": entity_id,
            "segment_count": len(video_paths),
        }

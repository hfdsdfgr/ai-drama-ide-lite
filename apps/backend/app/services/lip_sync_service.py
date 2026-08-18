"""Phase 14 M3 - Lip Sync service.

独立 Job：Video + Final Audio -> Lip Sync -> Synced Video。
不读台词、不调 TTS、不估算时长；只消费无声视频与最终音频母带。
"""

import shutil
import uuid
from pathlib import Path

from app.core.errors import AppError
from app.services.audio_mix_session_repository import AudioMixSessionRepository
from app.services.job_store import JOB_TYPE_LIP_SYNC
from app.services.lipsync_adapter import LipSyncAdapter, PassThroughLipSyncAdapter


class LipSyncService:
    def __init__(
        self,
        db_path,
        asset_version_service,
        projects_dir,
        adapter: LipSyncAdapter | None = None,
    ) -> None:
        self.db_path = db_path
        self.versions = asset_version_service
        self.projects_dir = Path(projects_dir)
        self.mix_sessions = AudioMixSessionRepository(db_path)
        self.adapter = adapter or PassThroughLipSyncAdapter()

    def create_job(
        self,
        store,
        project_id: str,
        shot_id: str,
    ):
        video = self.versions.get_current(project_id, "shot_video", shot_id)
        if video is None:
            raise AppError(
                422,
                "shot_video_missing",
                "请先生成该镜头的无声视频，再进行 Lip Sync",
            )
        sessions = self.mix_sessions.list_for_shot(project_id, shot_id)
        master = next(
            (
                s
                for s in sessions
                if s["status"] == "completed" and s["output_audio_path"]
            ),
            None,
        )
        if master is None:
            raise AppError(
                422,
                "audio_master_missing",
                "请先完成配音（混音）生成最终音频母带，再进行 Lip Sync",
            )

        return store.create(
            JOB_TYPE_LIP_SYNC,
            project_id,
            capability="lip_sync",
            input_payload={
                "shot_id": shot_id,
                "video_path": video.file_path,
                "audio_path": master["output_audio_path"],
                "mix_session_id": master["id"],
            },
        )

    def run(self, job, store) -> dict:
        payload = job.input_payload or {}
        project_id = job.project_id
        shot_id = payload["shot_id"]
        video_path = payload.get("video_path") or ""
        audio_path = payload.get("audio_path") or ""
        if not video_path or not audio_path:
            raise AppError(
                422,
                "lip_sync_input_missing",
                "Lip Sync 输入不完整：缺少视频或音频",
            )

        tmp_dir = self.projects_dir / project_id / ".tmp" / f"lipsync_{job.id}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        output = tmp_dir / f"lipsync_{uuid.uuid4().hex[:8]}.mp4"
        try:
            self.adapter.sync(video_path, audio_path, str(output))
            if not output.is_file():
                raise AppError(
                    500, "lip_sync_no_output", "Lip Sync 未生成输出视频"
                )
            record = self.versions.add_version(
                project_id,
                "shot_video_lip_synced",
                shot_id,
                source_path=output,
                file_ext="mp4",
                model_id=job.model_id,
                provider_id=job.provider_id,
                job_id=job.id,
                payload={
                    "video_path": video_path,
                    "audio_path": audio_path,
                    "mix_session_id": payload.get("mix_session_id", ""),
                    "adapter": self.adapter.name,
                },
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return {
            "version_id": record.id,
            "entity_type": record.entity_type,
            "entity_id": shot_id,
            "adapter": self.adapter.name,
        }

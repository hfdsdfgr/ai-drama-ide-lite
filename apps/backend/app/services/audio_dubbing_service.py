"""Phase 14 M2 — 角色自动配音服务。

流程：台词归属（LLM）→ 角色音色匹配 → 逐角色 TTS → 混音 → 合成有声视频 → 写版本。
"""

import re
from pathlib import Path

from app.core.errors import AppError
from app.services.audio_mix_service import AudioMixService
from app.services.dialogue_planning_service import DialoguePlanningService
from app.services.media_compose_service import MediaComposeService
from app.services.script_repo import ScriptRepository
from app.services.story_repo import StoryRepository
from app.services.voice_synthesis_service import VoiceSynthesisService


class AudioDubbingService:
    def __init__(self, db_path, manager, asset_version_service, projects_dir) -> None:
        self.db_path = db_path
        self.manager = manager
        self.versions = asset_version_service
        self.projects_dir = Path(projects_dir)
        self.dialogue_planner = DialoguePlanningService(manager)
        self.voice_synthesizer = VoiceSynthesisService(manager)
        self.audio_mixer = AudioMixService()
        self.media_composer = MediaComposeService()

    def create_job(
        self,
        store,
        project_id: str,
        shot_id: str,
        *,
        voice_model_id: str = "",
        script_model_id: str = "",
        voice: str = "",
        bgm_path: str = "",
    ):
        video = self.versions.get_current(project_id, "shot_video", shot_id)
        if video is None:
            raise AppError(
                422,
                "shot_video_missing",
                "请先生成该镜头的视频，再进行配音",
            )
        shot, _scene = ScriptRepository(self.db_path).get_shot_with_scene(
            project_id, shot_id
        )
        if not shot.dialogue.strip() and not bgm_path:
            raise AppError(
                422,
                "audio_required",
                "该镜头没有台词，请先导入音效或背景音乐文件，再进行配音",
            )

        has_dialogue = bool(shot.dialogue.strip())
        if has_dialogue:
            voice_model = self._pick_model(
                "audio", "text_to_speech", voice_model_id, "语音合成模型"
            )
            script_model = self._pick_model("llm", None, script_model_id, "文本模型")
            model_id = voice_model.id
            provider_id = voice_model.provider_id
            capability = "text_to_speech"
            script_id = script_model.id
        else:
            model_id = ""
            provider_id = ""
            capability = "audio_mix"
            script_id = ""

        return store.create(
            "dubbing",
            project_id,
            model_id=model_id,
            provider_id=provider_id,
            capability=capability,
            input_payload={
                "shot_id": shot_id,
                "script_model_id": script_id,
                "voice": voice,
                "bgm_path": bgm_path,
            },
        )

    def run(self, job) -> dict:
        payload = job.input_payload or {}
        project_id = job.project_id
        shot_id = payload["shot_id"]
        script_model_id = payload.get("script_model_id") or ""
        voice_override = payload.get("voice") or ""
        bgm_path = payload.get("bgm_path") or ""

        shot, _scene = ScriptRepository(self.db_path).get_shot_with_scene(
            project_id, shot_id
        )
        video = self.versions.get_current(project_id, "shot_video", shot_id)
        if video is None:
            raise AppError(422, "shot_video_missing", "该镜头的视频已不存在，无法配音")
        has_dialogue = bool(shot.dialogue.strip())
        if has_dialogue:
            voice_model = self.manager.repo.get_model(job.model_id)
            response_format = (
                "wav" if voice_model.provider_preset_key == "zhipu" else "mp3"
            )
        else:
            response_format = ""

        if has_dialogue:
            character_voices = self._character_voices(project_id)
            characters = [
                name.strip()
                for name in re.split(r"[,，]", shot.characters or "")
                if name.strip()
            ]
            lines = self.dialogue_planner.plan(
                script_model_id, shot.dialogue, characters
            )
        else:
            character_voices = {}
            lines = []

        tmp_dir = self.projects_dir / project_id / ".tmp" / f"dub_{job.id}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        voice_paths: list[str] = []
        try:
            voice_paths = self.voice_synthesizer.synthesize(
                job.model_id,
                lines,
                character_voices=character_voices,
                voice_override=voice_override,
                response_format=response_format,
                output_dir=str(tmp_dir),
            )

            audio_master = tmp_dir / "audio_master.wav"
            self.audio_mixer.mix_to_master(
                video.file_path,
                voice_paths,
                str(audio_master),
                bgm_path=bgm_path or None,
            )

            tmp_output = tmp_dir / "dubbed.mp4"
            self.media_composer.compose(
                video.file_path,
                str(audio_master),
                str(tmp_output),
            )
            record = self.versions.add_version(
                project_id,
                "shot_video_voiced",
                shot_id,
                source_path=tmp_output,
                file_ext="mp4",
                model_id=job.model_id,
                provider_id=job.provider_id,
                job_id=job.id,
                payload={
                    "dialogue": shot.dialogue,
                    "lines": lines,
                    "voice_model_id": job.model_id,
                    "bgm_path": bgm_path,
                },
            )
            return {
                "version_id": record.id,
                "entity_type": record.entity_type,
                "lines": lines,
            }
        finally:
            for path in voice_paths:
                try:
                    Path(path).unlink(missing_ok=True)
                except OSError:
                    pass
            for name in ("audio_master.wav", "dubbed.mp4"):
                try:
                    (tmp_dir / name).unlink(missing_ok=True)
                except OSError:
                    pass

    def _pick_model(self, model_type: str, capability: str | None, model_id: str, label: str):
        models = self.manager.repo.list_models(
            model_type=model_type,
            enabled_only=True,
            capability=capability,
        )
        if model_id:
            match = next((m for m in models if m.id == model_id), None)
            if match is None:
                raise AppError(422, "model_unavailable", f"所选{label}不可用，请刷新后重试")
            return match
        if not models:
            raise AppError(
                422,
                "no_model_available",
                f"没有可用的{label}，请先在设置中启用并配置 API Key",
            )
        return models[0]

    def _character_voices(self, project_id: str) -> dict[str, str]:
        bible = StoryRepository(self.db_path).get_bible(project_id)
        voices: dict[str, str] = {}
        if bible is None:
            return voices
        for character in bible.characters:
            if not character.voice_id:
                continue
            voices[character.name] = character.voice_id
            for alias in character.aliases:
                voices[alias] = character.voice_id
        return voices

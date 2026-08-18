"""Phase 14 M2 — 角色自动配音服务。

流程：台词归属（LLM）→ 角色音色匹配 → 逐角色 TTS → 混音 → 合成有声视频 → 写版本。
"""

import re
import shutil
from pathlib import Path

from app.core.errors import AppError
from app.services.audio_mix_service import AudioMixService
from app.services.audio_mix_session_repository import AudioMixSessionRepository
from app.services.audio_stem_repository import AudioStemRepository
from app.services.dialogue_clip_repository import DialogueClipRepository
from app.services.dialogue_planning_service import DialoguePlanningService
from app.services.job_store import (
    CATEGORY_PERMANENT,
    JOB_TYPE_AUDIO_MIXING,
    JOB_TYPE_AUDIO_SEPARATION,
    JOB_TYPE_DIALOGUE_PLANNING,
    JOB_TYPE_MEDIA_COMPOSE,
    JOB_TYPE_TTS_GENERATION,
)
from app.services.media_compose_service import MediaComposeService
from app.services.script_repo import ScriptRepository
from app.services.story_repo import StoryRepository
from app.services.timeline_service import TimelineService
from app.services.voice_synthesis_service import VoiceClip, VoiceSynthesisService


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
        self.audio_stems = AudioStemRepository(db_path)
        self.mix_sessions = AudioMixSessionRepository(db_path)
        self.dialogue_clips = DialogueClipRepository(db_path)
        self.timeline = TimelineService()

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

    def run(self, job, store) -> dict:
        payload = job.input_payload or {}
        project_id = job.project_id
        shot_id = payload["shot_id"]
        script_model_id = payload.get("script_model_id") or ""
        voice_override = payload.get("voice") or ""
        bgm_path = payload.get("bgm_path") or ""
        subjob_ids: list[str] = []

        separation_job = self._start_subjob(
            store,
            project_id,
            JOB_TYPE_AUDIO_SEPARATION,
            payload={"mode": "pass_through"},
        )
        subjob_ids.append(separation_job.id)
        store.mark_completed(
            separation_job.id,
            result_payload={"mode": "pass_through", "stem_ids": []},
        )

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
            dialogue_job = self._start_subjob(
                store,
                project_id,
                JOB_TYPE_DIALOGUE_PLANNING,
                model_id=script_model_id,
                capability="dialogue_planning",
                payload={
                    "dialogue": shot.dialogue,
                    "characters": characters,
                },
            )
            subjob_ids.append(dialogue_job.id)
            try:
                lines = self.dialogue_planner.plan(
                    script_model_id, shot.dialogue, characters
                )
            except Exception as exc:
                store.mark_failed(dialogue_job.id, str(exc), CATEGORY_PERMANENT)
                raise
            store.mark_completed(
                dialogue_job.id,
                result_payload={"lines": lines},
            )
        else:
            character_voices = {}
            lines = []

        tmp_dir = self.projects_dir / project_id / ".tmp" / f"dub_{job.id}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        voice_clips: list[VoiceClip] = []
        tts_job = None
        if has_dialogue:
            tts_job = self._start_subjob(
                store,
                project_id,
                JOB_TYPE_TTS_GENERATION,
                model_id=job.model_id,
                provider_id=job.provider_id,
                capability="text_to_speech",
                payload={
                    "lines": lines,
                    "voice_override": voice_override,
                    "response_format": response_format,
                },
            )
            subjob_ids.append(tts_job.id)
        try:
            if has_dialogue:
                try:
                    voice_clips = self.voice_synthesizer.synthesize(
                        job.model_id,
                        lines,
                        character_voices=character_voices,
                        voice_override=voice_override,
                        response_format=response_format,
                        output_dir=str(tmp_dir),
                    )
                except Exception as exc:
                    if tts_job is not None:
                        store.mark_failed(tts_job.id, str(exc), CATEGORY_PERMANENT)
                    raise
                if tts_job is not None:
                    store.mark_completed(
                        tts_job.id,
                        result_payload={"line_count": len(lines)},
                    )

            stem_dir = self.projects_dir / project_id / "audio" / "stems" / shot_id
            stem_dir.mkdir(parents=True, exist_ok=True)
            stem_records = []
            persistent_voice_paths: list[str] = []
            persistent_voice_clip_paths: list[str] = []
            for index, voice_clip in enumerate(voice_clips):
                ext = Path(voice_clip.path).suffix.lstrip(".") or "wav"
                target = stem_dir / f"{job.id}_{index}.{ext}"
                shutil.copyfile(voice_clip.path, target)
                voice_id = (
                    (voice_clip.result.meta or {}).get("voice", "")
                    if voice_clip.result
                    else ""
                )
                record = self.audio_stems.create(
                    project_id,
                    shot_id,
                    role="dialogue",
                    source_type="tts",
                    file_path=str(target),
                    format=ext,
                    model_id=job.model_id,
                    provider_id=job.provider_id,
                    job_id=job.id,
                    order_index=index,
                    payload={
                        "character": voice_clip.character,
                        "text": voice_clip.text,
                        "voice_profile_id": voice_id,
                    },
                )
                stem_records.append(record)
                persistent_voice_paths.append(str(target))
                persistent_voice_clip_paths.append(str(target))

            if voice_clips:
                clip_items = [
                    {
                        "path": persistent_voice_clip_paths[index],
                        "audio_asset_id": stem_records[index]["id"],
                        "speaker_id": vc.character,
                        "voice_profile_id": (
                            (vc.result.meta or {}).get("voice", "")
                            if vc.result
                            else ""
                        ),
                        "result": vc.result,
                    }
                    for index, vc in enumerate(voice_clips)
                ]
                clip_records = self.dialogue_clips.replace_for_shot(
                    project_id,
                    shot_id,
                    self.timeline.build_dialogue_clips(
                        project_id,
                        clip_items,
                        shot_id=shot_id,
                        version=1,
                    ),
                    job_id=job.id,
                )
            else:
                clip_records = []

            persistent_bgm_path = None
            if bgm_path:
                bgm_source = Path(bgm_path)
                if not bgm_source.is_file():
                    raise AppError(422, "audio_missing", f"音效 / BGM 文件不存在: {bgm_path}")
                bgm_ext = bgm_source.suffix.lstrip(".") or "wav"
                bgm_target = stem_dir / f"{job.id}_bgm.{bgm_ext}"
                shutil.copyfile(bgm_source, bgm_target)
                bgm_record = self.audio_stems.create(
                    project_id,
                    shot_id,
                    role="bgm",
                    source_type="upload",
                    file_path=str(bgm_target),
                    format=bgm_ext,
                    model_id=job.model_id,
                    provider_id=job.provider_id,
                    job_id=job.id,
                    order_index=len(stem_records),
                    payload={"source": bgm_path},
                )
                stem_records.append(bgm_record)
                persistent_bgm_path = str(bgm_target)

            mix_session = self.mix_sessions.create(
                project_id,
                shot_id,
                stem_ids=[record["id"] for record in stem_records],
                gain_settings={},
                status="mixing",
            )
            mixing_job = self._start_subjob(
                store,
                project_id,
                JOB_TYPE_AUDIO_MIXING,
                payload={
                    "mix_session_id": mix_session["id"],
                    "stem_ids": [record["id"] for record in stem_records],
                },
            )
            subjob_ids.append(mixing_job.id)
            mix_dir = self.projects_dir / project_id / "audio" / "mixes" / shot_id
            mix_dir.mkdir(parents=True, exist_ok=True)
            audio_master = mix_dir / f"{mix_session['id']}.wav"
            try:
                self.audio_mixer.mix_to_master(
                    video.file_path,
                    persistent_voice_paths,
                    str(audio_master),
                    bgm_path=persistent_bgm_path,
                )
            except Exception as exc:
                store.mark_failed(mixing_job.id, str(exc), CATEGORY_PERMANENT)
                self.mix_sessions.update(
                    mix_session["id"],
                    status="failed",
                    error=str(exc),
                )
                raise
            store.mark_completed(
                mixing_job.id,
                result_payload={
                    "mix_session_id": mix_session["id"],
                    "output_audio_path": str(audio_master),
                },
            )
            self.mix_sessions.update(
                mix_session["id"],
                status="completed",
                output_audio_path=str(audio_master),
            )

            tmp_output = tmp_dir / "dubbed.mp4"
            compose_job = self._start_subjob(
                store,
                project_id,
                JOB_TYPE_MEDIA_COMPOSE,
                payload={
                    "video_path": video.file_path,
                    "audio_path": str(audio_master),
                    "mix_session_id": mix_session["id"],
                },
            )
            subjob_ids.append(compose_job.id)
            try:
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
            except Exception as exc:
                store.mark_failed(compose_job.id, str(exc), CATEGORY_PERMANENT)
                raise
            store.mark_completed(
                compose_job.id,
                result_payload={
                    "version_id": record.id,
                    "entity_type": record.entity_type,
                },
            )
            return {
                "version_id": record.id,
                "entity_type": record.entity_type,
                "lines": lines,
                "subjob_ids": subjob_ids,
                "mix_session_id": mix_session["id"],
                "clip_ids": [clip["id"] for clip in clip_records],
            }
        finally:
            for voice_clip in voice_clips:
                try:
                    Path(voice_clip.path).unlink(missing_ok=True)
                except OSError:
                    pass
            try:
                (tmp_dir / "dubbed.mp4").unlink(missing_ok=True)
            except OSError:
                pass

    def _start_subjob(
        self,
        store,
        project_id: str,
        job_type: str,
        *,
        model_id: str = "",
        provider_id: str = "",
        capability: str = "",
        payload: dict | None = None,
    ):
        subjob = store.create(
            job_type,
            project_id,
            model_id=model_id,
            provider_id=provider_id,
            capability=capability,
            input_payload=payload or {},
        )
        if not store.mark_running(subjob.id):
            raise AppError(
                500,
                "subjob_start_failed",
                f"无法启动音频子任务: {job_type}",
            )
        return subjob

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

"""Phase 14 M2 — 配音服务测试。"""

import json
import subprocess
from pathlib import Path

from app.db.database import get_connection, init_db
from app.services.adapters.base import GenerationResult
from app.services.audio_mix_session_repository import AudioMixSessionRepository
from app.services.audio_stem_repository import AudioStemRepository
from app.services.asset_version_service import AssetVersionService
from app.services.audio_dubbing_service import AudioDubbingService
from app.services.dialogue_clip_repository import DialogueClipRepository
from app.services.job_store import JobStore
from app.services.media_mix import ffmpeg_exe, mix_audio_video


def _now() -> str:
    return "2026-08-16T00:00:00Z"


def _make_test_media(tmp_path: Path) -> tuple[str, str]:
    video = tmp_path / "silent.mp4"
    voice = tmp_path / "voice.wav"
    subprocess.run(
        [
            ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:d=2",
            "-c:v",
            "libx264",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            str(voice),
        ],
        check=True,
        capture_output=True,
    )
    return str(video), str(voice)


def test_mix_audio_video(tmp_path):
    video, voice = _make_test_media(tmp_path)
    output = tmp_path / "voiced.mp4"
    result = mix_audio_video(video, [voice], str(output))
    assert result == str(output)
    assert output.is_file()
    assert output.stat().st_size > 0


class _FakeRepo:
    def __init__(self, llm_id, audio_id):
        self._llm = _Model(llm_id, "llm", "llm-model")
        self._audio = _Model(audio_id, "audio", "tts-model")

    def get_model(self, model_id):
        if model_id == self._llm.id:
            return self._llm
        if model_id == self._audio.id:
            return self._audio
        raise KeyError(model_id)

    def list_models(self, model_type=None, enabled_only=False, capability=None):
        if model_type == "llm":
            return [self._llm]
        if model_type == "audio":
            return [self._audio]
        return []


class _Model:
    def __init__(self, id, model_type, model_id):
        self.id = id
        self.model_type = model_type
        self.model_id = model_id
        self.provider_id = "prov"
        self.provider_preset_key = ""


class _FakeManager:
    def __init__(self, repo, voice_path):
        self.repo = repo
        self.voice_path = voice_path

    def chat(self, model_id, messages, temperature=0.8, timeout=60):
        return json.dumps(
            [
                {"character": "林凡", "text": "你好。"},
                {"character": "苏璃", "text": "快走。"},
            ],
            ensure_ascii=False,
        )

    def generate(self, model_id, capability, request):
        return GenerationResult(urls=[self.voice_path], meta={"format": "wav"})


def _setup_project(tmp_path: Path):
    db_path = tmp_path / "test.db"
    projects_dir = tmp_path / "projects"
    init_db(db_path)
    with get_connection(db_path) as conn:
        now = _now()
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES ('p', 'p', '', ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('scene1', 'p', NULL, NULL, '场', 0, '', '', '', NULL, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', 'p', 'scene1', 1, 0, '', '', '林凡,苏璃', '', '', '你好。快走。', 5, '', NULL, ?, ?)",
            (now, now),
        )
    return db_path, projects_dir


def test_run_dubbing_writes_voiced_version(tmp_path):
    db_path, projects_dir = _setup_project(tmp_path)
    video, voice = _make_test_media(tmp_path)
    versions = AssetVersionService(db_path, projects_dir)
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO versions (id, project_id, entity_type, entity_id, version, payload, file_path, model_id, provider_id, job_id, is_current, created_at) VALUES ('v_video', 'p', 'shot_video', 'shot1', 1, '{}', ?, '', '', '', 1, ?)",
            (video, _now()),
        )

    repo = _FakeRepo("m_llm", "m_audio")
    manager = _FakeManager(repo, voice)
    service = AudioDubbingService(db_path, manager, versions, projects_dir)
    store = JobStore(db_path)
    job = store.create(
        "dubbing",
        "p",
        model_id="m_audio",
        provider_id="prov",
        capability="text_to_speech",
        input_payload={"shot_id": "shot1", "script_model_id": "m_llm"},
    )

    result = service.run(job, store)

    assert result["entity_type"] == "shot_video_voiced"
    current = versions.get_current("p", "shot_video_voiced", "shot1")
    assert current is not None
    assert Path(current.file_path).is_file()
    assert current.file_path.endswith(".mp4")
    stems = AudioStemRepository(db_path).list_for_shot("p", "shot1")
    assert len(stems) == 2
    assert {stem["role"] for stem in stems} == {"dialogue"}
    sessions = AudioMixSessionRepository(db_path).list_for_shot("p", "shot1")
    assert len(sessions) == 1
    assert sessions[0]["status"] == "completed"
    assert Path(sessions[0]["output_audio_path"]).is_file()
    clips = DialogueClipRepository(db_path).list_for_shot("p", "shot1")
    assert len(clips) == 2
    assert all(clip["alignment"] is not None for clip in clips)
    assert all(
        clip["alignment"].source == "audio_duration_only" for clip in clips
    )
    assert clips[1]["start_time"] >= clips[0]["end_time"]
    subjobs = store.list_jobs(project_id="p")
    assert {subjob.type for subjob in subjobs} >= {
        "audio_separation",
        "dialogue_planning",
        "tts_generation",
        "audio_mixing",
        "media_compose",
    }

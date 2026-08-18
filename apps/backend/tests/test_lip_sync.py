"""Phase 14 M3 - Lip Sync service / adapter tests."""

import subprocess
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.db.database import get_connection, init_db
from app.services.asset_version_service import AssetVersionService
from app.services.job_store import JOB_TYPE_LIP_SYNC, JobStore
from app.services.lip_sync_service import LipSyncService
from app.services.lipsync_adapter import PassThroughLipSyncAdapter
from app.services.media_mix import ffmpeg_exe


def _now() -> str:
    return "2026-08-18T00:00:00Z"


def _make_test_media(tmp_path: Path) -> tuple[str, str]:
    video = tmp_path / "silent.mp4"
    audio = tmp_path / "master.wav"
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
            str(audio),
        ],
        check=True,
        capture_output=True,
    )
    return str(video), str(audio)


def _setup_project(tmp_path: Path) -> tuple[Path, Path]:
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
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', 'p', NULL, 1, 0, '', '', '', '', '', '你好。', 5, '', NULL, ?, ?)",
            (now, now),
        )
    return db_path, projects_dir


def test_pass_through_adapter_combines_video_and_audio(tmp_path):
    video, audio = _make_test_media(tmp_path)
    output = tmp_path / "synced.mp4"

    result = PassThroughLipSyncAdapter().sync(video, audio, str(output))

    assert result == str(output)
    assert output.is_file()
    assert output.stat().st_size > 0


def test_pass_through_adapter_rejects_missing_inputs(tmp_path):
    _, audio = _make_test_media(tmp_path)

    with pytest.raises(AppError):
        PassThroughLipSyncAdapter().sync(
            str(tmp_path / "missing.mp4"), audio, str(tmp_path / "out.mp4")
        )


def test_create_job_requires_video_and_audio_master(tmp_path):
    db_path, projects_dir = _setup_project(tmp_path)
    service = LipSyncService(db_path, AssetVersionService(db_path, projects_dir), projects_dir)
    store = JobStore(db_path)

    with pytest.raises(AppError):
        service.create_job(store, "p", "shot1")


def test_create_job_and_run_writes_lip_synced_version(tmp_path):
    db_path, projects_dir = _setup_project(tmp_path)
    video, audio = _make_test_media(tmp_path)
    versions = AssetVersionService(db_path, projects_dir)
    with get_connection(db_path) as conn:
        now = _now()
        conn.execute(
            "INSERT INTO versions (id, project_id, entity_type, entity_id, version, payload, file_path, model_id, provider_id, job_id, is_current, created_at) VALUES ('v_video', 'p', 'shot_video', 'shot1', 1, '{}', ?, '', '', '', 1, ?)",
            (video, now),
        )
        conn.execute(
            "INSERT INTO audio_mix_sessions (id, project_id, shot_id, status, stem_snapshot, gain_settings, output_audio_path, error, created_at, updated_at) VALUES ('mix1', 'p', 'shot1', 'completed', '[]', '{}', ?, '', ?, ?)",
            (audio, now, now),
        )

    service = LipSyncService(db_path, versions, projects_dir)
    store = JobStore(db_path)
    job = service.create_job(store, "p", "shot1")
    assert job.type == JOB_TYPE_LIP_SYNC

    result = service.run(job, store)

    assert result["entity_type"] == "shot_video_lip_synced"
    current = versions.get_current("p", "shot_video_lip_synced", "shot1")
    assert current is not None
    assert Path(current.file_path).is_file()
    assert current.file_path.endswith(".mp4")

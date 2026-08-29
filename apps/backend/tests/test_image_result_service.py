"""Phase 13 M3 - ImageResultService tests."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from app.db.database import get_connection, init_db
from app.services.adapters.base import GenerationResult
from app.services.image_result_service import ImageResultService
from app.services.media_mix import ffmpeg_exe, _probe_video
from app.services.story_repo import StoryRepository


class _Job:
    def __init__(self, project_id, input_payload, capability="image_to_image"):
        self.id = "job_1"
        self.project_id = project_id
        self.model_id = "model_img"
        self.provider_id = "prov_1"
        self.capability = capability
        self.input_payload = input_payload


def _init_project(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at)"
            " VALUES ('proj_1', 'p', '', ?, ?)",
            (now, now),
        )
    return db_path


def test_persist_local_asset_image_writes_version_and_edge(tmp_path, monkeypatch):
    db_path = _init_project(tmp_path)
    monkeypatch.setattr(
        StoryRepository,
        "list_assets",
        lambda self, project_id: [
            {"asset_type": "character", "asset_id": "character_lin_001", "name": "林凡"}
        ],
    )
    service = ImageResultService(db_path, tmp_path / "projects")
    local_file = tmp_path / "source.png"
    local_file.write_bytes(b"png-bytes")
    job = _Job(
        "proj_1",
        {
            "prompt": "male protagonist",
            "negative_prompt": "bad",
            "aspect_ratio": "1024x1536",
            "extra": {
                "target_type": "asset",
                "target_id": "character_lin_001",
                "source_refs": [],
            },
        },
    )

    records = service.persist(
        job, GenerationResult(urls=[str(local_file)], meta={})
    )

    assert len(records) == 1
    record = records[0]
    assert record.entity_type == "character"
    assert record.entity_id == "character_lin_001"
    target = (
        tmp_path
        / "projects"
        / "proj_1"
        / "assets"
        / "character_lin_001"
        / "v1.png"
    )
    assert target.read_bytes() == b"png-bytes"

    edges = service.graph.list_edges("proj_1")
    assert any(
        e.upstream_type == "asset"
        and e.upstream_id == "character_lin_001"
        and e.downstream_type == "image_version"
        and e.downstream_id == record.id
        for e in edges
    )


def test_persist_shot_image_writes_version_and_reference_edges(tmp_path):
    db_path = _init_project(tmp_path)
    service = ImageResultService(db_path, tmp_path / "projects")
    local_file = tmp_path / "shot.png"
    local_file.write_bytes(b"shot-bytes")
    job = _Job(
        "proj_1",
        {
            "prompt": "close-up",
            "negative_prompt": "",
            "aspect_ratio": "1280x720",
            "extra": {
                "target_type": "shot",
                "target_id": "shot_01",
                "source_refs": [
                    {
                        "type": "shot",
                        "id": "shot_01",
                        "relation": "image_generated_from_shot",
                    },
                    {
                        "type": "asset",
                        "id": "character_lin_001",
                        "relation": "shot_references_asset",
                    },
                ],
            },
        },
    )

    records = service.persist(
        job, GenerationResult(urls=[str(local_file)], meta={})
    )

    assert len(records) == 1
    record = records[0]
    assert record.entity_type == "shot"
    target = (
        tmp_path
        / "projects"
        / "proj_1"
        / "generated"
        / "shot"
        / "shot_01"
        / "v1.png"
    )
    assert target.read_bytes() == b"shot-bytes"

    edges = service.graph.list_edges("proj_1")
    assert any(
        e.upstream_type == "shot"
        and e.upstream_id == "shot_01"
        and e.downstream_id == record.id
        for e in edges
    )
    assert any(
        e.upstream_type == "asset"
        and e.upstream_id == "character_lin_001"
        and e.downstream_id == record.id
        for e in edges
    )


def test_persist_shot_video_strips_audio_track(tmp_path):
    """strip_audio=True 时，视频落库前应移除音轨（生成无声版本）。"""
    db_path = _init_project(tmp_path)
    service = ImageResultService(db_path, tmp_path / "projects")

    source = tmp_path / "with_audio.mp4"
    subprocess.run(
        [
            ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=320x240:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    assert _probe_video(source)["has_audio"] is True

    job = _Job(
        "proj_1",
        {
            "prompt": "shot motion",
            "negative_prompt": "",
            "aspect_ratio": "720P",
            "extra": {
                "target_type": "shot",
                "target_id": "shot_01",
                "strip_audio": True,
                "source_refs": [],
            },
        },
        capability="image_to_video",
    )
    records = service.persist(
        job, GenerationResult(urls=[str(source)], meta={})
    )

    assert len(records) == 1
    record = records[0]
    assert record.entity_type == "shot_video"
    assert _probe_video(Path(record.file_path))["has_audio"] is False


def test_persist_shot_video_keeps_audio_when_not_stripping(tmp_path):
    """未标记 strip_audio 时，视频音轨应原样保留。"""
    db_path = _init_project(tmp_path)
    service = ImageResultService(db_path, tmp_path / "projects")

    source = tmp_path / "with_audio.mp4"
    subprocess.run(
        [
            ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=320x240:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
        capture_output=True,
    )

    job = _Job(
        "proj_1",
        {
            "prompt": "shot motion",
            "negative_prompt": "",
            "aspect_ratio": "720P",
            "extra": {
                "target_type": "shot",
                "target_id": "shot_01",
                "strip_audio": False,
                "source_refs": [],
            },
        },
        capability="image_to_video",
    )
    records = service.persist(
        job, GenerationResult(urls=[str(source)], meta={})
    )

    assert len(records) == 1
    record = records[0]
    assert _probe_video(Path(record.file_path))["has_audio"] is True

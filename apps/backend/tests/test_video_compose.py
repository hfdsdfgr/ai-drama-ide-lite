"""多分镜合成（concat）测试：media_mix 拼接 + 合成服务 + API。"""

import subprocess

import pytest

from app.db.database import get_connection
from app.services.media_mix import _probe_video, concat_videos, ffmpeg_exe


def _make_video(path, seconds: int = 2, with_audio: bool = False):
    cmd = [
        ffmpeg_exe(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=red:s=320x240:d={seconds}",
    ]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if with_audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd.append(str(path))
    subprocess.run(cmd, check=True, capture_output=True)


def test_concat_videos_with_and_without_audio(tmp_path):
    v1 = tmp_path / "a.mp4"
    v2 = tmp_path / "b.mp4"
    out = tmp_path / "out.mp4"
    _make_video(v1, seconds=2, with_audio=True)
    _make_video(v2, seconds=2, with_audio=False)

    result = concat_videos([str(v1), str(v2)], str(out))

    assert result == str(out)
    assert out.is_file()
    probe = _probe_video(out)
    assert probe["duration"] == pytest.approx(4.0, abs=0.6)
    assert probe["has_audio"] is True


def test_concat_videos_silent_only(tmp_path):
    v1 = tmp_path / "a.mp4"
    v2 = tmp_path / "b.mp4"
    out = tmp_path / "out.mp4"
    _make_video(v1, seconds=2)
    _make_video(v2, seconds=3)

    concat_videos([str(v1), str(v2)], str(out))

    probe = _probe_video(out)
    assert probe["duration"] == pytest.approx(5.0, abs=0.6)
    assert probe["has_audio"] is False


def test_concat_videos_missing_file(tmp_path):
    with pytest.raises(Exception) as exc_info:
        concat_videos([str(tmp_path / "nope.mp4")], str(tmp_path / "out.mp4"))
    assert "不存在" in str(exc_info.value)


def _setup_scene_with_videos(client, tmp_path) -> tuple[str, str]:
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    db_path = client.app.state.settings.db_path
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('sc1', ?, NULL, NULL, '', 0, '', '', '', NULL, ?, ?)",
            (project_id, now, now),
        )
        for idx, shot_id in enumerate(("shot1", "shot2"), start=1):
            conn.execute(
                "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES (?, ?, 'sc1', ?, ?, '', '', '', '', '', '', 5, '', NULL, ?, ?)",
                (shot_id, project_id, idx, idx, now, now),
            )

    versions = client.app.state.asset_version_service
    for idx, shot_id in enumerate(("shot1", "shot2"), start=1):
        video = tmp_path / f"shot{idx}.mp4"
        _make_video(video, seconds=1, with_audio=idx == 1)
        versions.add_version(
            project_id,
            "shot_video",
            shot_id,
            source_path=video,
            file_ext="mp4",
        )
    return project_id, "sc1"


def test_compose_scene_service_writes_version_and_edge(client, tmp_path):
    project_id, scene_id = _setup_scene_with_videos(client, tmp_path)
    service = client.app.state.video_sequence_service
    store = client.app.state.job_store
    job = store.create(
        "video_compose",
        project_id,
        capability="video_compose",
        input_payload={"entity_type": "scene", "entity_id": scene_id},
    )

    result = service.run(job, store)

    assert result["entity_type"] == "scene_video"
    assert result["segment_count"] == 2
    record = client.app.state.asset_version_service.get_current(
        project_id, "scene_video", scene_id
    )
    assert record is not None
    assert record.file_path.endswith(".mp4")
    # 生产依赖边：scene_video 依赖两个 shot 视频
    edges = client.app.state.production_graph_service.list_edges(project_id)
    composed = [e for e in edges if e.downstream_id == record.id]
    assert len(composed) == 2
    assert all(e.relation == "composed_from" for e in composed)


def test_compose_scene_missing_video_rejected(client, tmp_path):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    db_path = client.app.state.settings.db_path
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('sc1', ?, NULL, NULL, '', 0, '', '', '', NULL, ?, ?)",
            (project_id, now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', ?, 'sc1', 1, 0, '', '', '', '', '', '', 5, '', NULL, ?, ?)",
            (project_id, now, now),
        )
    service = client.app.state.video_sequence_service
    store = client.app.state.job_store
    job = store.create(
        "video_compose",
        project_id,
        capability="video_compose",
        input_payload={"entity_type": "scene", "entity_id": "sc1"},
    )

    with pytest.raises(Exception) as exc_info:
        service.run(job, store)
    assert "未生成视频" in str(exc_info.value)


def test_compose_api_creates_job(client, tmp_path):
    project_id, scene_id = _setup_scene_with_videos(client, tmp_path)
    response = client.post(
        f"/api/projects/{project_id}/videos/compose",
        json={"scene_id": scene_id},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "video_compose"
    assert body["capability"] == "video_compose"
    assert body["status"] in ("queued", "running", "completed")


def test_compose_api_requires_one_target(client):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    response = client.post(
        f"/api/projects/{project_id}/videos/compose",
        json={},
    )
    assert response.status_code == 422

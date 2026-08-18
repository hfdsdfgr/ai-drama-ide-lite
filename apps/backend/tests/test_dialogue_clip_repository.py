"""Phase 14 M3 - DialogueClip repository tests."""

from pathlib import Path

from app.db.database import get_connection, init_db
from app.schemas.audio_timeline import (
    AlignmentChar,
    AlignmentResult,
    DialogueClip,
    DialogueClipSegment,
)
from app.services.dialogue_clip_repository import DialogueClipRepository


def _setup_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        now = "2026-08-18T00:00:00Z"
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES ('p', 'p', '', ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', 'p', NULL, 1, 0, '', '', '', '', '', '你好。', 5, '', NULL, ?, ?)",
            (now, now),
        )
    return db_path


def test_replace_for_shot_persists_clips(tmp_path):
    db_path = _setup_db(tmp_path)
    repo = DialogueClipRepository(db_path)
    clip = DialogueClip(
        id="clip_01",
        project_id="p",
        start_time=0.0,
        end_time=1.2,
        audio_asset_id="stem_01",
        speaker_id="林凡",
        voice_profile_id="voice_a",
        shot_id="shot1",
        version=1,
        alignment=AlignmentResult(
            source="provider",
            duration=1.2,
            characters=[AlignmentChar(char="你", start_time=0.0, end_time=0.4)],
            words=[],
        ),
        segments=[
            DialogueClipSegment(shot_id="shot1", start_time=0.0, end_time=1.2),
        ],
    )

    rows = repo.replace_for_shot("p", "shot1", [clip], job_id="job_01")

    assert len(rows) == 1
    assert rows[0]["id"] == "clip_01"
    assert rows[0]["audio_asset_id"] == "stem_01"
    assert rows[0]["speaker_id"] == "林凡"
    assert rows[0]["alignment"].source == "provider"
    assert rows[0]["alignment"].characters[0].char == "你"
    assert len(rows[0]["segments"]) == 1


def test_replace_for_shot_overwrites_old_clips(tmp_path):
    db_path = _setup_db(tmp_path)
    repo = DialogueClipRepository(db_path)
    old = DialogueClip(
        id="clip_old",
        project_id="p",
        start_time=0.0,
        end_time=1.0,
        shot_id="shot1",
    )
    new = DialogueClip(
        id="clip_new",
        project_id="p",
        start_time=0.0,
        end_time=2.0,
        shot_id="shot1",
    )

    repo.replace_for_shot("p", "shot1", [old], job_id="job_old")
    repo.replace_for_shot("p", "shot1", [new], job_id="job_new")

    rows = repo.list_for_shot("p", "shot1")
    assert [row["id"] for row in rows] == ["clip_new"]


def test_list_for_project_orders_by_shot(tmp_path):
    db_path = _setup_db(tmp_path)
    repo = DialogueClipRepository(db_path)
    clips = [
        DialogueClip(id=f"clip_{i}", project_id="p", shot_id="shot1")
        for i in range(2)
    ]
    repo.replace_for_shot("p", "shot1", clips, job_id="job_01")

    rows = repo.list_for_project("p")

    assert len(rows) == 2


def test_get_missing_clip_raises(tmp_path):
    db_path = _setup_db(tmp_path)

    try:
        DialogueClipRepository(db_path).get("nope")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass

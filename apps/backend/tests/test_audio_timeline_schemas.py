"""Phase 14 M3 - Voice / Timeline / Lip Sync schema tests."""

import pytest
from pydantic import ValidationError

from app.schemas.audio_timeline import (
    AlignmentChar,
    AlignmentResult,
    AlignmentWord,
    DialogueClip,
    DialogueClipSegment,
)


def test_dialogue_clip_requires_id_and_project():
    with pytest.raises(ValidationError):
        DialogueClip()


def test_dialogue_clip_holds_core_fields():
    clip = DialogueClip(
        id="clip_01",
        project_id="proj_01",
        start_time=0.0,
        end_time=3.5,
        audio_asset_id="asset_voice_01",
        speaker_id="char_linfan",
        voice_profile_id="voice_linfan",
        shot_id="shot_01",
        version=2,
    )

    assert clip.speaker_id == "char_linfan"
    assert clip.voice_profile_id == "voice_linfan"
    assert clip.audio_asset_id == "asset_voice_01"
    assert clip.shot_id == "shot_01"
    assert clip.version == 2
    assert clip.total_duration() == 3.5


def test_dialogue_clip_supports_multiple_shots():
    clip = DialogueClip(
        id="clip_02",
        project_id="proj_01",
        start_time=0.0,
        end_time=3.5,
        audio_asset_id="asset_voice_01",
        speaker_id="char_linfan",
        voice_profile_id="voice_linfan",
        segments=[
            DialogueClipSegment(shot_id="shot_01", start_time=0.0, end_time=1.8),
            DialogueClipSegment(shot_id="shot_02", start_time=1.8, end_time=3.5),
        ],
    )

    assert len(clip.segments) == 2
    assert [seg.shot_id for seg in clip.segments] == ["shot_01", "shot_02"]
    assert clip.segments[0].end_time == 1.8
    assert clip.segments[1].start_time == 1.8


def test_dialogue_clip_rejects_invalid_time_range():
    with pytest.raises(ValidationError):
        DialogueClip(
            id="clip_03",
            project_id="proj_01",
            start_time=5.0,
            end_time=2.0,
        )


def test_dialogue_clip_rejects_invalid_segment_range():
    with pytest.raises(ValidationError):
        DialogueClipSegment(shot_id="shot_01", start_time=2.0, end_time=1.0)


def test_alignment_result_supports_character_and_word():
    alignment = AlignmentResult(
        source="provider",
        duration=3.5,
        characters=[
            AlignmentChar(char="你", start_time=0.0, end_time=0.4),
            AlignmentChar(char="好", start_time=0.4, end_time=0.8),
        ],
        words=[
            AlignmentWord(word="你好", start_time=0.0, end_time=0.8),
        ],
    )

    assert alignment.source == "provider"
    assert len(alignment.characters) == 2
    assert alignment.characters[1].char == "好"
    assert alignment.words[0].start_time == 0.0
    assert alignment.phonemes == []


def test_alignment_result_rejects_unknown_source():
    with pytest.raises(ValidationError):
        AlignmentResult(source="llm_estimated", duration=1.0)


def test_alignment_result_audio_duration_only_has_no_timestamps():
    alignment = AlignmentResult(source="audio_duration_only", duration=2.0)

    assert alignment.characters == []
    assert alignment.words == []
    assert alignment.phonemes == []

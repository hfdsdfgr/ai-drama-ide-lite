"""Phase 14 M3 - Timeline / Alignment service tests."""

import subprocess

import pytest

from app.core.errors import AppError
from app.schemas.audio_timeline import AlignmentResult, DialogueClip
from app.services.adapters.base import GenerationResult
from app.services.media_mix import ffmpeg_exe
from app.services.timeline_service import TimelineService


def _make_silent_wav(path, seconds: float) -> str:
    """用 FFmpeg 生成指定秒数的静音 WAV，用于探测真实时长。"""
    subprocess.run(
        [
            ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=16000:cl=mono",
            "-t",
            str(seconds),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return str(path)


def test_probe_audio_duration_returns_real_duration(tmp_path):
    audio = _make_silent_wav(tmp_path / "silence.wav", 2.5)

    service = TimelineService()
    duration = service.probe_audio_duration(audio)

    assert duration == pytest.approx(2.5, abs=0.2)


def test_probe_audio_duration_fails_for_missing_file(tmp_path):
    service = TimelineService()

    with pytest.raises(AppError):
        service.probe_audio_duration(str(tmp_path / "missing.wav"))


def test_build_alignment_from_provider_object_list():
    result = GenerationResult(
        urls=["/tmp/a.wav"],
        alignment={
            "source": "provider",
            "duration": 1.2,
            "characters": [
                {"char": "你", "start_time": 0.0, "end_time": 0.4},
                {"char": "好", "start_time": 0.4, "end_time": 0.8},
            ],
            "words": [
                {"word": "你好", "start_time": 0.0, "end_time": 0.8},
            ],
        },
    )

    alignment = TimelineService().build_alignment(result)

    assert alignment is not None
    assert alignment.source == "provider"
    assert len(alignment.characters) == 2
    assert alignment.characters[1].char == "好"
    assert alignment.words[0].start_time == 0.0
    assert alignment.phonemes == []


def test_build_alignment_from_provider_parallel_arrays():
    """兼容 ElevenLabs 并行数组格式。"""
    result = GenerationResult(
        urls=["/tmp/a.wav"],
        alignment={
            "source": "provider",
            "characters": ["你", "好"],
            "character_start_times_seconds": [0.0, 0.4],
            "character_end_times_seconds": [0.4, 0.8],
            "words": ["你好"],
            "word_start_times_seconds": [0.0],
            "word_end_times_seconds": [0.8],
        },
    )

    alignment = TimelineService().build_alignment(result)

    assert alignment is not None
    assert [c.char for c in alignment.characters] == ["你", "好"]
    assert alignment.characters[1].end_time == 0.8
    assert alignment.words[0].word == "你好"


def test_build_alignment_returns_none_without_provider_data():
    result = GenerationResult(urls=["/tmp/a.wav"])

    alignment = TimelineService().build_alignment(result)

    assert alignment is None


def test_forced_alignment_reserved_returns_none(tmp_path):
    audio = _make_silent_wav(tmp_path / "silence.wav", 1.0)

    alignment = TimelineService().forced_alignment(audio, "你好")

    assert alignment is None


def test_build_dialogue_clips_uses_real_duration_and_offsets(tmp_path):
    first = _make_silent_wav(tmp_path / "first.wav", 1.0)
    second = _make_silent_wav(tmp_path / "second.wav", 2.0)
    service = TimelineService()

    clips = service.build_dialogue_clips(
        "proj_01",
        [
            {
                "path": first,
                "speaker_id": "char_linfan",
                "voice_profile_id": "voice_a",
                "result": None,
            },
            {
                "path": second,
                "speaker_id": "char_xiaofuzi",
                "voice_profile_id": "voice_b",
                "result": None,
            },
        ],
        shot_id="shot_01",
        version=1,
    )

    assert len(clips) == 2
    assert isinstance(clips[0], DialogueClip)
    assert clips[0].start_time == pytest.approx(0.0, abs=0.2)
    assert clips[0].end_time == pytest.approx(1.0, abs=0.2)
    assert clips[1].start_time == pytest.approx(1.0, abs=0.3)
    assert clips[1].end_time == pytest.approx(3.0, abs=0.3)
    assert clips[0].speaker_id == "char_linfan"
    assert clips[1].voice_profile_id == "voice_b"
    assert all(clip.shot_id == "shot_01" for clip in clips)
    assert all(clip.alignment.source == "audio_duration_only" for clip in clips)
    assert all(clip.alignment.characters == [] for clip in clips)


def test_build_dialogue_clips_keeps_provider_alignment(tmp_path):
    audio = _make_silent_wav(tmp_path / "a.wav", 1.0)
    result = GenerationResult(
        urls=[audio],
        alignment={
            "source": "provider",
            "characters": [{"char": "好", "start_time": 0.0, "end_time": 0.4}],
            "words": [],
        },
    )

    clips = TimelineService().build_dialogue_clips(
        "proj_01",
        [{"path": audio, "result": result}],
        shot_id="shot_01",
    )

    assert clips[0].alignment is not None
    assert clips[0].alignment.source == "provider"
    assert len(clips[0].alignment.characters) == 1

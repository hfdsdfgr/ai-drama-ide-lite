"""Phase 14 M3 - Split audio pipeline service tests."""

import json

from app.services.adapters.base import GenerationResult
from app.services.dialogue_planning_service import DialoguePlanningService
from app.services.voice_synthesis_service import VoiceSynthesisService


class _ChatManager:
    def chat(self, model_id, messages, temperature=0.8, timeout=60):
        return json.dumps(
            [
                {"character": "赵明", "text": "你来了。"},
                {"character": "小福子", "text": "少爷醒了！"},
            ],
            ensure_ascii=False,
        )


def test_dialogue_planning_service_parses_lines():
    service = DialoguePlanningService(_ChatManager())
    lines = service.plan(
        "llm_model",
        "赵明：你来了。\n小福子：少爷醒了！",
        ["赵明", "小福子"],
    )

    assert lines == [
        {"character": "赵明", "text": "你来了。"},
        {"character": "小福子", "text": "少爷醒了！"},
    ]


def test_dialogue_planning_service_falls_back_without_llm():
    service = DialoguePlanningService(_ChatManager())
    lines = service.plan("", "你好。快走。", ["赵明", "小福子"])

    assert lines == [{"character": "", "text": "你好。快走。"}]


class _TTSManager:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.calls = []

    def generate(self, model_id, capability, request):
        self.calls.append(request)
        path = self.output_dir / f"voice_{len(self.calls)}.wav"
        path.write_bytes(b"voice")
        return GenerationResult(urls=[str(path)], meta={"format": "wav"})


def test_voice_synthesis_service_generates_individual_stems(tmp_path):
    manager = _TTSManager(tmp_path)
    service = VoiceSynthesisService(manager)
    lines = [
        {"character": "赵明", "text": "你来了。"},
        {"character": "小福子", "text": "少爷醒了！"},
    ]

    paths = service.synthesize(
        "tts_model",
        lines,
        character_voices={"赵明": "voice_a", "小福子": "voice_b"},
        voice_override="",
        response_format="wav",
        output_dir=str(tmp_path),
    )

    assert len(paths) == 2
    assert [clip.character for clip in paths] == ["赵明", "小福子"]
    assert [clip.text for clip in paths] == ["你来了。", "少爷醒了！"]
    assert [call.extra["voice"] for call in manager.calls] == [
        "voice_a",
        "voice_b",
    ]
    assert all(call.extra["response_format"] == "wav" for call in manager.calls)
    assert all(clip.result is not None for clip in paths)

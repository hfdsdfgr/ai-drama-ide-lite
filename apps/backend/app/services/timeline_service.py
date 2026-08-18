"""Phase 14 M3 - Timeline / Alignment service.

职责：把 TTS 输出转换为真实的 Dialogue Timeline。

时间轴来源优先级（禁止伪造）：
1. TTS Provider 返回真实 timestamps / alignment；
2. Forced Alignment（预留，未配置时跳过）；
3. 只使用音频真实 duration，不伪造字符级时间戳。
"""

import re
import subprocess
import uuid
from pathlib import Path

from app.core.errors import AppError
from app.schemas.audio_timeline import (
    AlignmentChar,
    AlignmentResult,
    AlignmentWord,
    DialogueClip,
)
from app.services.adapters.base import GenerationResult
from app.services.media_mix import ffmpeg_exe


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


class TimelineService:
    """把 TTS 输出转换为真实 DialogueClip 时间轴。"""

    # ---------- 真实时长 ----------

    def probe_audio_duration(self, audio_path: str) -> float:
        """用 FFmpeg 探测音频真实时长（秒），失败即报错而不是估算。"""
        path = Path(audio_path)
        if not path.is_file():
            raise AppError(422, "audio_missing", f"音频文件不存在: {audio_path}")
        cmd = [ffmpeg_exe(), "-hide_banner", "-i", str(path)]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AppError(504, "ffmpeg_timeout", "音频时长探测超时") from exc
        except Exception as exc:  # noqa: BLE001 - 统一转业务错误
            raise AppError(500, "ffmpeg_failed", f"音频时长探测失败：{exc}") from exc
        match = _DURATION_RE.search(proc.stderr or "")
        if not match:
            raise AppError(500, "audio_duration_unknown", "无法获取音频真实时长")
        hours, minutes, seconds = match.groups()
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)

    # ---------- Alignment 提取 ----------

    def build_alignment(self, result: GenerationResult) -> AlignmentResult | None:
        """从 TTS 结果提取 provider / forced_alignment alignment；无则返回 None。"""
        raw = result.alignment or {}
        source = raw.get("source")
        if source not in ("provider", "forced_alignment"):
            return None

        return AlignmentResult(
            source=source,
            duration=raw.get("duration"),
            characters=self._normalize_chars(raw),
            words=self._normalize_words(raw),
            phonemes=[],  # 预留，第一阶段不实现
            confidence=raw.get("confidence"),
            raw=raw,
        )

    @staticmethod
    def _normalize_chars(raw: dict) -> list[AlignmentChar]:
        """支持对象列表与 ElevenLabs 并行数组两种形态。"""
        chars = raw.get("characters") or []
        starts = raw.get("character_start_times_seconds") or []
        ends = raw.get("character_end_times_seconds") or []
        if not chars:
            return []
        items: list[AlignmentChar] = []
        if isinstance(chars[0], dict):
            for item in chars:
                items.append(
                    AlignmentChar(
                        char=str(item.get("char", "")),
                        start_time=float(item.get("start_time") or 0),
                        end_time=float(item.get("end_time") or 0),
                    )
                )
        else:
            for index, char in enumerate(chars):
                items.append(
                    AlignmentChar(
                        char=str(char),
                        start_time=(
                            float(starts[index]) if index < len(starts) else 0.0
                        ),
                        end_time=(
                            float(ends[index]) if index < len(ends) else 0.0
                        ),
                    )
                )
        return items

    @staticmethod
    def _normalize_words(raw: dict) -> list[AlignmentWord]:
        """支持对象列表与 ElevenLabs 并行数组两种形态。"""
        words = raw.get("words") or []
        starts = raw.get("word_start_times_seconds") or []
        ends = raw.get("word_end_times_seconds") or []
        if not words:
            return []
        items: list[AlignmentWord] = []
        if isinstance(words[0], dict):
            for item in words:
                items.append(
                    AlignmentWord(
                        word=str(item.get("word", "")),
                        start_time=float(item.get("start_time") or 0),
                        end_time=float(item.get("end_time") or 0),
                    )
                )
        else:
            for index, word in enumerate(words):
                items.append(
                    AlignmentWord(
                        word=str(word),
                        start_time=(
                            float(starts[index]) if index < len(starts) else 0.0
                        ),
                        end_time=(
                            float(ends[index]) if index < len(ends) else 0.0
                        ),
                    )
                )
        return items

    # ---------- Forced Alignment（预留） ----------

    def forced_alignment(
        self, audio_path: str, text: str
    ) -> AlignmentResult | None:
        """对最终音频执行 Forced Alignment（预留）。

        当前未接入 ElevenLabs / WhisperX / MFA，返回 None；
        调用方将回退到真实 duration，而不是伪造时间戳。
        """
        del audio_path, text  # 预留接口，暂不使用
        return None

    # ---------- Dialogue Timeline ----------

    def build_dialogue_clips(
        self,
        project_id: str,
        items: list[dict],
        *,
        shot_id: str = "",
        version: int = 1,
        start_offset: float = 0.0,
    ) -> list[DialogueClip]:
        """把逐句 TTS 结果转换为真实 DialogueClip 列表。

        items 每项：
        - path: 落盘音频路径
        - character / speaker_id / voice_profile_id: 角色与音色信息
        - result: TTS GenerationResult（含可选 alignment）

        每句真实时长由 FFmpeg 探测，offset 逐句累计；
        alignment 有 provider 数据则用 provider，否则 audio_duration_only。
        """
        clips: list[DialogueClip] = []
        offset = start_offset
        for item in items:
            audio_path = str(item["path"])
            duration = self.probe_audio_duration(audio_path)
            result = item.get("result")
            alignment = self.build_alignment(result) if result else None
            if alignment is None:
                alignment = AlignmentResult(
                    source="audio_duration_only",
                    duration=duration,
                )

            clips.append(
                DialogueClip(
                    id=f"clip_{uuid.uuid4().hex[:12]}",
                    project_id=project_id,
                    start_time=offset,
                    end_time=offset + duration,
                    audio_asset_id=item.get("audio_asset_id", ""),
                    alignment=alignment,
                    speaker_id=item.get("speaker_id", ""),
                    voice_profile_id=item.get("voice_profile_id", ""),
                    shot_id=shot_id,
                    version=version,
                )
            )
            offset += duration
        return clips

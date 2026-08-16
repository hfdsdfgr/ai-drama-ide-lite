"""Phase 14 M2 — 配音音视频合成（FFmpeg）。"""

import subprocess
from pathlib import Path

import imageio_ffmpeg

from app.core.errors import AppError


def ffmpeg_exe() -> str:
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001 - 依赖缺失属于环境错误
        raise AppError(500, "ffmpeg_unavailable", "FFmpeg 不可用，无法合成配音") from exc


def mix_audio_video(
    video_path: str,
    voice_paths: list[str],
    output_path: str,
    bgm_path: str | None = None,
) -> str:
    """把视频（可能自带音效）与对白、BGM 统一混音为一个有声视频文件。"""
    video = Path(video_path)
    output = Path(output_path)
    voices = [Path(p) for p in voice_paths if p]
    if not video.is_file():
        raise AppError(422, "video_missing", "待配音的视频文件不存在")
    for voice in voices:
        if not voice.is_file():
            raise AppError(422, "voice_missing", f"对白音频不存在: {voice}")

    output.parent.mkdir(parents=True, exist_ok=True)
    has_video_audio = _has_audio(video)
    if not has_video_audio and not voices and not bgm_path:
        raise AppError(422, "audio_missing", "没有可合成的对白、音效或背景音乐")

    cmd = [ffmpeg_exe(), "-y", "-i", str(video)]
    for voice in voices:
        cmd += ["-i", str(voice)]
    bgm_index = None
    if bgm_path:
        cmd += ["-i", str(bgm_path)]
        bgm_index = len(voices) + 1

    filters: list[str] = []
    audio_inputs: list[str] = []
    if has_video_audio:
        audio_inputs.append("0:a")
    if voices:
        if len(voices) == 1:
            audio_inputs.append("1:a")
        else:
            concat_inputs = "".join(f"[{i}:a]" for i in range(1, len(voices) + 1))
            filters.append(f"{concat_inputs}concat=n={len(voices)}:v=0:a=1[vo]")
            audio_inputs.append("[vo]")
    if bgm_index is not None:
        audio_inputs.append(f"{bgm_index}:a")

    if len(audio_inputs) == 1:
        audio_label = audio_inputs[0]
    else:
        amix_inputs = "".join(f"[{label}]" for label in audio_inputs)
        filters.append(
            f"{amix_inputs}amix=inputs={len(audio_inputs)}:duration=longest:dropout_transition=2:normalize=0[aout]"
        )
        audio_label = "[aout]"

    cmd += ["-map", "0:v"]
    cmd += ["-map", audio_label]
    if filters:
        cmd += ["-filter_complex", ";".join(filters)]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-shortest", str(output)]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError(504, "ffmpeg_timeout", "音视频合成超时，请重试") from exc
    except Exception as exc:  # noqa: BLE001 - 统一转业务错误
        raise AppError(500, "ffmpeg_failed", f"音视频合成失败：{exc}") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()[-1:] or ["未知错误"]
        raise AppError(500, "ffmpeg_failed", f"音视频合成失败：{detail[0][:300]}")
    if not output.is_file():
        raise AppError(500, "ffmpeg_failed", "音视频合成未生成输出文件")
    return str(output)


def _has_audio(video: Path) -> bool:
    try:
        proc = subprocess.run(
            [ffmpeg_exe(), "-hide_banner", "-i", str(video)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:  # noqa: BLE001 - 探测失败按无声处理
        return False
    return "Audio:" in (proc.stderr or "")

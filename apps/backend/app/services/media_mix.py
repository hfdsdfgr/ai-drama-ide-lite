"""Phase 14 M2 — 配音音视频合成（FFmpeg）。"""

import re
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg

from app.core.errors import AppError


def ffmpeg_exe() -> str:
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001 - 依赖缺失属于环境错误
        raise AppError(500, "ffmpeg_unavailable", "FFmpeg 不可用，无法合成配音") from exc


def mix_audio_to_master(
    video_path: str,
    voice_paths: list[str],
    output_audio_path: str,
    bgm_path: str | None = None,
) -> str:
    """把视频原音轨、对白、BGM 混成一条独立音频母带。"""
    video = Path(video_path)
    output = Path(output_audio_path)
    voices = [Path(p) for p in voice_paths if p]
    if not video.is_file():
        raise AppError(422, "video_missing", "待混音的视频文件不存在")
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

    cmd += ["-map", audio_label]
    if filters:
        cmd += ["-filter_complex", ";".join(filters)]
    cmd += ["-c:a", "pcm_s16le", "-vn", str(output)]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError(504, "ffmpeg_timeout", "音频混音超时，请重试") from exc
    except Exception as exc:  # noqa: BLE001 - 统一转业务错误
        raise AppError(500, "ffmpeg_failed", f"音频混音失败：{exc}") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()[-1:] or ["未知错误"]
        raise AppError(500, "ffmpeg_failed", f"音频混音失败：{detail[0][:300]}")
    if not output.is_file():
        raise AppError(500, "ffmpeg_failed", "音频混音未生成输出文件")
    return str(output)


def compose_video_with_audio(
    video_path: str,
    audio_path: str,
    output_path: str,
) -> str:
    """把无声视频和音频母带封装成最终有声视频。"""
    video = Path(video_path)
    audio = Path(audio_path)
    output = Path(output_path)
    if not video.is_file():
        raise AppError(422, "video_missing", "待合成的视频文件不存在")
    if not audio.is_file():
        raise AppError(422, "audio_missing", "待合成的音频母带不存在")

    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_exe(),
        "-y",
        "-i",
        str(video),
        "-i",
        str(audio),
        "-map",
        "0:v",
        "-map",
        "1:a",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError(504, "ffmpeg_timeout", "视频合成超时，请重试") from exc
    except Exception as exc:  # noqa: BLE001 - 统一转业务错误
        raise AppError(500, "ffmpeg_failed", f"视频合成失败：{exc}") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()[-1:] or ["未知错误"]
        raise AppError(500, "ffmpeg_failed", f"视频合成失败：{detail[0][:300]}")
    if not output.is_file():
        raise AppError(500, "ffmpeg_failed", "视频合成未生成输出文件")
    return str(output)


def _probe_video(path: Path) -> dict:
    """读取视频分辨率 / 帧率 / 时长 / 是否含音轨（供拼接归一化使用）。"""
    try:
        proc = subprocess.run(
            [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - 统一转为业务错误
        raise AppError(500, "ffmpeg_probe_failed", f"无法读取视频信息：{path.name}") from exc
    info = proc.stderr or ""

    duration = 0.0
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", info)
    if match:
        hours, minutes, seconds = (
            int(match.group(1)),
            int(match.group(2)),
            float(match.group(3)),
        )
        duration = hours * 3600 + minutes * 60 + seconds

    width = height = 0
    match = re.search(r"(\d{2,5})x(\d{2,5})", info)
    if match:
        width, height = int(match.group(1)), int(match.group(2))

    fps = 30.0
    match = re.search(r"(\d+(?:\.\d+)?) fps", info)
    if match:
        fps = float(match.group(1))

    return {
        "duration": duration,
        "width": width or 1280,
        "height": height or 720,
        "fps": fps,
        "has_audio": "Audio:" in info,
    }


def concat_videos(video_paths: list[str], output_path: str) -> str:
    """按顺序拼接多个分镜视频为单个成片。
    统一分辨率 / 帧率 / 像素格式（以第一个视频为准），有音轨的分镜保留声音，
    无音轨的分镜自动补静音轨，保证拼接结果总时长 = 各分镜时长之和。
    """
    paths = [Path(p) for p in video_paths if p]
    if not paths:
        raise AppError(422, "video_missing", "没有可拼接的视频")
    for path in paths:
        if not path.is_file():
            raise AppError(422, "video_missing", f"待拼接的视频不存在：{path.name}")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    probes = [_probe_video(path) for path in paths]
    base = probes[0]
    width, height, fps = base["width"], base["height"], base["fps"]
    any_audio = any(probe["has_audio"] for probe in probes)

    cmd = [ffmpeg_exe(), "-y"]
    for path in paths:
        cmd += ["-i", str(path)]
    # 无音轨的视频补一条静音输入（在 filter 内按对应视频时长截断）
    silent_start = len(paths)
    for index, probe in enumerate(probes):
        if any_audio and not probe["has_audio"]:
            cmd += [
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=44100",
            ]
            silent_start += 0  # 输入索引 = len(paths) + 已添加的静音数

    filters: list[str] = []
    vlabels: list[str] = []
    alabels: list[str] = []
    silent_inputs = 0
    for index, probe in enumerate(probes):
        filters.append(
            f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p[v{index}]"
        )
        vlabels.append(f"[v{index}]")
        if any_audio:
            if probe["has_audio"]:
                filters.append(
                    f"[{index}:a]aresample=44100,aformat=channel_layouts=stereo[a{index}]"
                )
                alabels.append(f"[a{index}]")
            else:
                src_index = len(paths) + silent_inputs
                silent_inputs += 1
                duration = probe["duration"] or 1.0
                filters.append(
                    f"[{src_index}:a]atrim=0:{duration},asetpts=PTS-STARTPTS,"
                    f"aformat=channel_layouts=stereo:sample_rates=44100[a{index}]"
                )
                alabels.append(f"[a{index}]")

    concat_inputs = ""
    for index in range(len(paths)):
        concat_inputs += vlabels[index]
        if any_audio:
            concat_inputs += alabels[index]
    filters.append(
        f"{concat_inputs}concat=n={len(paths)}:v=1:a={1 if any_audio else 0}[vout]"
    )

    cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]"]
    if any_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-movflags",
        "+faststart",
        str(output),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AppError(504, "ffmpeg_timeout", "视频拼接超时，请重试") from exc
    except Exception as exc:  # noqa: BLE001 - 统一转为业务错误
        raise AppError(500, "ffmpeg_failed", f"视频拼接失败：{exc}") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()[-1:] or ["未知错误"]
        raise AppError(500, "ffmpeg_failed", f"视频拼接失败：{detail[0][:300]}")
    if not output.is_file():
        raise AppError(500, "ffmpeg_failed", "视频拼接未生成输出文件")
    return str(output)


def mix_audio_video(
    video_path: str,
    voice_paths: list[str],
    output_path: str,
    bgm_path: str | None = None,
) -> str:
    """兼容旧调用：先混音成母带，再封装成有声视频。"""
    with tempfile.TemporaryDirectory() as tmp:
        master = Path(tmp) / "master.wav"
        mix_audio_to_master(video_path, voice_paths, str(master), bgm_path=bgm_path)
        return compose_video_with_audio(video_path, str(master), output_path)


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

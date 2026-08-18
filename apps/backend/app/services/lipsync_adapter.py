"""Phase 14 M3 - Lip Sync adapter interface.

Lip Sync 是独立 Job：输入 Video + Final Audio，输出 Synced Video。
它不读台词、不调 TTS、不估算时长，只消费视频与最终音频。

当前默认 PassThrough（仅封装音频，不做嘴型替换），用于验证流程；
后续按部署环境接入真实实现：
- LatentSyncAdapter：本地推理（Apache 2.0，1.5 约 8GB VRAM）；
- SyncSoAdapter：商业 API（异步 polling，多角色 / 侧脸 / 最高 4K）；
- 预留 Hedra / MuseTalk / VideoReTalking。
"""

from abc import ABC, abstractmethod
from pathlib import Path

from app.core.errors import AppError
from app.services.media_mix import compose_video_with_audio


class LipSyncAdapter(ABC):
    """Lip Sync 适配器接口：Video + Audio -> Synced Video。"""

    name: str = "base"

    @abstractmethod
    def sync(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> str:
        """生成同步视频并返回输出路径。"""


class PassThroughLipSyncAdapter(LipSyncAdapter):
    """占位实现：把最终音频封装进视频（不替换嘴型）。

    用于在未部署本地模型 / 未接入付费 API 时保持流程可运行。
    完成标准中的真实嘴型替换由后续 LatentSync / Sync.so 实现补齐。
    """

    name = "pass_through"

    def sync(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> str:
        video = Path(video_path)
        audio = Path(audio_path)
        if not video.is_file():
            raise AppError(422, "video_missing", "待 Lip Sync 的视频文件不存在")
        if not audio.is_file():
            raise AppError(422, "audio_missing", "待 Lip Sync 的音频文件不存在")
        return compose_video_with_audio(video_path, audio_path, output_path)

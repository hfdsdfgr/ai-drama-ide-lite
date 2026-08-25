"""Phase 10 — 持久化 Job Worker（单 worker 顺序执行）。

职责：
1. 从 JobStore 领取 queued 任务（条件 UPDATE，防止并发重复领取），单 worker 顺序执行，
   不并行处理同一个任务（产品约束：单模型生成）。
2. 执行 generation 任务：同步厂商直接生成；异步厂商 submit → 记录 task_id → 轮询。
3. 失败分类：retryable（超时 / 5xx / 429 / 网络）与 permanent（无效 Key / 不支持能力 /
   非法请求）分开记录，供任务中心展示与手动重试决策。
4. 默认不自动重试（max_attempts=1），避免重复提交产生费用；重试由用户手动触发（M3 API）。
5. 启动时恢复崩溃残留任务（recover_stale）。

进度只来自厂商真实返回；厂商不提供进度时保持 0，UI 显示「处理中」，不做假进度。
"""

import threading
from pathlib import Path

from app.core.errors import AppError
from app.core.logging import get_logger
from app.services.adapters.base import GenerationRequest, GenerationResult
from app.services.adapters.manager import ProviderManager
from app.services.asset_service import run_asset_completion
from app.services.capability_registry import IMAGE_CAPABILITIES, VIDEO_CAPABILITIES
from app.services.job_store import (
    CATEGORY_PERMANENT,
    CATEGORY_RETRYABLE,
    JOB_TYPE_ASSET_COMPLETION,
    JOB_TYPE_GENERATION,
    JOB_TYPE_LIP_SYNC,
    JOB_TYPE_VIDEO_COMPOSE,
    JOB_TYPE_DIALOGUE_REVIEW,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PAUSED,
    STATUS_QUEUED,
    JobStore,
)

logger = get_logger("job_worker")


def classify_error(exc: BaseException) -> str:
    """失败分类：临时网络/超时/5xx/429 可重试；无效 Key/不支持能力等永久失败。"""
    if isinstance(exc, AppError):
        if exc.status_code >= 500 or exc.status_code in (408, 429):
            return CATEGORY_RETRYABLE
        return CATEGORY_PERMANENT
    return CATEGORY_RETRYABLE


def _error_message(exc: BaseException) -> str:
    if isinstance(exc, AppError):
        return exc.message
    return str(exc) or exc.__class__.__name__


class JobWorker:
    def __init__(
        self,
        store: JobStore,
        manager: ProviderManager,
        output_dir: Path,
        *,
        scan_interval: float = 2.0,
        poll_interval: float = 3.0,
        image_result_service=None,
        audio_dubbing_service=None,
        lip_sync_service=None,
        video_sequence_service=None,
        dialogue_review_service=None,
    ) -> None:
        self.store = store
        self.manager = manager
        self.output_dir = Path(output_dir)
        self.scan_interval = scan_interval
        self.poll_interval = poll_interval
        self.image_result_service = image_result_service
        self.audio_dubbing_service = audio_dubbing_service
        self.lip_sync_service = lip_sync_service
        self.video_sequence_service = video_sequence_service
        self.dialogue_review_service = dialogue_review_service
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """启动 worker 线程；先恢复崩溃残留任务，再进入调度循环。"""
        if self._thread and self._thread.is_alive():
            return
        recovered = self.store.recover_stale()
        if recovered:
            logger.info("Recovered %d stale job(s) to queued", recovered)
        self._thread = threading.Thread(
            target=self._run, name="job-worker", daemon=True
        )
        self._thread.start()
        logger.info("Job worker started (scan=%ss, poll=%ss)", self.scan_interval, self.poll_interval)

    def stop(self) -> None:
        self._stop.set()

    @property
    def is_alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._drain()
            except Exception:  # noqa: BLE001 —— worker 边界，循环不能因单次异常退出
                logger.exception("Job worker drain failed")
            self._stop.wait(self.scan_interval)
        logger.info("Job worker stopped")

    def _drain(self) -> None:
        """领取并顺序执行 queued 任务（单 worker）。"""
        for job in self.store.list_jobs(status=STATUS_QUEUED, limit=20):
            if self._stop.is_set():
                break
            self._execute(job)

    def _execute(self, job) -> None:
        """领取一个任务并执行；返回前必须落到终态（或保持 cancelled/paused）。"""
        if not self.store.mark_running(job.id):
            return  # 已被取消 / 其他 worker 领取
        job = self.store.get(job.id)
        try:
            if job.type == JOB_TYPE_GENERATION:
                self._run_generation(job)
            elif job.type == JOB_TYPE_ASSET_COMPLETION:
                self._run_asset_completion(job)
            elif job.type == "dubbing":
                self._run_dubbing(job)
            elif job.type == JOB_TYPE_LIP_SYNC:
                self._run_lip_sync(job)
            elif job.type == JOB_TYPE_VIDEO_COMPOSE:
                self._run_video_compose(job)
            elif job.type == JOB_TYPE_DIALOGUE_REVIEW:
                self._run_dialogue_review(job)
            else:
                self.store.mark_failed(
                    job.id, f"未知任务类型: {job.type}", CATEGORY_PERMANENT
                )
        except Exception as exc:  # noqa: BLE001 —— 必须兜住并落到 failed
            category = classify_error(exc)
            self.store.mark_failed(job.id, _error_message(exc), category)
            logger.warning(
                "Job %s failed (%s): %s", job.id, category, _error_message(exc)
            )

    # ---------- 任务执行器 ----------

    def _run_generation(self, job) -> None:
        payload = job.input_payload or {}
        request_extra = dict(payload.get("extra") or {})
        request_extra["output_dir"] = str(self.output_dir)
        request = GenerationRequest(
            capability=job.capability,
            prompt=payload.get("prompt", ""),
            model_id=job.model_id,
            images=payload.get("images") or [],
            aspect_ratio=payload.get("aspect_ratio"),
            duration=payload.get("duration"),
            negative_prompt=payload.get("negative_prompt", ""),
            extra=request_extra,
        )
        started = self.manager.start_job(job.model_id, job.capability, request)
        if started["mode"] == "sync":
            self._finish_sync(job, started["result"])
            return
        task_id = started.get("task_id")
        if not task_id:
            self.store.mark_failed(
                job.id, "厂商未返回任务 ID", CATEGORY_PERMANENT
            )
            return
        self.store.set_task_id(job.id, task_id)
        self._poll_until_done(job.id)

    def _run_asset_completion(self, job) -> None:
        """资产卡补全：LLM 字段级补全（只补空不覆盖），结果写回 Story Bible。"""
        detail = run_asset_completion(
            self.store.db_path,
            self.manager,
            job.project_id,
            job.model_id,
        )
        self.store.mark_completed(
            job.id, result_payload={"detail": detail}
        )

    def _run_dubbing(self, job) -> None:
        """配音任务：台词归属 + 逐角色 TTS + FFmpeg 合成 + 写有声版本。"""
        if self.audio_dubbing_service is None:
            self.store.mark_failed(
                job.id, "配音服务未初始化", CATEGORY_PERMANENT
            )
            return
        result = self.audio_dubbing_service.run(job, self.store)
        self.store.mark_completed(job.id, result_payload=result)

    def _run_lip_sync(self, job) -> None:
        """Lip Sync：Video + Final Audio -> Synced Video（独立 Job）。"""
        if self.lip_sync_service is None:
            self.store.mark_failed(
                job.id, "Lip Sync 服务未初始化", CATEGORY_PERMANENT
            )
            return
        result = self.lip_sync_service.run(job, self.store)
        self.store.mark_completed(job.id, result_payload=result)

    def _run_video_compose(self, job) -> None:
        """多分镜合成：本地 FFmpeg 拼接，不调用外部 API。"""
        if self.video_sequence_service is None:
            self.store.mark_failed(
                job.id, "视频合成服务未初始化", CATEGORY_PERMANENT
            )
            return
        result = self.video_sequence_service.run(job, self.store)
        self.store.mark_completed(job.id, result_payload=result)

    def _run_dialogue_review(self, job) -> None:
        """台词审核：提取音轨 → 语音转写 → LLM 比对 → 写审核记录。"""
        if self.dialogue_review_service is None:
            self.store.mark_failed(
                job.id, "台词审核服务未初始化", CATEGORY_PERMANENT
            )
            return
        result = self.dialogue_review_service.run_model_review(job, self.store)
        self.store.mark_completed(job.id, result_payload=result)

    def _finish_sync(self, job, result) -> None:
        self._persist_image_result(job, result)
        self.store.mark_completed(
            job.id,
            result_payload=self._result_payload(result),
            output_files=self._local_files(result),
        )

    def _poll_until_done(self, job_id: str) -> None:
        """异步厂商任务轮询：检查本地状态（cancel/pause）与厂商真实状态。"""
        while not self._stop.is_set():
            current = self.store.get(job_id)
            if current.status in (STATUS_CANCELLED, STATUS_PAUSED):
                return  # 已取消或暂停：worker 停止轮询，任务保持该状态
            job = self.store.get(job_id)
            try:
                adapter = self.manager.adapter_for(job.model_id, job.capability)
                ctx = self.manager.ctx_for(job.model_id)
                status = adapter.poll(ctx, job.task_id)
            except Exception as exc:  # noqa: BLE001 —— 单次轮询失败按任务失败处理
                self.store.mark_failed(
                    job_id, _error_message(exc), classify_error(exc)
                )
                return

            if status.status == STATUS_COMPLETED:
                if status.result:
                    self._persist_image_result(job, status.result)
                    self.store.mark_completed(
                        job_id,
                        result_payload=self._result_payload(status.result),
                        output_files=self._local_files(status.result),
                    )
                else:
                    self.store.mark_failed(
                        job_id, "厂商返回完成但没有结果", CATEGORY_RETRYABLE
                    )
                return
            if status.status == STATUS_FAILED:
                self.store.mark_failed(
                    job_id,
                    status.error or "厂商任务失败",
                    CATEGORY_RETRYABLE,
                )
                return
            # 仍处理中：厂商给出真实进度才更新，否则保持原值（不做假进度）
            if status.progress is not None:
                self.store.update_progress(job_id, int(status.progress * 100))
            self._stop.wait(self.poll_interval)

    # ---------- 结果处理 ----------

    def _persist_image_result(self, job, result) -> None:
        if self.image_result_service is None:
            return
        if job.type != JOB_TYPE_GENERATION:
            return
        if job.capability not in (IMAGE_CAPABILITIES | VIDEO_CAPABILITIES):
            return
        if not isinstance(result, GenerationResult):
            return
        self.image_result_service.persist(job, result)

    @staticmethod
    def _result_payload(result) -> dict:
        if isinstance(result, GenerationResult):
            return {"urls": list(result.urls), "meta": dict(result.meta or {})}
        if isinstance(result, dict):
            return result
        return {}

    def _local_files(self, result) -> list[str]:
        if not isinstance(result, GenerationResult):
            return []
        return [
            url
            for url in result.urls
            if Path(url).is_absolute() and self.output_dir in Path(url).parents
        ]

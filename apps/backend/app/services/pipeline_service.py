"""Phase 20 一键生产编排器：按阶段序列执行项目生产流程。

阶段：小说分析（含 Story Bible 与角色/场景/道具提取）→ 剧本 → 资产卡补全
→ 分镜 → 分镜图 →（可选）图生视频。

特性：
- 开始前检查每阶段所需模型，缺失时给出明确提示；
- 已完成的阶段自动跳过（幂等）；
- 默认每阶段完成后暂停，等用户确认后继续（可开自动继续）；
- 复用现有 Job 系统，可暂停 / 恢复 / 取消 / 重试。
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.core.errors import AppError
from app.db.database import get_connection
from app.schemas.script import SceneCreate, ShotCreate
from app.services.job_store import JOB_TYPE_PIPELINE
from app.services.novel_repo import NovelRepository
from app.services.script_repo import ScriptRepository

PIPELINE_STAGES: tuple[dict, ...] = (
    {"key": "novel_analysis", "label": "小说分析 / Story Bible", "kind": "llm"},
    {"key": "script", "label": "剧本生成（分集 / 场景）", "kind": "llm"},
    {"key": "assets", "label": "资产卡补全", "kind": "llm"},
    {"key": "storyboard", "label": "分镜生成", "kind": "llm"},
    {"key": "shot_images", "label": "分镜图生成", "kind": "image"},
    {"key": "videos", "label": "图生视频", "kind": "video"},
    {"key": "quality_review", "label": "质量审查（视觉/剧情/台词）", "kind": "review"},
)

_MISSING_REASON = {
    "llm": "未配置可用的文本模型，请到「设置」添加并启用（需有效 API Key）",
    "image": "未配置可用的图片模型（文生图），请到「设置」添加并启用",
    "video": "未配置可用的视频模型（图生视频），请到「设置」添加并启用",
    "review": "质量审查需要视觉模型与文本模型，请到「设置」添加并启用",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PipelineService:
    def __init__(
        self,
        db_path,
        manager,
        *,
        story_service,
        ai_script_service,
        asset_service,
        image_generation_service,
        video_generation_service,
        asset_version_service,
        visual_review_service=None,
        story_consistency_service=None,
        dialogue_review_service=None,
    ) -> None:
        self.db_path = Path(db_path)
        self.manager = manager
        self.story_service = story_service
        self.ai_script_service = ai_script_service
        self.asset_service = asset_service
        self.image_generation_service = image_generation_service
        self.video_generation_service = video_generation_service
        self.versions = asset_version_service
        self.visual_review_service = visual_review_service
        self.story_consistency_service = story_consistency_service
        self.dialogue_review_service = dialogue_review_service

    # ---------- 计划与模型检查 ----------

    def plan(self, project_id: str) -> dict:
        stages = []
        for stage in PIPELINE_STAGES:
            completed = self._stage_completed(project_id, stage["key"])
            if completed:
                item = {**stage, "status": "completed", "model_id": "", "missing_reason": ""}
            else:
                model = self._pick_stage_model(stage)
                if model is None:
                    item = {
                        **stage,
                        "status": "not_ready",
                        "model_id": "",
                        "missing_reason": _MISSING_REASON.get(stage["kind"], "缺少所需模型"),
                    }
                else:
                    item = {
                        **stage,
                        "status": "ready",
                        "model_id": model.model_id,
                        "missing_reason": "",
                    }
            stages.append(item)
        can_start = any(s["status"] == "ready" for s in stages) and not all(
            s["status"] == "completed" for s in stages
        )
        return {"project_id": project_id, "stages": stages, "can_start": can_start}

    def start(
        self,
        store,
        project_id: str,
        *,
        auto_continue: bool = False,
        include_videos: bool = False,
        quality_review: bool = False,
    ):
        plan = self.plan(project_id)
        if not plan["can_start"]:
            reason = next(
                (s["missing_reason"] for s in plan["stages"] if s["status"] == "not_ready"),
                "所有阶段均已完成或无可执行阶段",
            )
            raise AppError(422, "pipeline_not_startable", f"无法开始：{reason}")
        stages = [
            s
            for s in PIPELINE_STAGES
            if (include_videos or s["key"] != "videos")
            and (quality_review or s["key"] != "quality_review")
        ]
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute("DELETE FROM pipelines WHERE project_id = ?", (project_id,))
            for stage in stages:
                conn.execute(
                    """
                    INSERT INTO pipelines (project_id, stage_key, status, message, updated_at)
                    VALUES (?, ?, 'queued', '', ?)
                    """,
                    (project_id, stage["key"], now),
                )
        return store.create(
            JOB_TYPE_PIPELINE,
            project_id,
            model_id="",
            provider_id="",
            capability="pipeline",
            input_payload={
                "project_id": project_id,
                "auto_continue": bool(auto_continue),
                "include_videos": bool(include_videos),
                "quality_review": bool(quality_review),
            },
        )

    def status(self, project_id: str) -> dict:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM pipelines WHERE project_id = ? ORDER BY rowid",
                (project_id,),
            ).fetchall()
        stages = [dict(row) for row in rows]
        return {"project_id": project_id, "stages": stages}

    def run(self, job, store) -> bool:
        """顺序执行阶段；返回 True=全部完成，False=阶段完成后已暂停等确认。"""
        payload = job.input_payload or {}
        project_id = payload.get("project_id") or job.project_id
        auto_continue = bool(payload.get("auto_continue"))
        include_videos = bool(payload.get("include_videos"))
        quality_review = bool(payload.get("quality_review"))
        stages = [
            s
            for s in PIPELINE_STAGES
            if (include_videos or s["key"] != "videos")
            and (quality_review or s["key"] != "quality_review")
        ]
        for index, stage in enumerate(stages):
            if self._get_stage_status(project_id, stage["key"]) == "completed":
                continue
            model = self._pick_stage_model(stage)
            if model is None:
                reason = _MISSING_REASON.get(stage["kind"], "缺少所需模型")
                self._set_stage(project_id, stage["key"], "failed", reason)
                raise AppError(422, "stage_model_missing", f"阶段「{stage['label']}」{reason}")
            self._set_stage(project_id, stage["key"], "running", "")
            try:
                self._execute_stage(
                    project_id, stage, model, store, include_videos=include_videos
                )
            except Exception as exc:
                self._set_stage(project_id, stage["key"], "failed", str(exc))
                raise
            self._set_stage(project_id, stage["key"], "completed", "")
            if not auto_continue and index < len(stages) - 1:
                store.pause(job.id)
                return False
        return True

    # ---------- 阶段执行 ----------

    def _execute_stage(
        self,
        project_id: str,
        stage: dict,
        model,
        store,
        *,
        include_videos: bool = False,
    ) -> None:
        key = stage["key"]
        if key == "novel_analysis":
            self._run_novel_analysis(project_id, model)
        elif key == "script":
            self._run_script(project_id, model)
        elif key == "assets":
            self._run_assets(project_id, model, store)
        elif key == "storyboard":
            self._run_storyboard(project_id, model)
        elif key == "shot_images":
            self._run_shot_images(project_id, model, store)
        elif key == "videos":
            self._run_videos(project_id, model, store)
        elif key == "quality_review":
            self._run_quality_review(project_id, store, include_videos=include_videos)

    def _run_novel_analysis(self, project_id: str, model) -> None:
        novels = NovelRepository(self.db_path).list_novels(project_id)
        if not novels:
            raise AppError(422, "pipeline_no_novel", "项目里还没有小说，请先导入")
        job = self.story_service.start(project_id, novels[0].id, model.id)
        while True:
            current = self.story_service.get(job["job_id"])
            if current["status"] == "completed":
                return
            if current["status"] == "failed":
                raise AppError(500, "stage_failed", current.get("error") or "小说分析失败")
            time.sleep(2)

    def _run_script(self, project_id: str, model) -> None:
        novels = NovelRepository(self.db_path).list_novels(project_id)
        if not novels:
            raise AppError(422, "pipeline_no_novel", "项目里还没有小说，请先导入")
        result = self.ai_script_service.generate_episode_script(
            project_id, novels[0].id, model.id
        )
        ScriptRepository(self.db_path).save_episode_script(
            project_id=project_id,
            novel_id=novels[0].id,
            source_chapter_index=0,
            episode_title=result.episode.title,
            episode_summary=result.episode.summary,
            scenes=[SceneCreate(**scene.model_dump()) for scene in result.scenes],
        )

    def _run_assets(self, project_id: str, model, store) -> None:
        job = self.asset_service.start(project_id, model.id)
        self._poll_job(store, job["job_id"])

    def _run_storyboard(self, project_id: str, model) -> None:
        repo = ScriptRepository(self.db_path)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id FROM scenes WHERE project_id = ? AND deleted_at IS NULL ORDER BY order_index",
                (project_id,),
            ).fetchall()
        for row in rows:
            scene_id = row["id"]
            if self._scene_has_shots(scene_id):
                continue
            result = self.ai_script_service.generate_shots(
                project_id, scene_id, model.id
            )
            repo.save_scene_shots(
                project_id,
                scene_id,
                [ShotCreate(**shot.model_dump()) for shot in result.shots],
            )

    def _run_shot_images(self, project_id: str, model, store) -> None:
        shots = self._shots_without_image(project_id)
        for shot in shots:
            job = self.image_generation_service.start_shot(
                project_id,
                shot,
                model.id,
                capability="text_to_image",
            )
            self._poll_job(store, job["job_id"])

    def _run_videos(self, project_id: str, model, store) -> None:
        shots = self._shots_without_video(project_id)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, prompt, action, duration FROM shots WHERE id IN (%s)"
                % ",".join("?" * len(shots)),
                shots,
            ).fetchall()
        supports_audio = "video_audio" in model.capabilities
        for row in rows:
            prompt = (row["prompt"] or row["action"] or "").strip()
            if not prompt:
                continue
            # 分镜时长由剧本阶段按 5/10/15 档位生成；这里必须使用分镜自身时长，
            # 不能硬编码 5 秒。旧数据可能不是 5 的倍数，归一化到最近的 5 秒档。
            duration = int(row["duration"] or 5)
            if duration <= 5:
                duration = 5
            elif duration > 15:
                duration = 15
            else:
                duration = round(duration / 5) * 5
            job = self.video_generation_service.start_shot_video(
                project_id,
                row["id"],
                model.id,
                prompt,
                duration=duration,
                with_audio=supports_audio,
            )
            self._poll_job(store, job["job_id"])

    def _run_quality_review(
        self, project_id: str, store, *, include_videos: bool = False
    ) -> None:
        """对每个已生成分镜图的镜头做视觉一致性（角色）+ 剧情一致性审核；
        若勾选了视频，再对有视频的镜头补台词审核。"""
        if (
            self.visual_review_service is None
            or self.story_consistency_service is None
            or self.dialogue_review_service is None
        ):
            raise AppError(500, "review_service_missing", "质量审查服务未初始化")
        vision_model = self._pick_vision_model()
        if vision_model is None:
            raise AppError(
                422,
                "review_model_missing",
                "质量审查需要可用的视觉模型（如 qwen-vl / glm-4v / gpt-4o），请先到「设置」启用",
            )
        llm_model = self._pick_stage_model({"kind": "llm"})
        if llm_model is None:
            raise AppError(
                422,
                "review_model_missing",
                "质量审查需要可用的文本模型，请先到「设置」启用",
            )
        asr_model = self._pick_asr_model() if include_videos else None
        if include_videos and asr_model is None:
            raise AppError(
                422,
                "review_model_missing",
                "包含视频的台词审核需要可用的语音转写模型（如 whisper / qwen3-asr），请先到「设置」启用",
            )

        shots = self._shots_with_image(project_id)
        for shot_id in shots:
            review_job = self.visual_review_service.create_model_review_job(
                store,
                project_id,
                shot_id,
                model_id=vision_model.id,
                review_type="character",
            )
            self._poll_job(store, review_job.id)
            story_job = self.story_consistency_service.create_model_review_job(
                store,
                project_id,
                shot_id,
                model_id=llm_model.id,
            )
            self._poll_job(store, story_job.id)
            if include_videos and self._shot_has_video(shot_id):
                dialogue_job = self.dialogue_review_service.create_model_review_job(
                    store,
                    project_id,
                    shot_id,
                    model_id=asr_model.id,
                    script_model_id=llm_model.id,
                )
                self._poll_job(store, dialogue_job.id)

    def _poll_job(self, store, job_id: str) -> None:
        while True:
            record = store.get(job_id)
            if record.status == "completed":
                return
            if record.status in ("failed", "cancelled"):
                raise AppError(
                    500,
                    "stage_job_failed",
                    record.error or f"子任务未完成（{record.status}）",
                )
            time.sleep(2)

    # ---------- 状态与查询 ----------

    def _set_stage(self, project_id: str, stage_key: str, status: str, message: str) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO pipelines (project_id, stage_key, status, message, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id, stage_key)
                DO UPDATE SET status = excluded.status, message = excluded.message,
                              updated_at = excluded.updated_at
                """,
                (project_id, stage_key, status, message, _now_iso()),
            )

    def _get_stage_status(self, project_id: str, stage_key: str) -> str:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT status FROM pipelines WHERE project_id = ? AND stage_key = ?",
                (project_id, stage_key),
            ).fetchone()
        return row["status"] if row else "queued"

    def _stage_completed(self, project_id: str, stage_key: str) -> bool:
        with get_connection(self.db_path) as conn:
            if stage_key == "novel_analysis":
                return self._bible_has_content(conn, project_id)
            if stage_key == "script":
                return self._count(conn, "episodes", project_id) > 0 or self._count(
                    conn, "scenes", project_id
                ) > 0
            if stage_key == "assets":
                return self._count(conn, "assets", project_id) > 0
            if stage_key == "storyboard":
                return self._count(conn, "shots", project_id) > 0
            if stage_key == "shot_images":
                return self._all_shots_have(conn, project_id, "shot")
            if stage_key == "videos":
                return self._all_shots_have(conn, project_id, "shot_video")
            if stage_key == "quality_review":
                row = conn.execute(
                    "SELECT status FROM pipelines WHERE project_id = ? AND stage_key = 'quality_review'",
                    (project_id,),
                ).fetchone()
                return bool(row and row["status"] == "completed")
        return False

    @staticmethod
    def _count(conn, table: str, project_id: str) -> int:
        return int(
            conn.execute(
                f"SELECT COUNT(*) AS c FROM {table} WHERE project_id = ?",
                (project_id,),
            ).fetchone()["c"]
        )

    @staticmethod
    def _bible_has_content(conn, project_id: str) -> bool:
        import json

        row = conn.execute(
            "SELECT content FROM stories WHERE project_id = ? ORDER BY updated_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if row is None:
            return False
        try:
            data = json.loads(row["content"])
        except (ValueError, TypeError):
            return False
        keys = (
            "synopsis",
            "characters",
            "locations",
            "props",
            "events",
            "conflicts",
            "plotlines",
            "foreshadowing",
        )
        return any(bool(data.get(key)) for key in keys)

    def _all_shots_have(self, conn, project_id: str, entity_type: str) -> bool:
        total = self._count(conn, "shots", project_id)
        if total == 0:
            return False
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT v.entity_id) AS c
            FROM versions v
            WHERE v.project_id = ? AND v.entity_type = ? AND v.is_current = 1
              AND v.entity_id IN (SELECT id FROM shots WHERE project_id = ? AND deleted_at IS NULL)
            """,
            (project_id, entity_type, project_id),
        ).fetchone()
        return int(row["c"]) >= total

    def _scene_has_shots(self, scene_id: str) -> bool:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM shots WHERE scene_id = ? AND deleted_at IS NULL",
                (scene_id,),
            ).fetchone()
        return int(row["c"]) > 0

    def _shots_without_image(self, project_id: str) -> list[str]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT s.id FROM shots s
                WHERE s.project_id = ? AND s.deleted_at IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM versions v
                      WHERE v.project_id = s.project_id AND v.entity_type = 'shot'
                        AND v.entity_id = s.id AND v.is_current = 1
                  )
                ORDER BY s.order_index
                """,
                (project_id,),
            ).fetchall()
        return [row["id"] for row in rows]

    def _shots_without_video(self, project_id: str) -> list[str]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT s.id FROM shots s
                WHERE s.project_id = ? AND s.deleted_at IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM versions v
                      WHERE v.project_id = s.project_id AND v.entity_type = 'shot_video'
                        AND v.entity_id = s.id AND v.is_current = 1
                  )
                ORDER BY s.order_index
                """,
                (project_id,),
            ).fetchall()
        return [row["id"] for row in rows]

    def _pick_stage_model(self, stage: dict):
        kind = stage["kind"]
        models = self.manager.repo.list_models(model_type=kind, enabled_only=True)
        if kind == "llm":
            return models[0] if models else None
        if kind == "image":
            for model in models:
                caps = set(model.capabilities)
                if caps & {"text_to_image", "reference_image"}:
                    return model
            return None
        if kind == "video":
            for model in models:
                if "image_to_video" in model.capabilities:
                    return model
            return None
        if kind == "review":
            vision = self._pick_vision_model()
            llm = self._pick_stage_model({"kind": "llm"})
            if vision is None or llm is None:
                return None
            return SimpleNamespace(id="", model_id="视觉模型 + 文本模型")
        return None

    def _pick_vision_model(self):
        models = self.manager.repo.list_models(model_type="llm", enabled_only=True)
        return next((m for m in models if "vision" in m.capabilities), None)

    def _pick_asr_model(self):
        models = self.manager.repo.list_models(model_type="audio", enabled_only=True)
        return next((m for m in models if "speech_to_text" in m.capabilities), None)

    def _shots_with_image(self, project_id: str) -> list[str]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT s.id FROM shots s
                WHERE s.project_id = ? AND s.deleted_at IS NULL
                  AND EXISTS (
                      SELECT 1 FROM versions v
                      WHERE v.project_id = s.project_id AND v.entity_type = 'shot'
                        AND v.entity_id = s.id AND v.is_current = 1
                  )
                ORDER BY s.order_index
                """,
                (project_id,),
            ).fetchall()
        return [row["id"] for row in rows]

    def _shot_has_video(self, shot_id: str) -> bool:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT 1 FROM versions
                WHERE entity_type = 'shot_video' AND entity_id = ? AND is_current = 1
                LIMIT 1
                """,
                (shot_id,),
            ).fetchone()
        return row is not None

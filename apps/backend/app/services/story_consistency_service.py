"""剧情一致性审核服务：检查镜头与前后镜头的剧情衔接是否合理。

模型审核：取目标镜头与同场景前一 / 后一镜头的动作与台词，交给文本 LLM 判断；
人工审核：用户自行判断。
"""

from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection
from app.services.job_store import JOB_TYPE_STORY_REVIEW
from app.services.llm_json import parse_review_result
from app.services.prompt_settings import PromptSettingsService
from app.services.script_repo import ScriptRepository
from app.services.story_consistency_repository import StoryConsistencyRepository


class StoryConsistencyService:
    def __init__(self, db_path, manager) -> None:
        self.db_path = db_path
        self.manager = manager
        self.prompts = PromptSettingsService(db_path)
        self.reviews = StoryConsistencyRepository(db_path)

    def create_model_review_job(
        self,
        store,
        project_id: str,
        shot_id: str,
        *,
        model_id: str,
        prompt_snapshot: dict | None = None,
    ):
        ScriptRepository(self.db_path).get_shot_with_scene(project_id, shot_id)
        self._pick_llm_model(model_id)
        return store.create(
            JOB_TYPE_STORY_REVIEW,
            project_id,
            model_id=model_id,
            provider_id="",
            capability="story_review",
            input_payload={
                "shot_id": shot_id,
                "model_id": model_id,
                "prompt_snapshot": (
                    prompt_snapshot if prompt_snapshot is not None else self.prompts.snapshot(project_id)
                ),
            },
        )

    def run_model_review(self, job, store) -> dict:
        payload = job.input_payload or {}
        project_id = job.project_id
        shot_id = payload.get("shot_id")
        model_id = payload.get("model_id") or job.model_id
        if not shot_id:
            raise AppError(422, "review_invalid_payload", "剧情审核任务参数不合法")
        snapshot = payload.get("prompt_snapshot")
        if snapshot is None:
            snapshot = self.prompts.snapshot(project_id)
        system = self.prompts.system_prompt(project_id, "review_story", snapshot=snapshot)

        shot, scene = ScriptRepository(self.db_path).get_shot_with_scene(
            project_id, shot_id
        )
        context = self._build_context(project_id, shot, scene)
        user = (
            f"场景：{scene.slugline or scene.title}\n\n"
            f"前一镜头：\n{context['prev'] or '（无，本镜头为场景首镜）'}\n\n"
            f"目标镜头：\n{context['current']}\n\n"
            f"后一镜头：\n{context['next'] or '（无，本镜头为场景末镜）'}\n"
        )
        raw = self.manager.chat(
            model_id,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
        )
        try:
            consistent, issue = parse_review_result(raw)
        except (ValueError, TypeError):
            consistent, issue = False, "审核结果解析失败，请人工复核"

        review = self.reviews.create(
            project_id, shot_id, mode="model", model_id=model_id
        )
        self.reviews.update_result(
            review["id"],
            status="passed" if consistent else "flagged",
            issue=issue,
        )
        return {
            "review_id": review["id"],
            "status": "passed" if consistent else "flagged",
            "issue": issue,
        }

    def create_manual_review(
        self,
        project_id: str,
        shot_id: str,
        *,
        consistent: bool,
        issue: str = "",
    ) -> dict:
        ScriptRepository(self.db_path).get_shot_with_scene(project_id, shot_id)
        review = self.reviews.create(project_id, shot_id, mode="manual")
        return self.reviews.update_result(
            review["id"],
            status="passed" if consistent else "flagged",
            issue=issue.strip(),
        )

    def set_decision(
        self,
        project_id: str,
        review_id: str,
        *,
        decision: str,
    ) -> dict:
        review = self.reviews.get(review_id)
        if review["project_id"] != project_id:
            raise AppError(404, "story_review_not_found", "剧情审核记录不存在")
        if decision not in ("regenerate", "delete_shot", "keep"):
            raise AppError(422, "invalid_decision", "审核决策不合法")
        return self.reviews.update_decision(review_id, decision)

    # ---------- 内部 ----------

    def _build_context(self, project_id: str, shot, scene) -> dict:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, action, dialogue FROM shots
                WHERE project_id = ? AND scene_id = ? AND deleted_at IS NULL
                ORDER BY order_index, created_at
                """,
                (project_id, scene.id),
            ).fetchall()
        ordered = [dict(row) for row in rows]
        index = next(
            (i for i, item in enumerate(ordered) if item["id"] == shot.id), -1
        )
        prev = ordered[index - 1] if index > 0 else None
        next_shot = ordered[index + 1] if 0 <= index < len(ordered) - 1 else None
        return {
            "prev": self._format_shot(prev),
            "current": self._format_shot(shot),
            "next": self._format_shot(next_shot),
        }

    @staticmethod
    def _format_shot(shot) -> str:
        if shot is None:
            return ""
        action = (shot.get("action") if isinstance(shot, dict) else shot.action) or ""
        dialogue = (shot.get("dialogue") if isinstance(shot, dict) else shot.dialogue) or ""
        return f"动作：{action}\n台词：{dialogue}".strip()

    def _pick_llm_model(self, model_id: str):
        try:
            model = self.manager.repo.get_model(model_id)
        except AppError as exc:
            raise AppError(422, "model_unavailable", "所选文本模型不可用") from exc
        if model.model_type != "llm" or not model.enabled:
            raise AppError(422, "model_unavailable", "请选择可用的文本模型")
        return model

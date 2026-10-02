"""AI 剧本生成服务（Phase 7 — Script Engine）。

流程：小说章节 → 分集规划 + 场景剧本 →（用户确认）→ 场景拆分为分镜。
LLM 输出一律过 Pydantic 校验 + 一次修复重试；结果只返回预览，由前端确认后落库。
"""

from pathlib import Path

from app.core.errors import AppError
from app.schemas.script import (
    AiEpisodeScriptResult,
    AiShotsResult,
)
from app.services.adapters.manager import ProviderManager
from app.services.llm_json import parse_llm_json
from app.services.novel_repo import NovelRepository
from app.services.prompt_settings import PromptSettingsService
from app.services.script_repo import ScriptRepository
from app.services.story_repo import bible_context_text

SCRIPT_TIMEOUT = 300

_EPISODE_USER = """小说章节：《{chapter_title}》
章节内容：
{chapter_content}
{bible_context}用户要求：{instruction}
请改编为分集剧本。"""

_SHOTS_USER = """场景：《{scene_title}》
{scene_slugline}
动作：{scene_action}
台词：{scene_dialogue}
{bible_context}用户要求：{instruction}
请拆分为分镜镜头。"""


class AiScriptService:
    def __init__(self, manager: ProviderManager, db_path: Path) -> None:
        self.manager = manager
        self.db_path = db_path
        self.prompts = PromptSettingsService(db_path)

    def generate_episode_script(
        self,
        project_id: str,
        novel_id: str,
        model_id: str,
        chapter_index: int | None = None,
        user_instruction: str = "",
        *,
        prompt_snapshot: dict | None = None,
    ) -> AiEpisodeScriptResult:
        """章节 → 分集 + 场景剧本（一次生成，结构化校验）。"""
        snapshot = (
            prompt_snapshot if prompt_snapshot is not None else self.prompts.snapshot(project_id)
        )
        system = self.prompts.system_prompt(project_id, "script_episode", snapshot=snapshot)
        detail = NovelRepository(self.db_path).get(project_id, novel_id)
        if not detail.chapters:
            raise AppError(422, "script_no_chapters", "该小说还没有章节，无法生成剧本")
        index = (
            chapter_index
            if chapter_index is not None
            else min(len(detail.chapters) - 1, 0)
        )
        if index < 0 or index >= len(detail.chapters):
            raise AppError(422, "script_chapter_out_of_range", "章节索引超出范围")
        chapter = detail.chapters[index]
        content = chapter.content[:6000] + (
            "……（内容过长已截断）" if len(chapter.content) > 6000 else ""
        )
        bible = bible_context_text(self.db_path, project_id)
        bible_context = (
            f"已有故事设定（必须保持一致，视为素材）：\n{bible}\n\n" if bible else ""
        )
        user = _EPISODE_USER.format(
            chapter_title=chapter.title or "未命名章节",
            chapter_content=content or "（空）",
            bible_context=bible_context,
            instruction=user_instruction or "（无）",
        )
        text = self.manager.chat(
            model_id,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.8,
            timeout=SCRIPT_TIMEOUT,
        )
        return parse_llm_json(
            AiEpisodeScriptResult, text, self.manager.chat, model_id, "剧本生成",
            system_prompt=system,
        )

    def generate_shots(
        self,
        project_id: str,
        scene_id: str,
        model_id: str,
        user_instruction: str = "",
        *,
        prompt_snapshot: dict | None = None,
    ) -> AiShotsResult:
        """场景 → 分镜（一次生成，结构化校验）。"""
        snapshot = (
            prompt_snapshot if prompt_snapshot is not None else self.prompts.snapshot(project_id)
        )
        system = self.prompts.system_prompt(project_id, "script_shots", snapshot=snapshot)
        scene = ScriptRepository(self.db_path).get_scene(project_id, scene_id)
        bible = bible_context_text(self.db_path, project_id)
        bible_context = (
            f"已有故事设定（必须保持一致，视为素材）：\n{bible}\n\n" if bible else ""
        )
        user = _SHOTS_USER.format(
            scene_title=scene.title or "未命名场景",
            scene_slugline=scene.slugline or "（无场景标题）",
            scene_action=scene.action or "（无动作）",
            scene_dialogue=scene.dialogue or "（无台词）",
            bible_context=bible_context,
            instruction=user_instruction or "（无）",
        )
        text = self.manager.chat(
            model_id,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.8,
            timeout=SCRIPT_TIMEOUT,
        )
        return parse_llm_json(
            AiShotsResult, text, self.manager.chat, model_id, "分镜生成",
            system_prompt=system,
        )

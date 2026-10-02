"""AI 整本小说撰写向导（AI 撰写）。

无状态接口：大纲生成 + 单章生成，向导状态由前端持有（刷新不丢）。
LLM 输出一律过 Pydantic 校验 + 一次修复重试；生成结果只返回预览，不落库，
由前端确认后调用现有章节 API 保存。
"""

import json
from pathlib import Path

from app.core.errors import AppError
from app.schemas.story import (
    AiChapterOut,
    AiNovelBrief,
    AiOutlineResult,
    OutlineChapter,
)
from app.services.adapters.manager import ProviderManager
from app.services.llm_json import parse_llm_json
from app.services.novel_repo import NovelRepository
from app.services.prompt_settings import PromptSettingsService
from app.services.story_repo import bible_context_text

CHAPTER_GEN_TIMEOUT = 300

_OUTLINE_USER = """题材：{genre}
受众：{audience}
情节复杂程度：{complexity}/10
章节数：{chapter_count}
用户的初步想法：
{ideas}
{bible_context}请输出书名与 {chapter_count} 章大纲。"""

_CHAPTER_USER = """题材：{genre}
受众：{audience}
情节复杂程度：{complexity}/10
用户的初步想法：{ideas}
{bible_context}整体大纲：
{outline}
前文摘要：
{previous}
本章索引：第 {index}/{total} 章
本章大纲要点：{current_summary}
本章额外要求：{instruction}
请撰写本章。"""

_CONTINUE_USER = """题材：{genre}
受众：{audience}
情节复杂程度：{complexity}/10
用户的初步想法：{ideas}
{bible_context}当前已有的前文（按章节顺序，较早章节已截断）：
{previous}
本章额外要求：{instruction}
请续写下一章。"""


class AiNovelService:
    def __init__(self, manager: ProviderManager, db_path: Path) -> None:
        self.manager = manager
        self.db_path = db_path
        self.prompts = PromptSettingsService(db_path)

    def outline(
        self, project_id: str, model_id: str, brief: AiNovelBrief,
        *,
        prompt_snapshot: dict | None = None,
    ) -> AiOutlineResult:
        snapshot = (
            prompt_snapshot if prompt_snapshot is not None else self.prompts.snapshot(project_id)
        )
        system = self.prompts.system_prompt(project_id, "novel_outline", snapshot=snapshot)
        bible = bible_context_text(self.db_path, project_id)
        bible_context = (
            f"已有故事设定（必须保持一致，视为素材）：\n{bible}\n\n" if bible else ""
        )
        user = _OUTLINE_USER.format(
            genre=brief.genre or "（未指定）",
            audience=brief.audience or "（未指定）",
            complexity=brief.complexity,
            chapter_count=brief.chapter_count,
            ideas=brief.ideas or "（暂无）",
            bible_context=bible_context,
        )
        text = self.manager.chat(
            model_id,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.6,
            timeout=120,
        )
        result = parse_llm_json(
            AiOutlineResult, text, self.manager.chat, model_id, "大纲生成",
            system_prompt=system,
        )
        if len(result.chapters) != brief.chapter_count:
            raise AppError(
                502,
                "ai_outline_count_mismatch",
                f"大纲章节数不符（期望 {brief.chapter_count}，实际 {len(result.chapters)}），请重试",
            )
        return result

    def chapter(
        self,
        project_id: str,
        model_id: str,
        brief: AiNovelBrief,
        outline: list[OutlineChapter],
        chapter_index: int,
        user_instruction: str = "",
        previous_summaries: list[str] | None = None,
        *,
        prompt_snapshot: dict | None = None,
    ) -> AiChapterOut:
        snapshot = (
            prompt_snapshot if prompt_snapshot is not None else self.prompts.snapshot(project_id)
        )
        system = self.prompts.system_prompt(project_id, "novel_chapter", snapshot=snapshot)
        if chapter_index >= len(outline):
            raise AppError(422, "ai_chapter_out_of_range", "章节索引超出大纲范围")
        current = outline[chapter_index]
        bible = bible_context_text(self.db_path, project_id)
        bible_context = (
            f"已有故事设定（必须保持一致，视为素材）：\n{bible}\n\n" if bible else ""
        )
        outline_json = json.dumps(
            [item.model_dump() for item in outline], ensure_ascii=False
        )
        previous = "\n".join(previous_summaries or []) or "（开头，无前文）"
        user = _CHAPTER_USER.format(
            genre=brief.genre or "（未指定）",
            audience=brief.audience or "（未指定）",
            complexity=brief.complexity,
            ideas=brief.ideas or "（暂无）",
            bible_context=bible_context,
            outline=outline_json,
            previous=previous,
            index=chapter_index + 1,
            total=len(outline),
            current_summary=current.summary or current.title,
            instruction=user_instruction or "（无）",
        )
        text = self.manager.chat(
            model_id,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.9,
            timeout=CHAPTER_GEN_TIMEOUT,
        )
        return parse_llm_json(
            AiChapterOut, text, self.manager.chat, model_id, "章节生成",
            system_prompt=system,
        )

    def chapter_stream(
        self,
        project_id: str,
        model_id: str,
        brief: AiNovelBrief,
        outline: list[OutlineChapter],
        chapter_index: int,
        user_instruction: str = "",
        previous_summaries: list[str] | None = None,
        *,
        prompt_snapshot: dict | None = None,
    ):
        """流式章节生成：逐段产出正文增量，供 SSE 使用。"""
        snapshot = (
            prompt_snapshot if prompt_snapshot is not None else self.prompts.snapshot(project_id)
        )
        system = self.prompts.system_prompt(project_id, "novel_chapter", snapshot=snapshot, variant="stream")
        if chapter_index >= len(outline):
            raise AppError(422, "ai_chapter_out_of_range", "章节索引超出大纲范围")
        current = outline[chapter_index]
        bible = bible_context_text(self.db_path, project_id)
        bible_context = (
            f"已有故事设定（必须保持一致，视为素材）：\n{bible}\n\n" if bible else ""
        )
        outline_json = json.dumps(
            [item.model_dump() for item in outline], ensure_ascii=False
        )
        previous = "\n".join(previous_summaries or []) or "（开头，无前文）"
        user = _CHAPTER_USER.format(
            genre=brief.genre or "（未指定）",
            audience=brief.audience or "（未指定）",
            complexity=brief.complexity,
            ideas=brief.ideas or "（暂无）",
            bible_context=bible_context,
            outline=outline_json,
            previous=previous,
            index=chapter_index + 1,
            total=len(outline),
            current_summary=current.summary or current.title,
            instruction=user_instruction or "（无）",
        )
        yield from self.manager.chat_stream(
            model_id,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.9,
            timeout=CHAPTER_GEN_TIMEOUT,
        )

    def continue_chapter_stream(
        self,
        project_id: str,
        novel_id: str,
        model_id: str,
        brief: AiNovelBrief,
        user_instruction: str = "",
        context_chapter_count: int = 3,
        *,
        prompt_snapshot: dict | None = None,
    ):
        """续写下一章：以小说最后 N 章正文为前文，流式生成。"""
        snapshot = (
            prompt_snapshot if prompt_snapshot is not None else self.prompts.snapshot(project_id)
        )
        system = self.prompts.system_prompt(project_id, "novel_continue_chapter", snapshot=snapshot)
        detail = NovelRepository(self.db_path).get(project_id, novel_id)
        chapters = detail.chapters
        if not chapters:
            raise AppError(422, "ai_continue_no_chapters", "当前小说还没有章节，无法续写")
        recent = chapters[-context_chapter_count:]
        parts = []
        for chapter in recent:
            body = (
                chapter.content[:2500]
                + ("……（内容过长已截断）" if len(chapter.content) > 2500 else "")
            )
            parts.append(f"《{chapter.title or '未命名章节'}》\n{body}")
        previous = "\n\n".join(parts) or "（无前文）"
        bible = bible_context_text(self.db_path, project_id)
        bible_context = (
            f"已有故事设定（必须保持一致，视为素材）：\n{bible}\n\n" if bible else ""
        )
        user = _CONTINUE_USER.format(
            genre=brief.genre or "（未指定）",
            audience=brief.audience or "（未指定）",
            complexity=brief.complexity,
            ideas=brief.ideas or "（暂无）",
            bible_context=bible_context,
            previous=previous,
            instruction=user_instruction or "（无）",
        )
        yield from self.manager.chat_stream(
            model_id,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.9,
            timeout=CHAPTER_GEN_TIMEOUT,
        )

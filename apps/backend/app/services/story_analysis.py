"""LLM Story Engine（Phase 6）。

管线：逐章抽取（携带滚动摘要 + 已抽实体）→ 全书合并（实体去重 + Synopsis +
冲突/情节线/伏笔）→ 写入 Story Bible。长文本用 map-reduce，避免超出上下文。
任务为内存 Job（真实进度），持久化 Job 系统属 Phase 10。
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.schemas.story import ChapterExtraction, StoryBible
from app.services.adapters.manager import ProviderManager
from app.services.llm_json import extract_json, parse_llm_json, trim
from app.services.novel_repo import NovelRepository
from app.services.prompt_settings import PromptSettingsService
from app.services.story_repo import StoryRepository

_extract_json = extract_json  # 兼容旧引用（测试导入）

MAX_CHAPTER_CHARS = 12000
MAX_ROLLING_CHARS = 3000
MAX_PREV_ENTITIES_CHARS = 2000
MAX_EXTRACTIONS_DUMP_CHARS = 45000

_EXTRACTION_USER = """小说：《{title}》
前文摘要：{rolling_summary}
已提取实体（用于避免新名字与旧实体冲突）：{prev_entities}

本章标题：{chapter_title}
本章内容：
{content}"""

_CONSOLIDATION_USER = """小说：《{title}》
{merge_context}以下是各章节抽取结果：
{extractions_json}
请合并为一份完整的 Story Bible。"""

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class StoryAnalysisService:
    def __init__(self, manager: ProviderManager, db_path: Path) -> None:
        self.manager = manager
        self.db_path = db_path
        self.prompts = PromptSettingsService(db_path)
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ---------- 任务入口 ----------

    def start(
        self, project_id: str, novel_id: str, model_id: str, mode: str = "full",
        *,
        prompt_snapshot: dict | None = None,
    ) -> dict:
        novel_repo = NovelRepository(self.db_path)
        detail = novel_repo.get(project_id, novel_id)
        if not detail.chapters:
            raise AppError(422, "no_chapters", "该小说还没有章节，无法分析")
        job_id = f"story_{uuid.uuid4().hex[:12]}"
        job = {
            "job_id": job_id,
            "project_id": project_id,
            "novel_id": novel_id,
            "model_id": model_id,
            "mode": mode,
            "prompt_snapshot": (
                prompt_snapshot if prompt_snapshot is not None else self.prompts.snapshot(project_id)
            ),
            "status": "queued",
            "progress": 0.0,
            "detail": "排队中",
            "error": None,
            "created_at": _now_iso(),
        }
        with self._lock:
            self._jobs[job_id] = job
        threading.Thread(target=self._run, args=(job_id,), daemon=True).start()
        return self.get(job_id)

    def get(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise AppError(404, "analysis_job_not_found", f"分析任务不存在: {job_id}")
        return {
            "job_id": job["job_id"],
            "project_id": job["project_id"],
            "status": job["status"],
            "progress": job["progress"],
            "detail": job["detail"],
            "error": job["error"],
            "created_at": job["created_at"],
        }

    # ---------- 工作线程 ----------

    def _run(self, job_id: str) -> None:
        job = self._jobs[job_id]
        try:
            novel_repo = NovelRepository(self.db_path)
            story_repo = StoryRepository(self.db_path)
            detail = novel_repo.get(job["project_id"], job["novel_id"])
            chapters = detail.chapters
            total = len(chapters)
            rolling_summary = ""
            extracted_names = ""
            extractions: list[ChapterExtraction] = []

            for index, chapter in enumerate(chapters):
                job["status"] = "running"
                job["progress"] = index / total
                job["detail"] = f"分析第 {index + 1}/{total} 章：{chapter.title or '未命名'}"
                extraction = self._extract_chapter(
                    job["model_id"],
                    detail.novel.title,
                    chapter.title or "",
                    chapter.content or "",
                    rolling_summary,
                    extracted_names,
                    project_id=job["project_id"],
                    prompt_snapshot=job["prompt_snapshot"],
                )
                extractions.append(extraction)
                rolling_summary = trim(
                    rolling_summary + "\n" + extraction.chapter_summary,
                    MAX_ROLLING_CHARS,
                )
                extracted_names = self._entity_names(extractions)

            job["progress"] = 0.9
            job["detail"] = "合并生成 Story Bible…"
            existing = (
                story_repo.get_bible(job["project_id"])
                if job["mode"] == "merge"
                else None
            )
            bible = self._consolidate(
                job["model_id"],
                detail.novel.title,
                extractions,
                existing,
                project_id=job["project_id"],
                prompt_snapshot=job["prompt_snapshot"],
            )
            story_repo.save_bible(job["project_id"], bible)
            job["status"] = "completed"
            job["progress"] = 1.0
            job["detail"] = (
                f"完成：{len(bible.characters)} 角色 / {len(bible.locations)} 地点"
                f" / {len(bible.props)} 道具"
            )
        except Exception as exc:  # noqa: BLE001 - 后台任务必须落定状态
            job["status"] = "failed"
            job["error"] = str(exc)
            job["detail"] = "分析失败"

    # ---------- LLM 调用 ----------

    def _extract_chapter(
        self,
        model_id: str,
        title: str,
        chapter_title: str,
        content: str,
        rolling_summary: str,
        prev_entities: str,
        *, project_id: str | None = None, prompt_snapshot: dict | None = None,
    ) -> ChapterExtraction:
        snapshot = prompt_snapshot
        if snapshot is None:
            snapshot = self.prompts.snapshot(project_id) if project_id else {"revision": 0, "stages": {}}
        system = self.prompts.system_prompt(project_id or "", "story_extract", snapshot=snapshot)
        content = trim(content, MAX_CHAPTER_CHARS)
        user = _EXTRACTION_USER.format(
            title=title,
            rolling_summary=rolling_summary or "（第一章）",
            prev_entities=prev_entities or "（暂无）",
            chapter_title=chapter_title,
            content=content,
        )
        text = self.manager.chat(
            model_id,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return self._parse_json(ChapterExtraction, text, model_id, "章节抽取", system_prompt=system)

    def _consolidate(
        self,
        model_id: str,
        title: str,
        extractions: list[ChapterExtraction],
        existing: StoryBible | None,
        *, project_id: str | None = None, prompt_snapshot: dict | None = None,
    ) -> StoryBible:
        snapshot = prompt_snapshot
        if snapshot is None:
            snapshot = self.prompts.snapshot(project_id) if project_id else {"revision": 0, "stages": {}}
        system = self.prompts.system_prompt(project_id or "", "story_consolidate", snapshot=snapshot)
        merge_context = ""
        if existing is not None:
            existing_json = json.dumps(existing.model_dump(), ensure_ascii=False)
            merge_context = (
                "这是已存在的 Story Bible（合并模式下请保留其中实体，并合并新增内容）：\n"
                + trim(existing_json, MAX_EXTRACTIONS_DUMP_CHARS)
                + "\n\n"
            )
        user = _CONSOLIDATION_USER.format(
            title=title,
            merge_context=merge_context,
            extractions_json=trim(
                json.dumps(
                    self._compact(extractions),
                    ensure_ascii=False,
                ),
                MAX_EXTRACTIONS_DUMP_CHARS,
            ),
        )
        text = self.manager.chat(
            model_id,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return self._parse_json(StoryBible, text, model_id, "Story Bible 合并", system_prompt=system)

    def _parse_json(self, model, text: str, model_id: str, label: str, *, system_prompt: str = ""):
        return parse_llm_json(model, text, self.manager.chat, model_id, label, system_prompt=system_prompt)

    # ---------- 辅助 ----------

    @staticmethod
    def _entity_names(extractions: list[ChapterExtraction]) -> str:
        names: list[str] = []
        for extraction in extractions:
            for character in extraction.characters:
                names.append(character.name)
            for location in extraction.locations:
                names.append(location.name)
            for prop in extraction.props:
                names.append(prop.name)
        seen: list[str] = []
        for name in names:
            if name not in seen:
                seen.append(name)
        return trim("、".join(seen), MAX_PREV_ENTITIES_CHARS)

    @staticmethod
    def _compact(extractions: list[ChapterExtraction]) -> list[dict]:
        """压缩抽取结果，控制合并阶段输入长度。"""
        compact: list[dict] = []
        for index, extraction in enumerate(extractions):
            compact.append(
                {
                    "chapter_index": index,
                    "chapter_summary": extraction.chapter_summary,
                    "characters": [
                        {
                            "name": c.name,
                            "aliases": c.aliases[:5],
                            "role_hint": c.role_hint,
                            "summary": c.summary[:200],
                        }
                        for c in extraction.characters
                    ],
                    "locations": [
                        {"name": loc.name, "description": loc.description[:200]}
                        for loc in extraction.locations
                    ],
                    "props": [
                        {"name": p.name, "description": p.description[:200]}
                        for p in extraction.props
                    ],
                    "events": [
                        {
                            "summary": e.summary,
                            "importance": e.importance,
                            "characters": e.characters[:8],
                        }
                        for e in extraction.events[:8]
                    ],
                }
            )
        return compact

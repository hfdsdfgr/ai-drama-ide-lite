import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { InfoTip } from "../components/InfoTip";
import {
  addChapter,
  createNovel,
  deleteChapter,
  deleteNovel,
  generateNovelText,
  getNovel,
  importNovel,
  listNovels,
  updateChapter,
  updateNovel,
} from "../api/novels";
import { listProjects } from "../api/projects";
import { listModels } from "../api/providers";
import {
  generateAiOutline,
  getStoryAnalysis,
  getStoryBible,
  startStoryAnalysis,
} from "../api/story";
import type { Model } from "../types/provider";
import type { Chapter, Novel, NovelDetail } from "../types/novel";
import type { Project } from "../types/project";
import type {
  AiChapter,
  AnalysisJob,
  AnalysisMode,
  OutlineChapter,
  StoryBible,
} from "../types/story";

type SaveState = "idle" | "saving" | "saved" | "error";
type AiAction = "continue" | "expand" | "rewrite";

// 虽然分类为 llm，但这些模型不是「文本创作」模型，不出现在小说 AI 下拉中
const NON_CHAT_LLM_FRAGMENTS = [
  "text-embedding",
  "embedding",
  "-tts-",
  "-asr-",
  "-ocr-",
  "-realtime",
  "livetranslate",
  "qwen-mt",
  "-omni-",
  "s2s",
  "captioner",
  "slp",
];

function isChatModel(model: Model): boolean {
  const id = model.model_id.toLowerCase();
  return !NON_CHAT_LLM_FRAGMENTS.some((fragment) => id.includes(fragment));
}

const GENRES = [
  "玄幻",
  "仙侠",
  "都市",
  "校园",
  "科幻",
  "悬疑",
  "言情",
  "武侠",
  "历史",
  "奇幻",
  "末世",
  "轻小说",
];

const AUDIENCES = ["全年龄", "青少年", "成人"];

export function NovelPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [novels, setNovels] = useState<Novel[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [detail, setDetail] = useState<NovelDetail | null>(null);
  const [chapterId, setChapterId] = useState<string | null>(null);
  const [novelTitle, setNovelTitle] = useState("");
  const [chapterTitle, setChapterTitle] = useState("");
  const [chapterContent, setChapterContent] = useState("");
  const [newNovelTitle, setNewNovelTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [novelSave, setNovelSave] = useState<SaveState>("idle");
  const [chapterSave, setChapterSave] = useState<SaveState>("idle");
  const [confirmDelete, setConfirmDelete] = useState<
    "chapter" | "novel" | null
  >(null);
  const [llmModels, setLlmModels] = useState<Model[]>([]);
  const [aiModelId, setAiModelId] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiAction, setAiAction] = useState<AiAction | null>(null);
  const [aiResult, setAiResult] = useState("");
  const [bible, setBible] = useState<StoryBible | null>(null);
  const [analysisJob, setAnalysisJob] = useState<AnalysisJob | null>(null);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const analysisPollRef = useRef<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"ai" | "bible">(
    "ai",
  );

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((e) => setError((e as Error).message));
  }, []);

  const refreshNovels = useCallback(
    async (pid: string, q: string) => {
      setLoading(true);
      setError("");
      try {
        setNovels(await listNovels(pid, q));
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (!projectId) return;
    setDetail(null);
    setChapterId(null);
    setAiResult("");
    void refreshNovels(projectId, "");
  }, [projectId, refreshNovels]);

  useEffect(() => {
    if (!projectId) return;
    listModels({ model_type: "llm", enabled_only: true })
      .then((models) => {
        const usable = models.filter(isChatModel);
        setLlmModels(usable);
        setAiModelId((prev) =>
          usable.some((m) => m.id === prev) ? prev : (usable[0]?.id ?? ""),
        );
      })
      .catch((e) => setError((e as Error).message));
  }, [projectId]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setQuery(searchInput);
    void refreshNovels(projectId, searchInput);
  }

  async function openNovel(novelId: string) {
    setError("");
    try {
      const loaded = await getNovel(projectId, novelId);
      setDetail(loaded);
      setNovelTitle(loaded.novel.title);
      const first = loaded.chapters[0] ?? null;
      setChapterId(first ? first.id : null);
      setChapterTitle(first ? first.title : "");
      setChapterContent(first ? first.content : "");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function selectChapter(id: string | null) {
    if (!detail) return;
    setChapterId(id);
    const chapter = detail.chapters.find((c) => c.id === id);
    setChapterTitle(chapter?.title ?? "");
    setChapterContent(chapter?.content ?? "");
    setChapterSave("idle");
    setAiResult("");
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const novel = await createNovel(projectId, newNovelTitle);
      setNewNovelTitle("");
      await refreshNovels(projectId, query);
      await openNovel(novel.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError("");
    try {
      const novel = await importNovel(projectId, file);
      await refreshNovels(projectId, query);
      await openNovel(novel.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleAddChapter() {
    if (!detail) return;
    setError("");
    try {
      const chapter = await addChapter(projectId, detail.novel.id, {
        title: `第 ${detail.chapters.length + 1} 章`,
      });
      const loaded = await getNovel(projectId, detail.novel.id);
      setDetail(loaded);
      selectChapter(chapter.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleDeleteChapter() {
    if (!detail || !chapterId) return;
    if (confirmDelete !== "chapter") {
      setConfirmDelete("chapter");
      return;
    }
    setConfirmDelete(null);
    setError("");
    try {
      await deleteChapter(projectId, detail.novel.id, chapterId);
      const loaded = await getNovel(projectId, detail.novel.id);
      setDetail(loaded);
      const first = loaded.chapters[0] ?? null;
      selectChapter(first ? first.id : null);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleDeleteNovel() {
    if (!detail) return;
    if (confirmDelete !== "novel") {
      setConfirmDelete("novel");
      return;
    }
    setConfirmDelete(null);
    setError("");
    try {
      await deleteNovel(projectId, detail.novel.id);
      setDetail(null);
      setChapterId(null);
      await refreshNovels(projectId, query);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function runAi(action: AiAction) {
    if (!detail || !chapterId) return;
    setAiBusy(true);
    setError("");
    setAiAction(action);
    try {
      const result = await generateNovelText(
        projectId,
        detail.novel.id,
        chapterId,
        action,
        aiModelId,
      );
      setAiResult(result.text);
    } catch (err) {
      setAiResult("");
      setAiAction(null);
      setError((err as Error).message);
    } finally {
      setAiBusy(false);
    }
  }

  function applyAiResult() {
    if (!aiResult) return;
    if (aiAction === "continue") {
      setChapterContent((prev) =>
        prev.trim() ? `${prev}\n\n${aiResult}` : aiResult,
      );
    } else {
      setChapterContent(aiResult);
    }
    setAiResult("");
    setAiAction(null);
  }

  // 小说标题自动保存
  useEffect(() => {
    if (!detail || novelTitle === detail.novel.title) return;
    setNovelSave("saving");
    const timer = setTimeout(async () => {
      try {
        const updated = await updateNovel(projectId, detail.novel.id, {
          title: novelTitle,
        });
        setDetail((prev) => (prev ? { ...prev, novel: updated } : prev));
        setNovels((prev) =>
          prev.map((n) => (n.id === updated.id ? updated : n)),
        );
        setNovelSave("saved");
      } catch (err) {
        setNovelSave("error");
        setError((err as Error).message);
      }
    }, 800);
    return () => clearTimeout(timer);
  }, [novelTitle, detail, projectId]);

  // 章节标题/内容自动保存
  useEffect(() => {
    if (!detail || !chapterId) return;
    const chapter = detail.chapters.find((c) => c.id === chapterId);
    if (!chapter || (chapter.title === chapterTitle && chapter.content === chapterContent)) {
      return;
    }
    setChapterSave("saving");
    const timer = setTimeout(async () => {
      try {
        const updated = await updateChapter(projectId, detail.novel.id, chapterId, {
          title: chapterTitle,
          content: chapterContent,
        });
        setDetail((prev) =>
          prev
            ? {
                ...prev,
                chapters: prev.chapters.map((c) =>
                  c.id === updated.id ? updated : c,
                ),
              }
            : prev,
        );
        setChapterSave("saved");
      } catch (err) {
        setChapterSave("error");
        setError((err as Error).message);
      }
    }, 800);
    return () => clearTimeout(timer);
  }, [chapterTitle, chapterContent, chapterId, detail, projectId]);

  const selectedChapter: Chapter | undefined =
    detail?.chapters.find((c) => c.id === chapterId) ?? undefined;
  const currentNovelId = detail?.novel.id;
  const totalWords = useMemo(
    () =>
      detail
        ? detail.chapters.reduce((sum, c) => sum + c.content.length, 0)
        : 0,
    [detail],
  );

  useEffect(() => {
    if (!currentNovelId) return;
    setAnalysisJob(null);
    analysisPollRef.current = null;
    setBible(null);
    getStoryBible(projectId)
      .then((r) => setBible(r.bible))
      .catch((e) => setError((e as Error).message));
  }, [projectId, currentNovelId]);

  async function runAnalysis(mode: AnalysisMode) {
    if (!detail || !aiModelId) return;
    setAnalysisBusy(true);
    setError("");
    try {
      const job = await startStoryAnalysis(projectId, detail.novel.id, aiModelId, mode);
      setAnalysisJob(job);
      analysisPollRef.current = job.job_id;
      while (analysisPollRef.current === job.job_id) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        if (analysisPollRef.current !== job.job_id) break;
        const updated = await getStoryAnalysis(projectId, job.job_id);
        setAnalysisJob(updated);
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          analysisPollRef.current = null;
          if (updated.status === "completed") {
            const bibleResult = await getStoryBible(projectId);
            setBible(bibleResult.bible);
          }
          break;
        }
      }
    } catch (err) {
      setError((err as Error).message);
      analysisPollRef.current = null;
    } finally {
      setAnalysisBusy(false);
    }
  }

  const [wiz, setWiz] = useState<{
    genre: string;
    audience: string;
    ideas: string;
    complexity: number;
    chapterCount: number;
    outlineTitle: string;
    outline: OutlineChapter[] | null;
    writing: boolean;
    currentIndex: number;
    preview: AiChapter | null;
    streaming: boolean;
    instruction: string;
    previousSummaries: string[];
    done: boolean;
  } | null>(null);
  const [wizBusy, setWizBusy] = useState(false);
  const [wizError, setWizError] = useState("");

  function updateWiz(
    patch: Partial<NonNullable<typeof wiz>>,
  ) {
    setWiz((prev) => (prev ? { ...prev, ...patch } : prev));
  }

  function startWizard() {
    setWiz({
      genre: "玄幻",
      audience: "全年龄",
      ideas: "",
      complexity: 5,
      chapterCount: 10,
      outlineTitle: "",
      outline: null,
      writing: false,
      currentIndex: 0,
      preview: null,
      streaming: false,
      instruction: "",
      previousSummaries: [],
      done: false,
    });
    setWizError("");
  }

  function wizardBrief() {
    if (!wiz) return null;
    return {
      genre: wiz.genre,
      audience: wiz.audience,
      ideas: wiz.ideas,
      complexity: wiz.complexity,
      chapter_count: wiz.chapterCount,
    };
  }

  async function genOutline(e: React.FormEvent) {
    e.preventDefault();
    if (!wiz || !aiModelId) return;
    setWizBusy(true);
    setWizError("");
    try {
      const brief = wizardBrief();
      if (!brief) return;
      const result = await generateAiOutline(projectId, aiModelId, brief);
      updateWiz({ outlineTitle: result.title, outline: result.chapters });
    } catch (err) {
      setWizError((err as Error).message);
    } finally {
      setWizBusy(false);
    }
  }

  async function startWriting() {
    if (!wiz) return;
    setWizBusy(true);
    setWizError("");
    try {
      let novelId = detail?.novel.id;
      if (!novelId) {
        const created = await createNovel(
          projectId,
          wiz.outlineTitle || "AI 撰写小说",
        );
        await refreshNovels(projectId, "");
        const loaded = await getNovel(projectId, created.id);
        setDetail(loaded);
        novelId = created.id;
      }
      updateWiz({ writing: true, currentIndex: 0 });
    } catch (err) {
      setWizError((err as Error).message);
    } finally {
      setWizBusy(false);
    }
  }

  async function genChapterPreview() {
    if (!wiz || !aiModelId || !wiz.outline) return;
    setWizBusy(true);
    setWizError("");
    const outline = wiz.outline;
    const index = wiz.currentIndex;
    const current = outline[index];
    updateWiz({
      streaming: true,
      preview: {
        title: current.title,
        content: "",
        summary: current.summary,
      },
    });
    try {
      const brief = wizardBrief();
      if (!brief) return;
      const response = await fetch(
        `/api/projects/${projectId}/story/ai-chapter-stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model_id: aiModelId,
            brief,
            outline,
            chapter_index: index,
            user_instruction: wiz.instruction,
            previous_summaries: wiz.previousSummaries,
          }),
        },
      );
      if (!response.ok || !response.body) {
        throw new Error(`请求失败（HTTP ${response.status}）`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.split("\n")[0];
          if (!line.startsWith("data:")) continue;
          let data: { delta?: string; done?: boolean; error?: string };
          try {
            data = JSON.parse(line.slice(5)) as {
              delta?: string;
              done?: boolean;
              error?: string;
            };
          } catch {
            continue;
          }
          if (data.error) throw new Error(data.error);
          if (data.delta) {
            setWiz((prev) =>
              prev?.preview
                ? {
                    ...prev,
                    preview: {
                      ...prev.preview,
                      content: prev.preview.content + (data.delta ?? ""),
                    },
                  }
                : prev,
            );
          }
        }
      }
      updateWiz({ streaming: false });
    } catch (err) {
      setWizError((err as Error).message);
      updateWiz({ streaming: false, preview: null });
    } finally {
      setWizBusy(false);
    }
  }

  function exportPreviewTxt() {
    if (!wiz?.preview) return;
    const text = `${wiz.preview.title}\n\n${wiz.preview.content}`;
    const blob = new Blob(["\ufeff" + text], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${wiz.preview.title || "章节"}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function savePreviewChapter() {
    if (!wiz?.preview || !detail) return;
    setWizBusy(true);
    setWizError("");
    try {
      await addChapter(projectId, detail.novel.id, {
        title: wiz.preview.title,
        content: wiz.preview.content,
      });
      const loaded = await getNovel(projectId, detail.novel.id);
      setDetail(loaded);
      const next = wiz.currentIndex + 1;
      updateWiz({
        currentIndex: next,
        preview: null,
        instruction: "",
        previousSummaries: [...wiz.previousSummaries, wiz.preview.summary],
        done: next >= (wiz.outline?.length ?? 0),
      });
    } catch (err) {
      setWizError((err as Error).message);
    } finally {
      setWizBusy(false);
    }
  }

  function updateOutlineChapter(
    index: number,
    field: keyof OutlineChapter,
    value: string,
  ) {
    setWiz((prev) => {
      if (!prev?.outline) return prev;
      return {
        ...prev,
        outline: prev.outline.map((c, i) =>
          i === index ? { ...c, [field]: value } : c,
        ),
      };
    });
  }

  function addOutlineChapter() {
    setWiz((prev) => {
      if (!prev?.outline) return prev;
      return {
        ...prev,
        outline: [
          ...prev.outline,
          { title: `第 ${prev.outline.length + 1} 章`, summary: "" },
        ],
      };
    });
  }

  function removeOutlineChapter(index: number) {
    setWiz((prev) => {
      if (!prev?.outline) return prev;
      return {
        ...prev,
        outline: prev.outline.filter((_, i) => i !== index),
      };
    });
  }

  useEffect(() => {
    setConfirmDelete(null);
  }, [chapterId, detail?.novel.id]);

  return (
    <div className="page novel-page">
      <div className="novel-topbar">
        {projects.length === 0 && (
          <p className="muted">还没有项目，请先在「主页」创建。</p>
        )}
        {error && <p className="error">{error}</p>}
        {projectId && (
          <form onSubmit={handleSearch} className="toolbar search-form">
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="搜索小说 / 章节内容"
            />
            <button type="submit">搜索</button>
          </form>
        )}
      </div>

      {projects.length > 0 && (
        <div className="novel-workspace">
          <aside className="novel-sidebar">
            <div className="sidebar-block">
              <div className="sidebar-head">
                <h3>项目</h3>
              </div>
              <select
                className="project-select"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
              >
                <option value="">选择项目</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="sidebar-block">
              <h3>小说</h3>
            {!projectId ? (
              <p className="muted">选择上方项目后查看小说。</p>
            ) : loading ? (
              <p>加载中…</p>
            ) : novels.length === 0 ? (
              <p className="muted">没有小说，新建或导入一个。</p>
            ) : (
              <ul className="novel-list">
                {novels.map((novel) => (
                  <li key={novel.id}>
                    <button
                      type="button"
                      className={
                        detail?.novel.id === novel.id
                          ? "project-item active"
                          : "project-item"
                      }
                      onClick={() => openNovel(novel.id)}
                    >
                      <span className="project-name">{novel.title}</span>
                      <span className="muted">
                        {novel.chapter_count} 章 ·{" "}
                        {novel.source_type === "imported" ? "导入" : "原创"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            </div>

            {detail && (
              <div className="sidebar-block">
                <div className="sidebar-head">
                  <h3>章节</h3>
                  <button type="button" onClick={handleAddChapter}>
                    + 新章节
                  </button>
                </div>
                <ul className="chapter-tree">
                  {detail.chapters.map((c) => (
                    <li key={c.id}>
                      <button
                        type="button"
                        className={
                          c.id === chapterId ? "chapter-item active" : "chapter-item"
                        }
                        onClick={() => selectChapter(c.id)}
                      >
                        {c.title || "未命名章节"}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {projectId && (
              <>
              <div className="sidebar-block">
                <h3>导入与管理</h3>
                <input
                  type="file"
                  id="novel-import-input"
                  accept=".txt,.md,.markdown,.docx"
                  style={{ display: "none" }}
                  onChange={handleImport}
                />
                <label htmlFor="novel-import-input" className="button-like">
                  导入 TXT/MD/DOCX
                </label>
                {confirmDelete === "novel" ? (
                  <div className="actions">
                    <button
                      type="button"
                      className="button-danger"
                      onClick={handleDeleteNovel}
                    >
                      确认删除
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDelete(null)}
                    >
                      取消
                    </button>
                  </div>
                ) : detail ? (
                  <button
                    type="button"
                    className="button-danger button-ghost"
                    onClick={handleDeleteNovel}
                  >
                    删除小说
                  </button>
                ) : null}
              </div>

              <form className="sidebar-block" onSubmit={handleCreate}>
                <h3>新建小说</h3>
                <input
                  value={newNovelTitle}
                  onChange={(e) => setNewNovelTitle(e.target.value)}
                  placeholder="新小说标题"
                />
                <button type="submit">创建</button>
              </form>

              <div className="sidebar-block">
                <h3>项目统计</h3>
                <ul className="stats-list">
                  <li>
                    <span>章节</span>
                    <b>{detail?.chapters.length ?? 0}</b>
                  </li>
                  <li>
                    <span>字数</span>
                    <b>{totalWords}</b>
                  </li>
                  <li>
                    <span>角色</span>
                    <b>{bible?.characters.length ?? 0}</b>
                  </li>
                  <li>
                    <span>场景</span>
                    <b>{bible?.locations.length ?? 0}</b>
                  </li>
                </ul>
              </div>
              </>
            )}
        </aside>

        <section className="novel-main">
          {detail ? (
            <>
                <div className="novel-head">
                  <label>
                    小说标题
                    <input
                      value={novelTitle}
                      onChange={(e) => setNovelTitle(e.target.value)}
                    />
                  </label>
                  <span className="muted save-status">
                    {novelSave === "saving" && "标题保存中…"}
                    {novelSave === "saved" && "标题已保存"}
                  </span>
                </div>

                {selectedChapter ? (
                  <>
                    <label>
                      章节标题
                      <input
                        value={chapterTitle}
                        onChange={(e) => setChapterTitle(e.target.value)}
                      />
                    </label>
                    <label>
                      正文（可直接编辑，自动保存）
                      <textarea
                        className="chapter-textarea"
                        value={chapterContent}
                        onChange={(e) => setChapterContent(e.target.value)}
                        rows={18}
                      />
                    </label>
                    <div className="actions">
                      <span className="muted save-status">
                        {chapterSave === "saving" && "自动保存中…"}
                        {chapterSave === "saved" && "已保存"}
                        {chapterSave === "error" && "保存失败"}
                      </span>
                      {confirmDelete === "chapter" ? (
                        <>
                          <button
                            type="button"
                            className="button-danger"
                            onClick={handleDeleteChapter}
                          >
                            确认删除
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDelete(null)}
                          >
                            取消
                          </button>
                        </>
                      ) : (
                        <button
                          type="button"
                          className="button-danger"
                          onClick={handleDeleteChapter}
                        >
                          删除章节
                        </button>
                      )}
                    </div>
                  </>
                ) : (
                  <p className="muted">点击左侧「+ 新章节」开始写作。</p>
                )}
              </>
            ) : (
              <div className="novel-empty">
                <p className="muted">
                  {!projectId
                    ? "请先在上方选择项目，再打开一部小说。"
                    : "从左侧选择一部小说开始阅读与创作。"}
                </p>
              </div>
            )}
          </section>

          <aside className="novel-inspector">
            <div className="tabs">
              <button
                type="button"
                className={inspectorTab === "ai" ? "tab active" : "tab"}
                onClick={() => setInspectorTab("ai")}
              >
                AI 助手
              </button>
              <button
                type="button"
                className={inspectorTab === "bible" ? "tab active" : "tab"}
                onClick={() => setInspectorTab("bible")}
              >
                Story Bible
              </button>
            </div>
            <div className="inspector-body">
              {inspectorTab === "ai" ? (
                <>
                <div className="card inspector-card assistant-head">
                  <h3>AI 助手</h3>
                  <p className="muted">
                    负责创意、大纲、续写、扩写、重写与整本小说生成。
                  </p>
                </div>
                {selectedChapter && (
                  <div className="card inspector-card context-card">
                    <h4>当前上下文</h4>
                    <p className="muted">
                      {selectedChapter.title || "未命名章节"} · 已写{" "}
                      {selectedChapter.content.length} 字
                    </p>
                    <p className="muted">
                      下一步：用下方「AI 创作」续写 / 扩写 / 重写本章，或用「AI
                      撰写」生成整本小说。
                    </p>
                  </div>
                )}
                <div className="card inspector-card">
                  <h3>AI 创作</h3>
                  {llmModels.length === 0 ? (
                    <p className="muted">
                      没有可用的文本模型。请在「设置」中启用至少一个文本模型，
                      并确认其 Provider 已启用（Provider 和模型需要同时启用）。
                    </p>
                  ) : (
                    <>
                      <label>
                        文本模型
                        <InfoTip text="从已配置并启用的文本模型中选择；可在「设置」中添加更多模型" />
                        <select
                          value={aiModelId}
                          onChange={(e) => setAiModelId(e.target.value)}
                        >
                          {llmModels.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.provider_name} / {m.model_id}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="toolbar">
                        <button
                          type="button"
                          disabled={!selectedChapter || aiBusy}
                          onClick={() => runAi("continue")}
                        >
                          {aiBusy && aiAction === "continue" ? "生成中…" : "AI 续写"}
                        </button>
                        <button
                          type="button"
                          disabled={!selectedChapter || aiBusy}
                          onClick={() => runAi("expand")}
                        >
                          {aiBusy && aiAction === "expand" ? "生成中…" : "AI 扩写"}
                        </button>
                        <button
                          type="button"
                          disabled={!selectedChapter || aiBusy}
                          onClick={() => runAi("rewrite")}
                        >
                          {aiBusy && aiAction === "rewrite" ? "生成中…" : "AI 重写"}
                        </button>
                      </div>
                    </>
                  )}

                  {aiResult && (
                    <div className="ai-result">
                      <label>
                        AI 生成结果（预览）
                        <textarea
                          className="chapter-textarea"
                          value={aiResult}
                          readOnly
                          rows={10}
                        />
                      </label>
                      <div className="actions">
                        <button type="button" onClick={applyAiResult}>
                          {aiAction === "continue" ? "插入到结尾" : "替换正文"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setAiResult("");
                            setAiAction(null);
                          }}
                        >
                          放弃
                        </button>
                      </div>
                    </div>
                  )}
                </div>
                <div className="card inspector-card">
              <div className="page-head">
                <h3>AI 撰写整本小说</h3>
                {wiz && (
                  <button type="button" onClick={() => setWiz(null)}>
                    关闭向导
                  </button>
                )}
              </div>
              {!wiz ? (
                <div className="toolbar">
                  <button type="button" onClick={startWizard}>
                    开始 AI 撰写
                  </button>
                  <span className="muted">
                    从题材设定到大纲再到正文，AI 逐章撰写，每章由你确认。
                  </span>
                </div>
              ) : wiz.outline === null ? (
                <form className="wizard-form" onSubmit={genOutline}>
                  <label>
                    题材
                    <select
                      value={GENRES.includes(wiz.genre) ? wiz.genre : "自定义"}
                      onChange={(e) =>
                        updateWiz({
                          genre: e.target.value === "自定义" ? "" : e.target.value,
                        })
                      }
                    >
                      <option value="">选择题材</option>
                      {GENRES.map((g) => (
                        <option key={g} value={g}>
                          {g}
                        </option>
                      ))}
                      <option value="自定义">自定义</option>
                    </select>
                  </label>
                  {!GENRES.includes(wiz.genre) && wiz.genre !== "" && (
                    <label>
                      自定义题材
                      <input
                        value={wiz.genre}
                        onChange={(e) => updateWiz({ genre: e.target.value })}
                        placeholder="输入题材，如：克苏鲁"
                      />
                    </label>
                  )}
                  <label>
                    受众
                    <select
                      value={wiz.audience}
                      onChange={(e) => updateWiz({ audience: e.target.value })}
                    >
                      {AUDIENCES.map((a) => (
                        <option key={a} value={a}>
                          {a}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    情节复杂程度（{wiz.complexity}/10）
                    <input
                      type="range"
                      min={1}
                      max={10}
                      value={wiz.complexity}
                      onChange={(e) =>
                        updateWiz({ complexity: Number(e.target.value) })
                      }
                    />
                  </label>
                  <p className="muted">
                    {wiz.complexity <= 3
                      ? "爽文向：单主线、快节奏、爽点密集"
                      : wiz.complexity <= 7
                        ? "中等复杂：两三条情节线、有铺垫转折"
                        : "大部头向：多线叙事、长线伏笔、人物弧光"}
                  </p>
                  <label>
                    章节数
                    <input
                      type="number"
                      min={1}
                      max={60}
                      value={wiz.chapterCount}
                      onChange={(e) =>
                        updateWiz({
                          chapterCount: Math.min(
                            60,
                            Math.max(1, Number(e.target.value) || 1),
                          ),
                        })
                      }
                    />
                  </label>
                  <label>
                    初步想法
                    <textarea
                      value={wiz.ideas}
                      onChange={(e) => updateWiz({ ideas: e.target.value })}
                      rows={3}
                      placeholder="主角是谁？世界观？想看什么剧情？风格偏好？"
                    />
                  </label>
                  <div className="toolbar">
                    <button type="submit" disabled={wizBusy || !aiModelId}>
                      {wizBusy ? "生成中…" : "生成大纲"}
                    </button>
                  </div>
                  {wizError && <p className="error">{wizError}</p>}
                </form>
              ) : wiz.done ? (
                <div className="toolbar">
                  <p className="ok">
                    全书撰写完成：{wiz.outline.length} 章已保存到当前小说。
                  </p>
                  <button type="button" onClick={() => setWiz(null)}>
                    关闭向导
                  </button>
                </div>
              ) : !wiz.writing ? (
                <>
                  <p className="muted">
                    书名：{wiz.outlineTitle || "（未命名）"} · 将写入
                    {detail ? `当前小说「${detail.novel.title}」` : "新建小说"}
                  </p>
                  <div className="wizard-outline">
                    {wiz.outline.map((c, i) => (
                      <div key={i} className="wizard-outline-row">
                        <input
                          value={c.title}
                          onChange={(e) =>
                            updateOutlineChapter(i, "title", e.target.value)
                          }
                          placeholder="章节标题"
                        />
                        <textarea
                          value={c.summary}
                          onChange={(e) =>
                            updateOutlineChapter(i, "summary", e.target.value)
                          }
                          rows={2}
                          placeholder="本章内容要点"
                        />
                        <button
                          type="button"
                          onClick={() => removeOutlineChapter(i)}
                        >
                          删除
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="toolbar">
                    <button type="button" onClick={addOutlineChapter}>
                      添加章节
                    </button>
                    <button
                      type="button"
                      disabled={wizBusy || wiz.outline.length === 0}
                      onClick={startWriting}
                    >
                      开始逐章撰写
                    </button>
                    <button
                      type="button"
                      onClick={() => updateWiz({ outline: null })}
                    >
                      重新生成大纲
                    </button>
                  </div>
                  {wizError && <p className="error">{wizError}</p>}
                </>
              ) : (
                <>
                  <p className="muted">
                    正在撰写第 {wiz.currentIndex + 1}/{wiz.outline.length} 章：
                    {wiz.outline[wiz.currentIndex].title}（
                    {wiz.outline[wiz.currentIndex].summary || "无要点"}）
                  </p>
                  <label>
                    对本章的要求（可留空）
                    <textarea
                      value={wiz.instruction}
                      onChange={(e) => updateWiz({ instruction: e.target.value })}
                      rows={2}
                      placeholder="例如：节奏快一点 / 多写对话 / 让主角吃瘪"
                    />
                  </label>
                  {wiz.preview ? (
                    <div className="wizard-preview">
                      <p className="muted">
                        {wiz.streaming
                          ? `正在生成… 已生成 ${wiz.preview.content.length} 字`
                          : `本章共 ${wiz.preview.content.length} 字`}
                      </p>
                      <label>
                        章节标题
                        <input
                          value={wiz.preview.title}
                          onChange={(e) => {
                            if (!wiz.preview) return;
                            updateWiz({
                              preview: { ...wiz.preview, title: e.target.value },
                            });
                          }}
                          disabled={wiz.streaming}
                        />
                      </label>
                      <label>
                        正文预览
                        <textarea
                          className="chapter-textarea"
                          value={wiz.preview.content}
                          onChange={(e) => {
                            if (!wiz.preview) return;
                            updateWiz({
                              preview: { ...wiz.preview, content: e.target.value },
                            });
                          }}
                          rows={12}
                          readOnly={wiz.streaming}
                        />
                      </label>
                      <div className="toolbar">
                        <button
                          type="button"
                          disabled={wizBusy || !detail || wiz.streaming}
                          onClick={savePreviewChapter}
                        >
                          接受并保存 → 下一章
                        </button>
                        <button
                          type="button"
                          disabled={wizBusy || wiz.streaming}
                          onClick={genChapterPreview}
                        >
                          按意见重写本章
                        </button>
                        <button
                          type="button"
                          disabled={wiz.streaming}
                          onClick={exportPreviewTxt}
                        >
                          导出 TXT
                        </button>
                        <button
                          type="button"
                          disabled={wiz.streaming}
                          onClick={() => updateWiz({ preview: null })}
                        >
                          放弃本章
                        </button>
                      </div>
                      {!detail && (
                        <p className="muted">
                          请先创建并打开一部小说，才能保存章节（当前将新建）。
                        </p>
                      )}
                    </div>
                  ) : (
                    <div className="toolbar">
                      <button
                        type="button"
                        disabled={wizBusy || !aiModelId}
                        onClick={genChapterPreview}
                      >
                        {wizBusy ? "生成中…" : "生成本章"}
                      </button>
                    </div>
                  )}
                  {wizError && <p className="error">{wizError}</p>}
                </>
              )}
            </div>
              </>
              ) : (
                <>
                <div className="card inspector-card assistant-head">
                  <h3>Story Bible</h3>
                  <p className="muted">
                    项目长期设定：世界观、人物、地点、时间线。AI
                    写作会以它为设定依据。
                  </p>
                </div>
                <div className="card inspector-card">
                  <h3>故事分析（Story Bible）</h3>
              {llmModels.length === 0 ? (
                <p className="muted">
                  没有可用的文本模型。请在「设置」中启用至少一个文本模型，
                  并确认其 Provider 已启用（Provider 和模型需要同时启用）。
                </p>
              ) : (
                <>
                  <div className="toolbar">
                    <button
                      type="button"
                      disabled={!detail || !aiModelId || analysisBusy}
                      onClick={() => runAnalysis("full")}
                    >
                      分析故事
                    </button>
                    <button
                      type="button"
                      disabled={!detail || !aiModelId || analysisBusy || !bible}
                      onClick={() => runAnalysis("merge")}
                    >
                      增量合并新章节
                    </button>
                    {analysisJob && (
                      <span className="muted">
                        {analysisJob.detail}
                        {analysisJob.progress != null &&
                          `（${Math.round(analysisJob.progress * 100)}%）`}
                      </span>
                    )}
                  </div>
                  {analysisJob?.error && (
                    <p className="error">{analysisJob.error}</p>
                  )}
                  {!detail && (
                    <p className="muted">先打开一部小说，再进行分析。</p>
                  )}
                  {bible ? (
                    <div className="bible">
                      {bible.synopsis && <p>{bible.synopsis}</p>}
                      {bible.characters.length > 0 && (
                        <div className="bible-section">
                          <h4>角色</h4>
                          <ul>
                            {bible.characters.map((c) => (
                              <li key={c.name}>
                                <strong>{c.name}</strong>
                                {c.role_hint ? `（${c.role_hint}）` : ""} {c.summary}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {bible.locations.length > 0 && (
                        <div className="bible-section">
                          <h4>地点</h4>
                          <ul>
                            {bible.locations.map((l) => (
                              <li key={l.name}>
                                <strong>{l.name}</strong> {l.description}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {bible.props.length > 0 && (
                        <div className="bible-section">
                          <h4>道具</h4>
                          <ul>
                            {bible.props.map((p) => (
                              <li key={p.name}>
                                <strong>{p.name}</strong> {p.description}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {bible.events.length > 0 && (
                        <div className="bible-section">
                          <h4>时间线</h4>
                          <ol>
                            {bible.events.map((e, i) => (
                              <li key={i}>
                                第 {e.chapter_index + 1} 章：{e.summary}
                              </li>
                            ))}
                          </ol>
                        </div>
                      )}
                      {bible.conflicts.length > 0 && (
                        <div className="bible-section">
                          <h4>主要冲突</h4>
                          <ul>
                            {bible.conflicts.map((c) => (
                              <li key={c}>{c}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {bible.plotlines.length > 0 && (
                        <div className="bible-section">
                          <h4>情节线</h4>
                          <ul>
                            {bible.plotlines.map((p) => (
                              <li key={p}>{p}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {bible.foreshadowing.length > 0 && (
                        <div className="bible-section">
                          <h4>伏笔</h4>
                          <ul>
                            {bible.foreshadowing.map((f) => (
                              <li key={f}>{f}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ) : (
                    detail && (
                      <p className="muted">
                        还没有 Story Bible。点击「分析故事」从当前小说提取角色、地点、道具与事件。
                      </p>
                    )
                  )}
                </>
              )}
            </div>
                </>
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

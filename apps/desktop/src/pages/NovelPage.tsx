import { useCallback, useEffect, useState } from "react";

import {
  addChapter,
  createNovel,
  deleteChapter,
  deleteNovel,
  getNovel,
  importNovel,
  listNovels,
  updateChapter,
  updateNovel,
} from "../api/novels";
import { listProjects } from "../api/projects";
import type { Chapter, Novel, NovelDetail } from "../types/novel";
import type { Project } from "../types/project";

type SaveState = "idle" | "saving" | "saved" | "error";

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
    void refreshNovels(projectId, "");
  }, [projectId, refreshNovels]);

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
    if (!window.confirm("确定删除当前章节？")) return;
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
    if (!window.confirm(`确定删除小说「${detail.novel.title}」？`)) return;
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

  return (
    <div className="page">
      <div className="page-head">
        <h2>小说</h2>
      </div>

      {projects.length === 0 ? (
        <p className="muted">还没有项目，请先在「项目」页创建。</p>
      ) : (
        <label>
          项目
          <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
            <option value="">选择项目</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {error && <p className="error">{error}</p>}

      {projectId && (
        <>
          <div className="toolbar">
            <form onSubmit={handleSearch} className="toolbar">
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="搜索小说 / 章节内容"
              />
              <button type="submit">搜索</button>
            </form>
            <form onSubmit={handleCreate} className="toolbar">
              <input
                value={newNovelTitle}
                onChange={(e) => setNewNovelTitle(e.target.value)}
                placeholder="新小说标题"
              />
              <button type="submit">新建</button>
            </form>
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
          </div>

          <div className="card">
            <h3>小说列表</h3>
            {loading ? (
              <p>加载中…</p>
            ) : novels.length === 0 ? (
              <p className="muted">没有小说，新建或导入一个。</p>
            ) : (
              <ul className="project-list">
                {novels.map((novel) => (
                  <li key={novel.id}>
                    <button
                      type="button"
                      className="project-item"
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
            <div className="novel-editor">
              <aside className="chapter-list">
                <h3>章节</h3>
                <button type="button" onClick={handleAddChapter}>
                  + 新章节
                </button>
                <ul>
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
                <button type="button" className="button-danger" onClick={handleDeleteNovel}>
                  删除小说
                </button>
              </aside>

              <section className="chapter-edit">
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
                      正文
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
                      <button
                        type="button"
                        className="button-danger"
                        onClick={handleDeleteChapter}
                      >
                        删除章节
                      </button>
                    </div>
                  </>
                ) : (
                  <p className="muted">点击「+ 新章节」开始写作。</p>
                )}

                <div className="card ai-placeholder">
                  <h3>AI 创作</h3>
                  <p className="muted">
                    AI 续写 / 扩写 / 重写将在 Phase 3（AI Provider 基础系统）后可用。
                  </p>
                  <div className="toolbar">
                    <button type="button" disabled>
                      AI 续写
                    </button>
                    <button type="button" disabled>
                      AI 扩写
                    </button>
                    <button type="button" disabled>
                      AI 重写
                    </button>
                  </div>
                </div>
              </section>
            </div>
          )}
        </>
      )}
    </div>
  );
}

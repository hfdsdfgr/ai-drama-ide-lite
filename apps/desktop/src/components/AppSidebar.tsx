import { useCallback, useEffect, useState } from "react";

import { getNovel, listNovels } from "../api/novels";
import { getProject } from "../api/projects";
import type { Chapter, Novel } from "../types/novel";

export interface NovelJump {
  novelId: string;
  chapterId?: string | null;
}

interface AppSidebarProps {
  activeProjectId: string;
  onJump: (target: NovelJump) => void;
}

export function AppSidebar({ activeProjectId, onJump }: AppSidebarProps) {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [chapters, setChapters] = useState<Record<string, Chapter[]>>({});
  const [openNovelId, setOpenNovelId] = useState<string | null>(null);
  const [busyNovelId, setBusyNovelId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem("ai-drama.sidebar-collapsed") === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      window.localStorage.setItem("ai-drama.sidebar-collapsed", collapsed ? "1" : "0");
    } catch {
      // Local storage is an optional preference; navigation must still work.
    }
  }, [collapsed]);

  useEffect(() => {
    if (!activeProjectId) {
      setProjectName("");
      return;
    }
    getProject(activeProjectId)
      .then((project) => setProjectName(project.name))
      .catch(() => setProjectName(""));
  }, [activeProjectId]);

  const refreshNovels = useCallback(() => {
    if (!activeProjectId) {
      setNovels([]);
      setChapters({});
      setOpenNovelId(null);
      return;
    }
    listNovels(activeProjectId)
      .then(setNovels)
      .catch(() => setNovels([]));
  }, [activeProjectId]);

  useEffect(() => {
    refreshNovels();
  }, [refreshNovels]);

  // 小说/章节在模块内增删改后，侧栏树同步刷新
  useEffect(() => {
    function onNovelTreeChanged() {
      refreshNovels();
      if (!activeProjectId || !openNovelId) return;
      setBusyNovelId(openNovelId);
      getNovel(activeProjectId, openNovelId)
        .then((detail) =>
          setChapters((prev) => ({ ...prev, [openNovelId]: detail.chapters })),
        )
        .catch(() => setChapters((prev) => ({ ...prev, [openNovelId]: [] })))
        .finally(() => setBusyNovelId(null));
    }
    window.addEventListener("novel-tree-changed", onNovelTreeChanged);
    return () => window.removeEventListener("novel-tree-changed", onNovelTreeChanged);
  }, [refreshNovels, activeProjectId, openNovelId]);

  async function toggleNovel(novelId: string) {
    if (openNovelId === novelId) {
      setOpenNovelId(null);
      return;
    }
    setOpenNovelId(novelId);
    setBusyNovelId(novelId);
    try {
      const detail = await getNovel(activeProjectId, novelId);
      setChapters((prev) => ({ ...prev, [novelId]: detail.chapters }));
    } catch {
      setChapters((prev) => ({ ...prev, [novelId]: [] }));
    } finally {
      setBusyNovelId(null);
    }
  }

  return (
    <aside className={collapsed ? "app-sidebar is-collapsed" : "app-sidebar"}>
      <div className="sidebar-brand">
        {!collapsed && (
          <>
            <span className="sidebar-logo">AI Drama IDE</span>
            <span className="sidebar-version">Lite</span>
            {projectName && (
              <span className="sidebar-project-context" title={projectName}>
                {projectName}
              </span>
            )}
          </>
        )}
        <button
          type="button"
          className="sidebar-collapse"
          aria-label={collapsed ? "展开项目栏" : "收起项目栏"}
          aria-expanded={!collapsed}
          title={collapsed ? "展开项目栏" : "收起项目栏"}
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      {!collapsed &&
        (activeProjectId ? (
          <div className="sidebar-section sidebar-tree">
            <div className="sidebar-section-title">小说结构</div>
            {novels.length === 0 ? (
              <p className="sidebar-empty">该项目暂无小说</p>
            ) : (
              novels.map((novel) => {
                const open = openNovelId === novel.id;
                return (
                  <div key={novel.id} className="side-novel">
                    <div className="side-novel-row">
                      <button
                        type="button"
                        className="side-novel-toggle"
                        aria-label={open ? "收起章节" : "展开章节"}
                        onClick={() => void toggleNovel(novel.id)}
                      >
                        {busyNovelId === novel.id ? "…" : open ? "▾" : "▸"}
                      </button>
                      <button
                        type="button"
                        className="side-novel-title"
                        onClick={() => onJump({ novelId: novel.id })}
                      >
                        {novel.title || "未命名小说"}
                      </button>
                    </div>
                    {open && (
                      <div className="side-chapters">
                        {(chapters[novel.id] ?? []).length === 0 ? (
                          <p className="sidebar-empty">暂无章节</p>
                        ) : (
                          (chapters[novel.id] ?? []).map((ch, idx) => (
                            <button
                              key={ch.id}
                              type="button"
                              className="side-chapter"
                              onClick={() =>
                                onJump({ novelId: novel.id, chapterId: ch.id })
                              }
                            >
                              {ch.title || `第 ${idx + 1} 章`}
                            </button>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        ) : (
          <div className="sidebar-section">
            <div className="sidebar-section-title">项目</div>
            <p className="sidebar-empty">在「主页」打开或新建项目</p>
          </div>
        ))}
    </aside>
  );
}

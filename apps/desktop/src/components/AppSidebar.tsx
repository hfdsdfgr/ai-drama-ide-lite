import { useEffect, useState } from "react";

import { getNovel, listNovels } from "../api/novels";
import type { Chapter, Novel } from "../types/novel";

export interface NovelJump {
  novelId: string;
  chapterId?: string | null;
}

interface AppSidebarProps {
  activeProjectId: string;
  onJump: (target: NovelJump) => void;
}

export function AppSidebar({
  activeProjectId,
  onJump,
}: AppSidebarProps) {
  const [novels, setNovels] = useState<Novel[]>([]);
  const [chapters, setChapters] = useState<Record<string, Chapter[]>>({});
  const [openNovelId, setOpenNovelId] = useState<string | null>(null);
  const [busyNovelId, setBusyNovelId] = useState<string | null>(null);

  useEffect(() => {
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
    <aside className="app-sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-logo">AI Drama IDE</span>
        <span className="sidebar-version">Lite</span>
      </div>

      {activeProjectId ? (
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
      )}

    </aside>
  );
}

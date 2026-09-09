import { useState } from "react";

import { StatusBar } from "./components/StatusBar";
import { AppSidebar, type NovelJump } from "./components/AppSidebar";
import { AssetPage } from "./pages/AssetPage";
import { GenerationPage } from "./pages/GenerationPage";
import { NovelPage } from "./pages/NovelPage";
import { ProjectPage } from "./pages/ProjectPage";
import { ScriptPage } from "./pages/ScriptPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StoryboardPage } from "./pages/StoryboardPage";
import { StoryBiblePage } from "./pages/StoryBiblePage";
import "./App.css";

type View =
  | "project"
  | "novel"
  | "bible"
  | "script"
  | "storyboard"
  | "assets"
  | "generation"
  | "settings";

interface ModuleDef {
  key: string;
  label: string;
  ready: boolean;
}

// 一级创作模块导航；未就绪的模块预埋入口，后续 Phase 逐批启用。
const CREATION_MODULES: ModuleDef[] = [
  { key: "project", label: "主页", ready: true },
  { key: "novel", label: "小说", ready: true },
  { key: "bible", label: "故事圣经", ready: true },
  { key: "script", label: "剧本", ready: true },
  { key: "assets", label: "资产", ready: true },
  { key: "storyboard", label: "分镜", ready: true },
  { key: "generation", label: "生成中心", ready: true },
];

function App() {
  const [view, setView] = useState<View>("project");
  const [jumpToShotId, setJumpToShotId] = useState<string | null>(null);
  const [activeProjectId, setActiveProjectId] = useState("");
  const [novelJump, setNovelJump] = useState<NovelJump | null>(null);

  function handleJumpToShot(shotId: string) {
    setJumpToShotId(shotId);
    setView("storyboard");
  }

  function handleSelectProject(projectId: string) {
    setActiveProjectId(projectId);
    setNovelJump(null);
    setView("project");
  }

  function handleNovelJump(target: NovelJump) {
    setNovelJump(target);
    setView("novel");
  }

  return (
    <div className="app">
      <div className="app-shell">
        <AppSidebar activeProjectId={activeProjectId} onJump={handleNovelJump} />
        <div className="app-content">
          <header className="app-header">
            <nav className="module-nav" aria-label="主导航">
              {CREATION_MODULES.map((m) => (
                <button
                  key={m.key}
                  type="button"
                  className={view === m.key ? "nav-active" : ""}
                  aria-current={view === m.key ? "page" : undefined}
                  disabled={!m.ready}
                  title={m.ready ? "" : "该模块将在后续阶段开放"}
                  onClick={() => {
                    if (m.ready) setView(m.key as View);
                  }}
                >
                  {m.label}
                  {!m.ready && <span className="nav-soon">待建</span>}
                </button>
              ))}
            </nav>
            <div className="app-actions">
              <button
                type="button"
                aria-label="设置"
                title="设置"
                className={view === "settings" ? "nav-active" : ""}
                aria-current={view === "settings" ? "page" : undefined}
                onClick={() => setView("settings")}
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
                </svg>
              </button>
            </div>
          </header>
          <main className="app-main">
            <div className={view === "project" ? "view-pane active" : "view-pane"}>
              <ProjectPage
                openProjectId={activeProjectId}
                onSelectProject={handleSelectProject}
              />
            </div>
            <div className={view === "novel" ? "view-pane active" : "view-pane"}>
              <NovelPage
                active={view === "novel"}
                projectId={activeProjectId}
                jumpTo={
                  activeProjectId && novelJump
                    ? { projectId: activeProjectId, ...novelJump }
                    : null
                }
              />
            </div>
            <div className={view === "bible" ? "view-pane active" : "view-pane"}>
              <StoryBiblePage active={view === "bible"} projectId={activeProjectId} />
            </div>
            <div className={view === "script" ? "view-pane active" : "view-pane"}>
              <ScriptPage active={view === "script"} projectId={activeProjectId} />
            </div>
            <div className={view === "storyboard" ? "view-pane active" : "view-pane"}>
              <StoryboardPage
                active={view === "storyboard"}
                projectId={activeProjectId}
                jumpToShotId={view === "storyboard" ? jumpToShotId : null}
                onJumpConsumed={() => setJumpToShotId(null)}
              />
            </div>
            <div className={view === "assets" ? "view-pane active" : "view-pane"}>
              <AssetPage
                active={view === "assets"}
                projectId={activeProjectId}
                onOpenStoryboard={() => setView("storyboard")}
              />
            </div>
            <div className={view === "generation" ? "view-pane active" : "view-pane"}>
              <GenerationPage
                active={view === "generation"}
                projectId={activeProjectId}
                onJumpToShot={handleJumpToShot}
              />
            </div>
            <div className={view === "settings" ? "view-pane active" : "view-pane"}>
              <SettingsPage />
            </div>
          </main>
          <StatusBar />
        </div>
      </div>
    </div>
  );
}

export default App;

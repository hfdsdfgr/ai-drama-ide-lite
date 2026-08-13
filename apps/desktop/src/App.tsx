import { useState } from "react";

import { StatusBar } from "./components/StatusBar";
import { NovelPage } from "./pages/NovelPage";
import { ProjectPage } from "./pages/ProjectPage";
import { SettingsPage } from "./pages/SettingsPage";
import "./App.css";

type View = "project" | "novel" | "settings";

interface ModuleDef {
  key: string;
  label: string;
  ready: boolean;
}

// 一级创作模块导航；未就绪的模块预埋入口，后续 Phase 逐批启用。
const CREATION_MODULES: ModuleDef[] = [
  { key: "project", label: "主页", ready: true },
  { key: "novel", label: "小说", ready: true },
  { key: "bible", label: "故事圣经", ready: false },
  { key: "script", label: "剧本", ready: false },
  { key: "character", label: "角色", ready: false },
  { key: "scene", label: "场景", ready: false },
  { key: "storyboard", label: "分镜", ready: false },
  { key: "generation", label: "生成中心", ready: false },
];

function App() {
  const [view, setView] = useState<View>("project");

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-brand">
          <span className="app-logo">AI Drama IDE</span>
          <span className="app-version">Lite</span>
        </div>
        <nav className="module-nav" aria-label="主导航">
          {CREATION_MODULES.map((m) => (
            <button
              key={m.key}
              type="button"
              className={view === m.key ? "nav-active" : ""}
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
            className={view === "settings" ? "nav-active" : ""}
            onClick={() => setView("settings")}
          >
            设置
          </button>
        </div>
      </header>
      <main className="app-main">
        {view === "project" && <ProjectPage />}
        {view === "novel" && <NovelPage />}
        {view === "settings" && <SettingsPage />}
      </main>
      <StatusBar />
    </div>
  );
}

export default App;

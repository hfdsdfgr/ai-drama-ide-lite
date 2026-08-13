import { useState } from "react";

import { ProjectPage } from "./pages/ProjectPage";
import { SettingsPage } from "./pages/SettingsPage";
import "./App.css";

type View = "project" | "settings";

function App() {
  const [view, setView] = useState<View>("project");

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Drama IDE Lite</h1>
        <nav>
          <button
            type="button"
            className={view === "project" ? "nav-active" : ""}
            onClick={() => setView("project")}
          >
            项目
          </button>
          <button
            type="button"
            className={view === "settings" ? "nav-active" : ""}
            onClick={() => setView("settings")}
          >
            设置
          </button>
        </nav>
      </header>
      <main>{view === "project" ? <ProjectPage /> : <SettingsPage />}</main>
    </div>
  );
}

export default App;

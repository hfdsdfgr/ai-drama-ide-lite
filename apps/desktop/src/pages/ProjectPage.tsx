import { useCallback, useEffect, useState } from "react";

import {
  createProject,
  deleteProject,
  exportProject,
  importProject,
  listProjects,
  updateProject,
} from "../api/projects";
import type { Project } from "../types/project";

export function ProjectPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Project | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveState, setSaveState] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setProjects(await listProjects());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // 自动保存：描述编辑停止 800ms 后自动保存
  useEffect(() => {
    if (!selected || draft === selected.description) return;
    setSaveState("saving");
    const timer = setTimeout(async () => {
      try {
        const updated = await updateProject(selected.id, { description: draft });
        setSelected(updated);
        setProjects((prev) =>
          prev.map((p) => (p.id === updated.id ? updated : p)),
        );
        setSaveState("saved");
      } catch (err) {
        setSaveState("error");
        setError((err as Error).message);
      }
    }, 800);
    return () => clearTimeout(timer);
  }, [draft, selected]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const project = await createProject({ name, description });
      setProjects((prev) => [project, ...prev]);
      setName("");
      setDescription("");
      setSelected(project);
      setDraft(project.description);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function handleOpen(project: Project) {
    setSelected(project);
    setDraft(project.description);
    setError("");
  }

  async function handleSave() {
    if (!selected) return;
    setSaving(true);
    setError("");
    try {
      const updated = await updateProject(selected.id, { description: draft });
      setSelected(updated);
      setSaveState("saved");
      setProjects((prev) =>
        prev.map((p) => (p.id === updated.id ? updated : p)),
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selected) return;
    if (!window.confirm(`确定删除项目「${selected.name}」？此操作不可撤销。`)) {
      return;
    }
    setError("");
    try {
      await deleteProject(selected.id);
      setProjects((prev) => prev.filter((p) => p.id !== selected.id));
      setSelected(null);
      setDraft("");
      setSaveState("idle");
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
      const project = await importProject(file);
      setProjects((prev) => [project, ...prev]);
      setSelected(project);
      setDraft(project.description);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleExport() {
    if (!selected) return;
    setError("");
    try {
      await exportProject(selected.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <h2>项目</h2>
        <div className="toolbar">
          <input
            type="file"
            id="project-import-input"
            accept=".zip"
            style={{ display: "none" }}
            onChange={handleImport}
          />
          <label htmlFor="project-import-input" className="button-like">
            导入项目
          </label>
        </div>
      </div>

      <form className="card" onSubmit={handleCreate}>
        <h3>新建项目</h3>
        <label>
          名称
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：我的第一部漫剧"
            required
          />
        </label>
        <label>
          描述
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="一句话介绍这个故事（可选）"
            rows={2}
          />
        </label>
        <button type="submit">创建</button>
      </form>

      {error && <p className="error">{error}</p>}

      <div className="card">
        <h3>打开项目</h3>
        {loading ? (
          <p>加载中…</p>
        ) : projects.length === 0 ? (
          <p className="muted">还没有项目，先创建一个。</p>
        ) : (
          <ul className="project-list">
            {projects.map((project) => (
              <li key={project.id}>
                <button
                  type="button"
                  className="project-item"
                  onClick={() => handleOpen(project)}
                >
                  <span className="project-name">{project.name}</span>
                  <span className="muted">
                    更新于{" "}
                    {new Date(project.updated_at).toLocaleString("zh-CN")}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {selected && (
        <div className="card">
          <h3>当前项目：{selected.name}</h3>
          <label>
            描述
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={3}
            />
          </label>
          <button type="button" onClick={handleSave} disabled={saving}>
            {saving ? "保存中…" : "保存"}
          </button>
          <div className="actions">
            <button type="button" onClick={handleExport}>
              导出项目
            </button>
            <button
              type="button"
              className="button-danger"
              onClick={handleDelete}
            >
              删除项目
            </button>
            <span className="muted save-status">
              {saveState === "saving" && "自动保存中…"}
              {saveState === "saved" && "已保存"}
              {saveState === "error" && "保存失败"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

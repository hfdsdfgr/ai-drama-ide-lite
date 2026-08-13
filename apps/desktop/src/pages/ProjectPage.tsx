import { useCallback, useEffect, useState } from "react";

import { createProject, listProjects, updateProject } from "../api/projects";
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
      setProjects((prev) =>
        prev.map((p) => (p.id === updated.id ? updated : p)),
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <h2>项目</h2>

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
        </div>
      )}
    </div>
  );
}

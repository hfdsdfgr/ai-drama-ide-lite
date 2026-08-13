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
  const [nameDraft, setNameDraft] = useState("");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
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

  // 自动保存：名称/描述编辑停止 800ms 后自动保存
  useEffect(() => {
    if (!selected) return;
    if (nameDraft === selected.name && draft === selected.description) return;
    setSaveState("saving");
    const timer = setTimeout(async () => {
      try {
        const updated = await updateProject(selected.id, {
          ...(nameDraft === selected.name ? {} : { name: nameDraft }),
          ...(draft === selected.description ? {} : { description: draft }),
        });
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
  }, [nameDraft, draft, selected]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const project = await createProject({ name, description });
      setProjects((prev) => [project, ...prev]);
      setName("");
      setDescription("");
      setSelected(project);
      setNameDraft(project.name);
      setDraft(project.description);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function handleOpen(project: Project) {
    setSelected(project);
    setNameDraft(project.name);
    setDraft(project.description);
    setConfirmDeleteId(null);
    setError("");
  }

  function handleNew() {
    setSelected(null);
    setNameDraft("");
    setDraft("");
    setConfirmDeleteId(null);
    setError("");
  }

  async function handleSave() {
    if (!selected) return;
    setSaving(true);
    setError("");
    try {
      const updated = await updateProject(selected.id, {
        name: nameDraft,
        description: draft,
      });
      setProjects((prev) =>
        prev.map((p) => (p.id === updated.id ? updated : p)),
      );
      setSelected(null);
      setNameDraft("");
      setDraft("");
      setSaveState("idle");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(project: Project) {
    if (confirmDeleteId !== project.id) {
      setConfirmDeleteId(project.id);
      return;
    }
    setConfirmDeleteId(null);
    setError("");
    try {
      await deleteProject(project.id);
      setProjects((prev) => prev.filter((p) => p.id !== project.id));
      if (selected?.id === project.id) {
        setSelected(null);
        setNameDraft("");
        setDraft("");
        setSaveState("idle");
      }
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
      setNameDraft(project.name);
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
        <h2>主页</h2>
        <div className="toolbar">
          <button type="button" onClick={handleNew}>
            新建项目
          </button>
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

      {error && <p className="error">{error}</p>}

      <div className="project-workspace">
        <aside className="sidebar-block project-pane">
          <h3>项目</h3>
          {loading ? (
            <p>加载中…</p>
          ) : projects.length === 0 ? (
            <p className="muted">还没有项目，点右上角「新建项目」创建一个。</p>
          ) : (
            <ul className="project-list">
              {projects.map((project) => (
                <li key={project.id}>
                  <div
                    className={
                      selected?.id === project.id
                        ? "project-row active"
                        : "project-row"
                    }
                  >
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
                    {confirmDeleteId === project.id ? (
                      <div className="project-actions">
                        <button
                          type="button"
                          className="button-danger"
                          onClick={() => handleDelete(project)}
                        >
                          确认
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(null)}
                        >
                          取消
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="button-danger"
                        onClick={() => handleDelete(project)}
                      >
                        删除
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section className="card project-detail">
          {selected ? (
            <>
              <h3>项目详情</h3>
              <label>
                名称
                <input
                  value={nameDraft}
                  onChange={(e) => setNameDraft(e.target.value)}
                  placeholder="项目名称"
                />
              </label>
              <label>
                描述
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={4}
                />
              </label>
              <div className="actions">
                <button type="button" onClick={handleSave} disabled={saving}>
                  {saving ? "保存中…" : "保存"}
                </button>
                <button type="button" onClick={handleExport}>
                  导出项目
                </button>
                {confirmDeleteId === selected.id ? (
                  <>
                    <button
                      type="button"
                      className="button-danger"
                      onClick={() => handleDelete(selected)}
                    >
                      确认删除
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDeleteId(null)}
                    >
                      取消
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="button-danger"
                    onClick={() => handleDelete(selected)}
                  >
                    删除项目
                  </button>
                )}
                <span className="muted save-status">
                  {saveState === "saving" && "自动保存中…"}
                  {saveState === "saved" && "已保存"}
                  {saveState === "error" && "保存失败"}
                </span>
              </div>
            </>
          ) : (
            <form onSubmit={handleCreate}>
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
                  rows={3}
                />
              </label>
              <button type="submit">创建</button>
            </form>
          )}
        </section>
      </div>
    </div>
  );
}

import { useCallback, useEffect, useState } from "react";

import { getNovel, listNovels } from "../api/novels";
import { listProjects } from "../api/projects";
import { listModels } from "../api/providers";
import {
  generateEpisodeScript,
  generateShots,
  getEpisodeDetail,
  listEpisodes,
  deleteEpisode,
  saveEpisodeScript,
  saveSceneShots,
  updateScene,
} from "../api/script";
import type { Model } from "../types/provider";
import type { Chapter, Novel } from "../types/novel";
import type { Project } from "../types/project";
import type {
  AiEpisodeScriptResult,
  AiShotsResult,
  Episode,
  EpisodeDetail,
  Scene,
} from "../types/script";

// 虽然分类为 llm，但这些模型不是「文本创作」模型，不用于剧本生成
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

export function ScriptPage({ active }: { active: boolean }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novelId, setNovelId] = useState("");
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(null);
  const [episodeDetail, setEpisodeDetail] = useState<EpisodeDetail | null>(null);
  const [llmModels, setLlmModels] = useState<Model[]>([]);
  const [aiModelId, setAiModelId] = useState("");
  const [shotModelId, setShotModelId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [chapterIndex, setChapterIndex] = useState(0);
  const [scriptInstruction, setScriptInstruction] = useState("");
  const [scriptPreview, setScriptPreview] =
    useState<AiEpisodeScriptResult | null>(null);
  const [genBusy, setGenBusy] = useState(false);

  const [shotSceneId, setShotSceneId] = useState<string | null>(null);
  const [shotInstruction, setShotInstruction] = useState("");
  const [shotPreview, setShotPreview] = useState<AiShotsResult | null>(null);
  const [shotBusy, setShotBusy] = useState(false);
  const [editingSceneId, setEditingSceneId] = useState<string | null>(null);
  const [sceneDraft, setSceneDraft] = useState<{
    slugline: string;
    action: string;
    dialogue: string;
  } | null>(null);
  const [confirmEpisodeDeleteId, setConfirmEpisodeDeleteId] = useState<
    string | null
  >(null);

  useEffect(() => {
    if (!active) return;
    listProjects()
      .then(setProjects)
      .catch((e) => setError((e as Error).message));
    listModels({ model_type: "llm", enabled_only: true })
      .then((models) => {
        const usable = models.filter(isChatModel);
        setLlmModels(usable);
        setAiModelId((prev) =>
          usable.some((m) => m.id === prev) ? prev : (usable[0]?.id ?? ""),
        );
        setShotModelId((prev) =>
          usable.some((m) => m.id === prev) ? prev : (usable[0]?.id ?? ""),
        );
      })
      .catch((e) => setError((e as Error).message));
  }, [active]);

  const refreshNovels = useCallback(async (pid: string) => {
    setError("");
    try {
      setNovels(await listNovels(pid));
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    if (!projectId) return;
    setNovelId("");
    setEpisodes([]);
    setEpisodeDetail(null);
    void refreshNovels(projectId);
  }, [projectId, refreshNovels]);

  useEffect(() => {
    if (!projectId || !novelId) return;
    setChapters([]);
    setEpisodes([]);
    setEpisodeDetail(null);
    setScriptPreview(null);
    getNovel(projectId, novelId)
      .then((d) => setChapters(d.chapters))
      .catch((e) => setError((e as Error).message));
    listEpisodes(projectId, novelId)
      .then(setEpisodes)
      .catch((e) => setError((e as Error).message));
  }, [projectId, novelId]);

  const loadEpisodeDetail = useCallback(
    async (episodeId: string) => {
      if (!projectId) return;
      setError("");
      try {
        const detail = await getEpisodeDetail(projectId, episodeId);
        setEpisodeDetail(detail);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [projectId],
  );

  async function selectEpisode(episodeId: string) {
    setSelectedEpisodeId(episodeId);
    setShotPreview(null);
    await loadEpisodeDetail(episodeId);
  }

  async function generateScript() {
    if (!projectId || !novelId || !aiModelId) return;
    setGenBusy(true);
    setError("");
    try {
      const result = await generateEpisodeScript(projectId, {
        novel_id: novelId,
        model_id: aiModelId,
        chapter_index: chapterIndex,
        user_instruction: scriptInstruction,
      });
      setScriptPreview(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenBusy(false);
    }
  }

  async function saveScript() {
    if (!projectId || !novelId || !scriptPreview) return;
    setGenBusy(true);
    setError("");
    try {
      const detail = await saveEpisodeScript(projectId, {
        novel_id: novelId,
        chapter_index: chapterIndex,
        episode: scriptPreview.episode,
        scenes: scriptPreview.scenes,
      });
      setScriptPreview(null);
      const list = await listEpisodes(projectId, novelId);
      setEpisodes(list);
      await selectEpisode(detail.episode.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenBusy(false);
    }
  }

  async function generateSceneShots(sceneId: string) {
    if (!projectId || !shotModelId) return;
    setShotBusy(true);
    setError("");
    try {
      const result = await generateShots(projectId, sceneId, {
        model_id: shotModelId,
        scene_id: sceneId,
        user_instruction: shotInstruction,
      });
      setShotSceneId(sceneId);
      setShotPreview(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setShotBusy(false);
    }
  }

  async function saveShots(sceneId: string) {
    if (!projectId || !shotPreview) return;
    setShotBusy(true);
    setError("");
    try {
      await saveSceneShots(projectId, sceneId, {
        shots: shotPreview.shots,
      });
      setShotPreview(null);
      setShotSceneId(null);
      setNotice("分镜已保存，请前往「分镜」模块查看和编辑。");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setShotBusy(false);
    }
  }

  function startEditScene(scene: Scene) {
    setEditingSceneId(scene.id);
    setSceneDraft({
      slugline: scene.slugline,
      action: scene.action,
      dialogue: scene.dialogue,
    });
  }

  async function saveSceneEdit(sceneId: string) {
    if (!projectId || !sceneDraft || !selectedEpisodeId) return;
    setError("");
    try {
      await updateScene(projectId, sceneId, sceneDraft);
      await loadEpisodeDetail(selectedEpisodeId);
      setEditingSceneId(null);
      setSceneDraft(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleDeleteEpisode(episodeId: string) {
    if (!projectId) return;
    if (confirmEpisodeDeleteId !== episodeId) {
      setConfirmEpisodeDeleteId(episodeId);
      return;
    }
    setConfirmEpisodeDeleteId(null);
    setError("");
    try {
      await deleteEpisode(projectId, episodeId);
      const list = await listEpisodes(projectId, novelId);
      setEpisodes(list);
      if (selectedEpisodeId === episodeId) {
        setSelectedEpisodeId(null);
        setEpisodeDetail(null);
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="page script-page">
      {error && <p className="error">{error}</p>}
      {notice && <p className="ok">{notice}</p>}

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
            <div className="sidebar-head">
              <h3>小说</h3>
            </div>
            <select
              className="project-select"
              value={novelId}
              onChange={(e) => setNovelId(e.target.value)}
              disabled={!projectId}
            >
              <option value="">选择小说</option>
              {novels.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.title}
                </option>
              ))}
            </select>
          </div>

          <div className="sidebar-block">
            <div className="sidebar-head">
              <h3>分集</h3>
            </div>
            {!novelId ? (
              <p className="muted">先选择项目和小说。</p>
            ) : episodes.length === 0 ? (
              <p className="muted">还没有分集，用右侧「生成剧本」创建。</p>
            ) : (
              <ul className="chapter-tree">
                {episodes.map((ep) => (
                  <li key={ep.id}>
                    <div className="chapter-row">
                      <button
                        type="button"
                        className={
                          ep.id === selectedEpisodeId
                            ? "chapter-item active"
                            : "chapter-item"
                        }
                        onClick={() => selectEpisode(ep.id)}
                      >
                        {ep.title || "未命名分集"}
                      </button>
                      {confirmEpisodeDeleteId === ep.id ? (
                        <span className="chapter-row-actions">
                          <button
                            type="button"
                            className="button-danger"
                            onClick={() => handleDeleteEpisode(ep.id)}
                          >
                            确认
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmEpisodeDeleteId(null)}
                          >
                            取消
                          </button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          className="chapter-delete"
                          title="删除分集"
                          onClick={() => handleDeleteEpisode(ep.id)}
                        >
                          ×
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        <section className="novel-main">
          {episodeDetail ? (
            <>
              <div className="panel-head">
                <h3>{episodeDetail.episode.title}</h3>
                <p className="muted">{episodeDetail.episode.summary}</p>
              </div>
              {episodeDetail.scenes.length === 0 ? (
                <p className="muted">本分集还没有场景。</p>
              ) : (
                episodeDetail.scenes.map((scene) => {
                  return (
                    <div className="card" key={scene.id}>
                      <div className="scene-head">
                        <strong>{scene.slugline || scene.title}</strong>
                        <div className="toolbar">
                          <button
                            type="button"
                            disabled={shotBusy || !shotModelId}
                            onClick={() => generateSceneShots(scene.id)}
                          >
                            {shotBusy && shotSceneId === scene.id
                              ? "正在生成分镜…"
                              : "生成分镜"}
                          </button>
                          {editingSceneId === scene.id ? (
                            <button
                              type="button"
                              onClick={() => {
                                setEditingSceneId(null);
                                setSceneDraft(null);
                              }}
                            >
                              取消
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => startEditScene(scene)}
                            >
                              编辑
                            </button>
                          )}
                        </div>
                      </div>
                      {shotBusy && shotSceneId === scene.id && (
                        <p className="muted">
                          正在生成分镜，通常需要 1-3 分钟，请稍候…
                        </p>
                      )}
                      {editingSceneId === scene.id && sceneDraft ? (
                        <div className="wizard-preview">
                          <label>
                            场景标题（slugline）
                            <input
                              value={sceneDraft.slugline}
                              onChange={(e) =>
                                setSceneDraft({
                                  ...sceneDraft,
                                  slugline: e.target.value,
                                })
                              }
                              placeholder="室内·地点·日/夜"
                            />
                          </label>
                          <label>
                            动作
                            <textarea
                              value={sceneDraft.action}
                              onChange={(e) =>
                                setSceneDraft({
                                  ...sceneDraft,
                                  action: e.target.value,
                                })
                              }
                              rows={3}
                            />
                          </label>
                          <label>
                            台词
                            <textarea
                              value={sceneDraft.dialogue}
                              onChange={(e) =>
                                setSceneDraft({
                                  ...sceneDraft,
                                  dialogue: e.target.value,
                                })
                              }
                              rows={3}
                            />
                          </label>
                          <div className="toolbar">
                            <button
                              type="button"
                              className="btn-primary"
                              onClick={() => saveSceneEdit(scene.id)}
                            >
                              保存
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          {scene.action && <p className="muted">{scene.action}</p>}
                          {scene.dialogue && (
                            <pre className="scene-dialogue">{scene.dialogue}</pre>
                          )}
                        </>
                      )}
                      {shotPreview && shotSceneId === scene.id && (
                        <div className="shots-preview">
                          <h4>分镜预览（{shotPreview.shots.length} 个镜头）</h4>
                          <ol className="shot-list">
                            {shotPreview.shots.map((shot, i) => (
                              <li key={i}>
                                <strong>
                                  {shot.shot_type} · {shot.duration}s
                                </strong>
                                {shot.camera && <span> {shot.camera}</span>}
                                <p className="muted">{shot.action}</p>
                                {shot.dialogue && (
                                  <p className="shot-dialogue">{shot.dialogue}</p>
                                )}
                              </li>
                            ))}
                          </ol>
                          <div className="toolbar">
                            <button
                              type="button"
                              className="btn-primary"
                              disabled={shotBusy}
                              onClick={() => saveShots(scene.id)}
                            >
                              保存分镜
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setShotPreview(null);
                                setShotSceneId(null);
                              }}
                            >
                              放弃
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </>
          ) : scriptPreview ? (
            <>
              <div className="panel-head">
                <h3>
                  {scriptPreview.episode.title}
                  <span className="badge badge-default">待保存</span>
                </h3>
                <p className="muted">{scriptPreview.episode.summary}</p>
              </div>
              <p className="muted">
                这是 AI 生成的剧本预览，确认后点右侧「保存剧本」写入项目。
              </p>
              {scriptPreview.scenes.length === 0 ? (
                <p className="muted">本分集还没有场景。</p>
              ) : (
                scriptPreview.scenes.map((scene, i) => (
                  <div className="card" key={i}>
                    <div className="scene-head">
                      <strong>{scene.slugline || scene.title}</strong>
                    </div>
                    {scene.action && <p className="muted">{scene.action}</p>}
                    {scene.dialogue && (
                      <pre className="scene-dialogue">{scene.dialogue}</pre>
                    )}
                  </div>
                ))
              )}
            </>
          ) : (
            <div className="novel-empty">
              <p className="muted">
                {!novelId
                  ? "先选择项目和小说，再用右侧「生成剧本」创建分集。"
                  : "从左侧选择分集，或用右侧「生成剧本」创建。"}
              </p>
            </div>
          )}
        </section>

        <aside className="novel-inspector">
          <div className="panel-head">
            <h3>AI 助手</h3>
            <p className="muted">章节 → 分集剧本 → 场景分镜</p>
          </div>
          <div className="card inspector-card">
            <h3>生成剧本</h3>
            {llmModels.length === 0 && (
              <p className="muted">
                没有可用的文本模型。请在「设置」中启用至少一个文本模型，
                并确认其 Provider 已启用（Provider 和模型需要同时启用）。
              </p>
            )}
            <label>
              文本模型
              <select
                value={aiModelId}
                onChange={(e) => setAiModelId(e.target.value)}
                disabled={llmModels.length === 0}
              >
                {llmModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.model_id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              章节
              <select
                value={chapterIndex}
                onChange={(e) => setChapterIndex(Number(e.target.value))}
                disabled={!novelId || chapters.length === 0}
              >
                {chapters.map((c, i) => (
                  <option key={c.id} value={i}>
                    {c.title || `第 ${i + 1} 章`}
                  </option>
                ))}
              </select>
            </label>
            <label>
              对剧本的要求（可留空）
              <textarea
                value={scriptInstruction}
                onChange={(e) => setScriptInstruction(e.target.value)}
                rows={3}
                placeholder="例如：节奏快一点 / 突出主角成长 / 减少配角戏份"
              />
            </label>
            {scriptPreview ? (
              <div className="wizard-preview">
                <p className="ok">
                  剧本已生成：{scriptPreview.episode.title}（
                  {scriptPreview.scenes.length} 个场景），完整预览已显示在中栏。
                </p>
                <div className="toolbar">
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={genBusy}
                    onClick={saveScript}
                  >
                    保存剧本
                  </button>
                  <button
                    type="button"
                    onClick={() => setScriptPreview(null)}
                  >
                    放弃
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="btn-primary"
                disabled={
                  !projectId || !novelId || !aiModelId || genBusy || chapters.length === 0
                }
                onClick={generateScript}
              >
                {genBusy ? "生成中…" : "生成剧本"}
              </button>
            )}
          </div>

          <div className="card inspector-card">
            <h3>生成分镜</h3>
            {llmModels.length === 0 && (
              <p className="muted">没有可用的文本模型。</p>
            )}
            <label>
              文本模型
              <select
                value={shotModelId}
                onChange={(e) => setShotModelId(e.target.value)}
                disabled={llmModels.length === 0}
              >
                {llmModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.model_id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              对分镜的要求（可留空）
              <textarea
                value={shotInstruction}
                onChange={(e) => setShotInstruction(e.target.value)}
                rows={2}
                placeholder="例如：多用特写 / 慢镜头"
              />
            </label>
            <p className="muted">在左侧场景卡片上点「生成分镜」开始。</p>
            {shotPreview && shotSceneId && (
              <p className="ok">
                已生成 {shotPreview.shots.length} 个镜头，预览在中栏场景卡片内。
              </p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";

import { listNovels } from "../api/novels";
import { listProjects } from "../api/projects";
import { listModels } from "../api/providers";
import {
  getStoryAnalysis,
  getStoryBible,
  startStoryAnalysis,
} from "../api/story";
import type { Model } from "../types/provider";
import type { Novel } from "../types/novel";
import type { Project } from "../types/project";
import type {
  AnalysisJob,
  AnalysisMode,
  StoryBible,
} from "../types/story";

// 虽然分类为 llm，但这些模型不是「文本创作」模型，不用于故事分析
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

export function StoryBiblePage({ active }: { active: boolean }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novelId, setNovelId] = useState("");
  const [bible, setBible] = useState<StoryBible | null>(null);
  const [analysisJob, setAnalysisJob] = useState<AnalysisJob | null>(null);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [llmModels, setLlmModels] = useState<Model[]>([]);
  const [aiModelId, setAiModelId] = useState("");
  const [error, setError] = useState("");
  const analysisPollRef = useRef<string | null>(null);

  // 模型与项目是全局配置；页面常驻挂载，只有切到本页（active）才加载，
  // 避免应用启动时后端尚未就绪导致请求失败后永不重试。
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
    setBible(null);
    void refreshNovels(projectId);
  }, [projectId, refreshNovels]);

  useEffect(() => {
    if (!projectId || !novelId) return;
    setBible(null);
    getStoryBible(projectId)
      .then((r) => setBible(r.bible))
      .catch((e) => setError((e as Error).message));
  }, [projectId, novelId]);

  async function runAnalysis(mode: AnalysisMode) {
    if (!projectId || !novelId || !aiModelId) return;
    setAnalysisBusy(true);
    setError("");
    try {
      const job = await startStoryAnalysis(projectId, novelId, aiModelId, mode);
      setAnalysisJob(job);
      analysisPollRef.current = job.job_id;
      while (analysisPollRef.current === job.job_id) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        if (analysisPollRef.current !== job.job_id) break;
        const updated = await getStoryAnalysis(projectId, job.job_id);
        setAnalysisJob(updated);
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          analysisPollRef.current = null;
          if (updated.status === "completed") {
            const bibleResult = await getStoryBible(projectId);
            setBible(bibleResult.bible);
          }
          break;
        }
      }
    } catch (err) {
      setError((err as Error).message);
      analysisPollRef.current = null;
    } finally {
      setAnalysisBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="page-head">
        <h2>故事圣经</h2>
      </div>

      <div className="toolbar">
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
        <label>
          小说
          <select
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
        </label>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="card">
        <div className="panel-head">
          <h3>Story Bible</h3>
          <p className="muted">
            项目长期设定：世界观、人物、地点、时间线。AI 写作会以它为设定依据。
          </p>
        </div>
        {llmModels.length === 0 ? (
          <p className="muted">
            没有可用的文本模型。请在「设置」中启用至少一个文本模型，
            并确认其 Provider 已启用（Provider 和模型需要同时启用）。
          </p>
        ) : (
          <>
            <div className="toolbar">
              <button
                type="button"
                className="btn-primary"
                disabled={!projectId || !novelId || analysisBusy}
                onClick={() => runAnalysis("full")}
              >
                分析故事
              </button>
              <button
                type="button"
                disabled={!projectId || !novelId || analysisBusy || !bible}
                onClick={() => runAnalysis("merge")}
              >
                增量合并新章节
              </button>
              {analysisJob && (
                <span className="muted">
                  {analysisJob.detail}
                  {analysisJob.progress != null &&
                    `（${Math.round(analysisJob.progress * 100)}%）`}
                </span>
              )}
            </div>
            {analysisJob?.error && <p className="error">{analysisJob.error}</p>}
            {!novelId && (
              <p className="muted">先选择项目和小说，再进行分析。</p>
            )}
            {bible ? (
              <div className="bible">
                {bible.synopsis && <p>{bible.synopsis}</p>}
                {bible.characters.length > 0 && (
                  <div className="bible-section">
                    <h4>角色</h4>
                    <ul>
                      {bible.characters.map((c) => (
                        <li key={c.name}>
                          <strong>{c.name}</strong>
                          {c.role_hint ? `（${c.role_hint}）` : ""} {c.summary}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {bible.locations.length > 0 && (
                  <div className="bible-section">
                    <h4>地点</h4>
                    <ul>
                      {bible.locations.map((l) => (
                        <li key={l.name}>
                          <strong>{l.name}</strong> {l.description}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {bible.props.length > 0 && (
                  <div className="bible-section">
                    <h4>道具</h4>
                    <ul>
                      {bible.props.map((p) => (
                        <li key={p.name}>
                          <strong>{p.name}</strong> {p.description}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {bible.events.length > 0 && (
                  <div className="bible-section">
                    <h4>时间线</h4>
                    <ol>
                      {bible.events.map((e, i) => (
                        <li key={i}>
                          第 {e.chapter_index + 1} 章：{e.summary}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
                {bible.conflicts.length > 0 && (
                  <div className="bible-section">
                    <h4>主要冲突</h4>
                    <ul>
                      {bible.conflicts.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {bible.plotlines.length > 0 && (
                  <div className="bible-section">
                    <h4>情节线</h4>
                    <ul>
                      {bible.plotlines.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {bible.foreshadowing.length > 0 && (
                  <div className="bible-section">
                    <h4>伏笔</h4>
                    <ul>
                      {bible.foreshadowing.map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              novelId && (
                <p className="muted">
                  还没有 Story Bible。点击「分析故事」从当前小说提取角色、地点、道具与事件。
                </p>
              )
            )}
          </>
        )}
      </div>
    </div>
  );
}

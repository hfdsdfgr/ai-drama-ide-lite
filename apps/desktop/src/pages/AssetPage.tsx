import { useCallback, useEffect, useRef, useState } from "react";

import {
  deleteAsset,
  getAssetGeneration,
  getAssetSpecs,
  listAssets,
  startAssetGeneration,
  updateAsset,
} from "../api/assets";
import {
  deleteAssetVersion,
  listAssetVersions,
  promoteAssetVersion,
} from "../api/asset_versions";
import { getApiBase } from "../api/client";
import { listProjects } from "../api/projects";
import { listModels } from "../api/providers";
import type { AssetVersion } from "../types/asset_version";
import type { Model } from "../types/provider";
import type { Project } from "../types/project";
import type {
  AssetCard,
  AssetGenerateJob,
  AssetSpecs,
  AssetType,
} from "../types/story";

interface FieldDef {
  key: string;
  label: string;
  placeholder: string;
  rows?: number;
}

const FIELD_SETS: Record<AssetType, FieldDef[]> = {
  character: [
    {
      key: "identity",
      label: "身份标签",
      placeholder: "身份 / 年龄 / 阵营，如：男主，18 岁，青云镇少年",
    },
    {
      key: "appearance",
      label: "面部特征",
      placeholder: "脸型、五官、瞳色、肤色——3-4 个关键特征最有效",
    },
    {
      key: "hairstyle",
      label: "发型发色",
      placeholder: "长度 / 发型 / 发色，必须明确，防止漂移",
    },
    {
      key: "costume",
      label: "服装配饰",
      placeholder: "具体单品、颜色、材质、层次，越具体越稳定",
    },
    { key: "build", label: "体型姿态", placeholder: "体态 / 身高 / 姿势习惯" },
    {
      key: "marks",
      label: "特殊标记",
      placeholder: "泪痣 / 耳钉 / 疤痕 / 纹身——一致性锚点",
    },
    {
      key: "personality",
      label: "性格标签",
      placeholder: "3-5 个关键词，供剧情与表演使用",
    },
    {
      key: "style",
      label: "风格参考",
      placeholder: "写实 / 动漫 / 国风 / 赛博，全剧统一",
    },
  ],
  location: [
    {
      key: "description",
      label: "概述",
      placeholder: "该场景的一句话概括",
    },
    {
      key: "environment",
      label: "环境描述",
      placeholder: "建筑、地貌、细节元素",
    },
    {
      key: "time",
      label: "时间段",
      placeholder: "白天 / 黄昏 / 夜晚 / 具体时刻",
    },
    {
      key: "lighting",
      label: "光线",
      placeholder: "自然光 / 烛光 / 霓虹，氛围",
    },
    {
      key: "style",
      label: "视觉风格",
      placeholder: "写实 / 动漫 / 国风 / 赛博",
    },
  ],
  prop: [
    {
      key: "description",
      label: "概述",
      placeholder: "道具是什么、在剧情中的作用",
    },
    {
      key: "material",
      label: "材质",
      placeholder: "白玉 / 金属 / 皮革…",
    },
    {
      key: "reference",
      label: "参考 / 用途",
      placeholder: "谁使用、何时出现、参考来源",
    },
  ],
};

const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  character: "角色",
  location: "场景",
  prop: "道具",
};

// 虽然分类为 llm，但这些模型不是「文本创作」模型，不用于资产卡生成
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

function buildDraft(asset: AssetCard): Record<string, string> {
  const fields = asset.fields as unknown as Record<string, unknown>;
  const draft: Record<string, string> = {
    reference_prompt: asset.reference_prompt,
    aspect_ratio: String(fields["aspect_ratio"] ?? ""),
    art_style: String(fields["art_style"] ?? ""),
  };
  for (const field of FIELD_SETS[asset.asset_type]) {
    draft[field.key] = String(fields[field.key] ?? "");
  }
  return draft;
}

function formatVersionTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function AssetPage({ active }: { active: boolean }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [assets, setAssets] = useState<AssetCard[]>([]);
  const [assetType, setAssetType] = useState<AssetType>("character");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string> | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmDeleteName, setConfirmDeleteName] = useState<string | null>(null);
  const [llmModels, setLlmModels] = useState<Model[]>([]);
  const [aiModelId, setAiModelId] = useState("");
  const [specs, setSpecs] = useState<AssetSpecs | null>(null);
  const [genJob, setGenJob] = useState<AssetGenerateJob | null>(null);
  const [genBusy, setGenBusy] = useState(false);
  const [error, setError] = useState("");
  const [versions, setVersions] = useState<AssetVersion[]>([]);
  const [apiBase, setApiBase] = useState("");
  const [confirmDeleteVersionId, setConfirmDeleteVersionId] = useState<
    string | null
  >(null);
  const [versionBusy, setVersionBusy] = useState(false);
  const pollRef = useRef<string | null>(null);

  const refreshAssets = useCallback(async (pid: string) => {
    setError("");
    try {
      const items = await listAssets(pid);
      setAssets(items);
      setSelectedName(null);
      setDraft(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    if (!active) return;
    void getApiBase().then(setApiBase).catch(() => {});
    listProjects()
      .then((data) => {
        const sorted = [...data].sort((a, b) =>
          b.created_at.localeCompare(a.created_at),
        );
        setProjects(sorted);
        setProjectId((prev) =>
          prev && sorted.some((p) => p.id === prev)
            ? prev
            : (sorted[0]?.id ?? ""),
        );
      })
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
    if (projectId) {
      void refreshAssets(projectId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  useEffect(() => {
    if (!projectId) {
      setAssets([]);
      setSpecs(null);
      return;
    }
    getAssetSpecs(projectId)
      .then(setSpecs)
      .catch((e) => setError((e as Error).message));
    void refreshAssets(projectId);
  }, [projectId, refreshAssets]);

  const visibleAssets = assets.filter((a) => a.asset_type === assetType);
  const selected = assets.find(
    (a) => a.asset_type === assetType && a.name === selectedName,
  );

  // 主从布局：切换分类后自动选中第一个资产
  useEffect(() => {
    const first = visibleAssets[0];
    if (first && selectedName === null) {
      setSelectedName(first.name);
      setDraft(buildDraft(first));
    }
  }, [visibleAssets, selectedName]);

  function selectAsset(asset: AssetCard) {
    setSelectedName(asset.name);
    setDraft(buildDraft(asset));
    setConfirmDeleteName(null);
    setConfirmDeleteVersionId(null);
  }

  function changeType(next: AssetType) {
    setAssetType(next);
    setSelectedName(null);
    setDraft(null);
    setConfirmDeleteName(null);
    setConfirmDeleteVersionId(null);
  }

  const refreshVersions = useCallback(async () => {
    if (!projectId || !selected?.asset_id) return;
    try {
      setVersions(await listAssetVersions(projectId, selected.asset_id));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [projectId, selected?.asset_id]);

  useEffect(() => {
    if (!projectId || !selected?.asset_id) {
      setVersions([]);
      return;
    }
    void refreshVersions();
    setConfirmDeleteVersionId(null);
  }, [projectId, selected?.asset_id, refreshVersions]);

  async function handlePromoteVersion(versionId: string) {
    if (!projectId || !selected?.asset_id) return;
    setVersionBusy(true);
    setError("");
    try {
      await promoteAssetVersion(projectId, selected.asset_id, versionId);
      await refreshVersions();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setVersionBusy(false);
    }
  }

  async function handleDeleteVersion(versionId: string) {
    if (!projectId || !selected?.asset_id) return;
    if (confirmDeleteVersionId !== versionId) {
      setConfirmDeleteVersionId(versionId);
      return;
    }
    setVersionBusy(true);
    setError("");
    try {
      await deleteAssetVersion(projectId, selected.asset_id, versionId);
      setConfirmDeleteVersionId(null);
      await refreshVersions();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setVersionBusy(false);
    }
  }

  async function saveAsset() {
    if (!projectId || !selected || !draft) return;
    setSaving(true);
    setError("");
    try {
      const updated = await updateAsset(projectId, {
        asset_type: selected.asset_type,
        name: selected.name,
        patch: draft,
      });
      setAssets((prev) =>
        prev.map((a) =>
          a.asset_type === updated.asset_type && a.name === updated.name
            ? updated
            : a,
        ),
      );
      setDraft(buildDraft(updated));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!projectId || !selected) return;
    if (confirmDeleteName !== selected.name) {
      setConfirmDeleteName(selected.name);
      return;
    }
    setConfirmDeleteName(null);
    setError("");
    try {
      await deleteAsset(projectId, {
        asset_type: selected.asset_type,
        name: selected.name,
      });
      const items = await listAssets(projectId);
      setAssets(items);
      setSelectedName(null);
      setDraft(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function runGeneration() {
    if (!projectId || !aiModelId) return;
    setGenBusy(true);
    setError("");
    try {
      const job = await startAssetGeneration(projectId, aiModelId);
      setGenJob(job);
      pollRef.current = job.job_id;
      while (pollRef.current === job.job_id) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        if (pollRef.current !== job.job_id) break;
        const updated = await getAssetGeneration(projectId, job.job_id);
        setGenJob(updated);
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          pollRef.current = null;
          if (updated.status === "completed") {
            const items = await listAssets(projectId);
            setAssets(items);
            if (selectedName) {
              const refreshed = items.find(
                (a) =>
                  a.asset_type === assetType && a.name === selectedName,
              );
              if (refreshed) setDraft(buildDraft(refreshed));
            }
          }
          break;
        }
      }
    } catch (e) {
      setError((e as Error).message);
      pollRef.current = null;
    } finally {
      setGenBusy(false);
    }
  }

  const spec = selected?.image_spec;
  const activeRatio = draft?.aspect_ratio || spec?.aspect_ratio || "2:3";
  const activeSpecOption =
    specs?.aspect_ratios.find((r) => r.value === activeRatio) ?? null;
  const previewSpec = {
    aspect_ratio: activeSpecOption?.value ?? spec?.aspect_ratio ?? "2:3",
    width: activeSpecOption?.width ?? spec?.width ?? 1024,
    height: activeSpecOption?.height ?? spec?.height ?? 1536,
  };

  return (
    <div className="page asset-page">
      {error && <p className="error">{error}</p>}

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
              <h3>资产分类</h3>
            </div>
            <div className="tabs">
              {(["character", "location", "prop"] as AssetType[]).map((t) => (
                <button
                  key={t}
                  type="button"
                  className={assetType === t ? "tab active" : "tab"}
                  onClick={() => changeType(t)}
                >
                  {ASSET_TYPE_LABELS[t]}
                  <span className="asset-count">
                    {assets.filter((a) => a.asset_type === t).length}
                  </span>
                </button>
              ))}
            </div>
            {!projectId ? (
              <p className="muted">先选择项目。</p>
            ) : visibleAssets.length === 0 ? (
              <p className="muted">
                还没有{ASSET_TYPE_LABELS[assetType]}资产。
                <br />
                先在「故事圣经」运行故事分析，或用右侧 AI 向导补全资产卡。
              </p>
            ) : (
              <ul className="chapter-tree">
                {visibleAssets.map((asset) => (
                  <li key={asset.asset_id}>
                    <button
                      type="button"
                      className={
                        asset.name === selectedName
                          ? "chapter-item active"
                          : "chapter-item"
                      }
                      onClick={() => selectAsset(asset)}
                    >
                      <span className="asset-item-name">{asset.name}</span>
                      <span className="asset-item-id">{asset.asset_id}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        <section className="novel-main">
          {selected ? (
            <>
              <div className="panel-head">
                <div className="scene-head">
                  <h3>{selected.name}</h3>
                  <div className="toolbar">
                    <span className="badge">{selected.asset_id}</span>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={saving}
                      onClick={saveAsset}
                    >
                      {saving ? "保存中…" : "保存资产卡"}
                    </button>
                    <button
                      type="button"
                      className="button-danger button-ghost"
                      onClick={handleDelete}
                    >
                      {confirmDeleteName === selected.name
                        ? "确认删除"
                        : "删除资产"}
                    </button>
                    {confirmDeleteName === selected.name && (
                      <button
                        type="button"
                        onClick={() => setConfirmDeleteName(null)}
                      >
                        取消
                      </button>
                    )}
                  </div>
                </div>
                <p className="muted">
                  {ASSET_TYPE_LABELS[selected.asset_type]}视觉资产卡 ·
                  图片规格固定为 {selected.image_spec.aspect_ratio}
                </p>
              </div>

              {spec && (
                <div className="asset-spec-card">
                  <div
                    className="asset-spec-box"
                    style={{ aspectRatio: previewSpec.aspect_ratio }}
                  >
                    <span className="asset-spec-label">{spec.label}</span>
                    <span className="asset-spec-meta">
                      {previewSpec.aspect_ratio} · {previewSpec.width}×
                      {previewSpec.height}
                    </span>
                  </div>
                  <div className="asset-spec-controls">
                    <label>
                      图片比例
                      <select
                        value={draft?.aspect_ratio ?? ""}
                        onChange={(e) =>
                          setDraft((prev) =>
                            prev
                              ? { ...prev, aspect_ratio: e.target.value }
                              : prev,
                          )
                        }
                      >
                        <option value="">
                          默认（{spec.aspect_ratio}）
                        </option>
                        {specs?.aspect_ratios.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      画风
                      <select
                        value={draft?.art_style ?? ""}
                        onChange={(e) =>
                          setDraft((prev) =>
                            prev
                              ? { ...prev, art_style: e.target.value }
                              : prev,
                          )
                        }
                      >
                        {specs?.art_styles.map((s) => (
                          <option key={s.value} value={s.value}>
                            {s.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <p className="muted">
                    生图时将按此比例与画风生成；「默认」使用当前类型的标准规格。
                  </p>
                </div>
              )}

              <div className="card">
                <div className="sidebar-head">
                  <h3>固定人设提示词</h3>
                  <span className="badge badge-default">Reference Prompt</span>
                </div>
                <p className="muted">
                  后续生图 / 生视频会复用这段描述保证一致性，AI 生成后建议人工确认。
                </p>
                <textarea
                  value={draft?.reference_prompt ?? ""}
                  onChange={(e) =>
                    setDraft((prev) =>
                      prev ? { ...prev, reference_prompt: e.target.value } : prev,
                    )
                  }
                  rows={4}
                  placeholder="英文固定人设提示词，例如：male protagonist, short black hair, dark eyes, green cloth robe, consistent character design"
                />
              </div>

              <div className="card">
                <h3>资产卡字段</h3>
                {FIELD_SETS[selected.asset_type].map((field) => (
                  <label key={field.key}>
                    {field.label}
                    <textarea
                      value={draft?.[field.key] ?? ""}
                      onChange={(e) =>
                        setDraft((prev) =>
                          prev ? { ...prev, [field.key]: e.target.value } : prev,
                        )
                      }
                      rows={field.rows ?? 2}
                      placeholder={field.placeholder}
                    />
                  </label>
                ))}
              </div>

              <div className="card">
                <div className="sidebar-head">
                  <h3>图片版本</h3>
                  <span className="badge badge-default">
                    {versions.some((v) => v.is_current)
                      ? `当前 v${versions.find((v) => v.is_current)?.version}`
                      : "暂无版本"}
                  </span>
                  <button
                    type="button"
                    disabled
                    title="图片生成功能将在后续阶段开放"
                  >
                    生成图片
                  </button>
                </div>
                <p className="muted">
                  图片生成功能将在后续阶段开放，生成结果会自动保存为新版本。
                </p>
                {versions.length === 0 ? (
                  <p className="muted">还没有图片版本。</p>
                ) : (
                  <ul className="version-list">
                    {versions.map((v) => (
                      <li
                        key={v.id}
                        className={
                          v.is_current
                            ? "version-item version-item-current"
                            : "version-item"
                        }
                      >
                        <img
                          src={`${apiBase}${v.file_url}`}
                          alt={`版本 v${v.version}`}
                          className="version-thumb"
                        />
                        <div className="version-info">
                          <span className="project-name">
                            v{v.version}
                            {v.is_current && " · 当前"}
                          </span>
                          <span className="muted">
                            {formatVersionTime(v.created_at)}
                            {v.model_id ? ` · ${v.model_id}` : ""}
                          </span>
                        </div>
                        <div className="version-actions">
                          {!v.is_current && (
                            <button
                              type="button"
                              onClick={() => void handlePromoteVersion(v.id)}
                              disabled={versionBusy}
                            >
                              设为当前
                            </button>
                          )}
                          {!v.is_current && (
                            <button
                              type="button"
                              className={
                                confirmDeleteVersionId === v.id
                                  ? "button-danger"
                                  : "button-ghost"
                              }
                              onClick={() => void handleDeleteVersion(v.id)}
                              disabled={versionBusy}
                            >
                              {confirmDeleteVersionId === v.id
                                ? "确认删除"
                                : "删除"}
                            </button>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          ) : (
            <div className="novel-empty">
              <p className="muted">
                {!projectId
                  ? "选择项目后查看项目视觉资产。"
                  : `从左侧选择${ASSET_TYPE_LABELS[assetType]}资产进行编辑。`}
              </p>
            </div>
          )}
        </section>

        <aside className="novel-inspector">
          <div className="panel-head">
            <h3>AI 向导</h3>
            <p className="muted">从 Story Bible 补全视觉资产卡</p>
          </div>
          <div className="card inspector-card">
            <h3>生成资产卡</h3>
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
            <button
              type="button"
              className="btn-primary"
              disabled={!projectId || !aiModelId || genBusy || llmModels.length === 0}
              onClick={runGeneration}
            >
              {genBusy ? "生成中…" : "补全资产卡"}
            </button>
            {genJob && (
              <p className="muted">
                {genJob.detail}
                {genJob.progress != null &&
                  `（${Math.round(genJob.progress * 100)}%）`}
              </p>
            )}
            {genJob?.error && <p className="error">{genJob.error}</p>}
            <div className="context-card">
              <h4>规则</h4>
              <p className="muted">
                只补充空白字段，不会覆盖你已经填写的内容。
              </p>
              <p className="muted">
                图片规格固定：角色 2:3（1024×1536）、场景 16:9（1280×720）、
                道具 1:1（1024×1024）。
              </p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

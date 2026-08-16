import { Fragment, useCallback, useEffect, useRef, useState } from "react";

import { InfoTip } from "../components/InfoTip";
import {
  createGenerationJob,
  getGenerationJob,
} from "../api/generation";
import {
  bulkAddModels,
  createModel,
  createProvider,
  deleteModel,
  deleteProvider,
  discoverModels,
  getPresetModels,
  listModels,
  listPresets,
  listProviders,
  setDefaultModel,
  testProvider,
  updateModelCapabilities,
  updateModel,
  updateProvider,
} from "../api/providers";
import type {
  BuiltinModel,
  CapabilityKey,
  Model,
  ModelType,
  Preset,
  Provider,
  ProviderProtocol,
  ProviderTestResult,
} from "../types/provider";
import { PROTOCOL_LABELS } from "../types/provider";
import type { GenerationJob } from "../types/generation";
import {
  CAPABILITY_LABELS,
  IMAGE_CAPABILITIES,
  VIDEO_CAPABILITIES,
} from "../types/provider";

const CUSTOM_KEY = "__custom__";

const TYPE_LABEL: Record<ModelType, string> = {
  llm: "文本模型",
  image: "图片模型",
  video: "视频模型",
};

const GEN_STATUS_LABEL: Record<GenerationJob["status"], string> = {
  queued: "排队中…",
  running: "生成中…",
  paused: "已暂停",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function SettingsPage() {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Provider | null>(null);
  const [discoveringId, setDiscoveringId] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, ProviderTestResult>
  >({});
  const [collapsedTests, setCollapsedTests] = useState<Record<string, boolean>>(
    {},
  );
  const [builtin, setBuiltin] = useState<Record<string, BuiltinModel[]>>({});
  const [builtinOpen, setBuiltinOpen] = useState<string | null>(null);
  const [builtinBusy, setBuiltinBusy] = useState<string | null>(null);
  const [capEdit, setCapEdit] = useState<{
    modelId: string;
    caps: CapabilityKey[];
  } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<{
    kind: "provider" | "model";
    id: string;
  } | null>(null);
  const [genPanel, setGenPanel] = useState<{
    modelId: string;
    prompt: string;
    capability: string;
  } | null>(null);
  const [genJobs, setGenJobs] = useState<Record<string, GenerationJob>>({});
  const [genErrors, setGenErrors] = useState<Record<string, string>>({});
  const [genBusy, setGenBusy] = useState(false);
  const genPollRef = useRef<string | null>(null);

  const [formPreset, setFormPreset] = useState("");
  const [formName, setFormName] = useState("");
  const [formBaseUrl, setFormBaseUrl] = useState("");
  const [formProtocol, setFormProtocol] = useState<ProviderProtocol>("openai_compat");
  const [formNeedsKey, setFormNeedsKey] = useState(true);
  const [formApiKey, setFormApiKey] = useState("");
  const [modelFilter, setModelFilter] = useState<"all" | ModelType>("all");
  const [manualModel, setManualModel] = useState<{
    providerId: string;
    modelId: string;
    modelType: ModelType;
  } | null>(null);

  const refresh = useCallback(async () => {
    const [p, provs, mods] = await Promise.all([
      listPresets(),
      listProviders(),
      listModels(),
    ]);
    setPresets(p);
    setProviders(provs);
    setModels(mods);
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError((e as Error).message));
  }, [refresh]);

  function resetForm() {
    setFormPreset("");
    setFormName("");
    setFormBaseUrl("");
    setFormProtocol("openai_compat");
    setFormNeedsKey(true);
    setFormApiKey("");
    setShowForm(false);
    setEditing(null);
    setNotice("");
  }

  async function discover(id: string, silent: boolean) {
    setDiscoveringId(id);
    try {
      await discoverModels(id);
      await refresh();
    } catch (err) {
      if (silent) {
        setNotice(`模型拉取失败：${(err as Error).message}（可手动添加模型）`);
      } else {
        setError((err as Error).message);
      }
    } finally {
      setDiscoveringId(null);
    }
  }

  async function runTest(provider: Provider) {
    setTestingId(provider.id);
    setError("");
    try {
      const result = await testProvider(provider.id);
      setTestResults((prev) => ({ ...prev, [provider.id]: result }));
      setCollapsedTests((prev) => ({ ...prev, [provider.id]: false }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setTestingId(null);
    }
  }

  async function handleSaveCapabilities(e: React.FormEvent) {
    e.preventDefault();
    if (!capEdit) return;
    setError("");
    try {
      await updateModelCapabilities(capEdit.modelId, capEdit.caps, "manual");
      setCapEdit(null);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleResetCapabilities(model: Model) {
    setError("");
    try {
      await updateModelCapabilities(model.id, [], "auto");
      setCapEdit(null);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function toggleCap(cap: CapabilityKey, on: boolean) {
    setCapEdit((prev) => {
      if (!prev) return prev;
      const caps = on
        ? [...prev.caps, cap]
        : prev.caps.filter((c) => c !== cap);
      return { ...prev, caps };
    });
  }

  function openGenPanel(model: Model) {
    const defaultCap =
      model.model_type === "video" ? "text_to_video" : "text_to_image";
    setGenPanel({
      modelId: model.id,
      prompt: "一只小猫在月光下奔跑",
      capability: model.capabilities.includes(defaultCap as CapabilityKey)
        ? defaultCap
        : model.capabilities[0] ?? "",
    });
    setGenJobs((prev) => {
      const next = { ...prev };
      delete next[model.id];
      return next;
    });
    setGenErrors((prev) => {
      const next = { ...prev };
      delete next[model.id];
      return next;
    });
  }

  function closeGenPanel() {
    genPollRef.current = null;
    setGenPanel(null);
  }

  async function startGenTest(e: React.FormEvent) {
    e.preventDefault();
    if (!genPanel) return;
    setGenBusy(true);
    setGenErrors((prev) => {
      const next = { ...prev };
      delete next[genPanel.modelId];
      return next;
    });
    try {
      const job = await createGenerationJob({
        model_id: genPanel.modelId,
        capability: genPanel.capability,
        prompt: genPanel.prompt.trim(),
      });
      setGenJobs((prev) => ({ ...prev, [genPanel.modelId]: job }));
      genPollRef.current = job.job_id;
      while (genPollRef.current === job.job_id) {
        await sleep(3000);
        if (genPollRef.current !== job.job_id) break;
        const updated = await getGenerationJob(job.job_id);
        setGenJobs((prev) => ({ ...prev, [genPanel.modelId]: updated }));
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          genPollRef.current = null;
          break;
        }
      }
    } catch (err) {
      setGenErrors((prev) => ({
        ...prev,
        [genPanel.modelId]: (err as Error).message,
      }));
      genPollRef.current = null;
    } finally {
      setGenBusy(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      let provider: Provider;
      if (editing) {
        provider = await updateProvider(editing.id, {
          name: formName || undefined,
          api_base_url: formBaseUrl || undefined,
          needs_key: formNeedsKey,
          protocol: formProtocol,
          api_key: formApiKey || undefined,
        });
      } else if (formPreset === CUSTOM_KEY) {
        provider = await createProvider({
          name: formName,
          api_base_url: formBaseUrl,
          protocol: formProtocol,
          needs_key: formNeedsKey,
          api_key: formApiKey || undefined,
        });
      } else {
        provider = await createProvider({
          preset_key: formPreset,
          api_key: formApiKey || undefined,
        });
      }
      const shouldDiscover =
        editing || !provider.needs_key || provider.has_api_key;
      resetForm();
      await refresh();
      if (shouldDiscover) {
        await discover(provider.id, true);
      }
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function startEdit(provider: Provider) {
    setEditing(provider);
    setFormName(provider.name);
    setFormBaseUrl(provider.api_base_url);
    setFormProtocol(provider.protocol);
    setFormNeedsKey(provider.needs_key);
    setFormApiKey("");
    setShowForm(true);
    setNotice("");
  }

  async function handleDeleteProvider(provider: Provider) {
    if (confirmDelete?.kind !== "provider" || confirmDelete.id !== provider.id) {
      setConfirmDelete({ kind: "provider", id: provider.id });
      return;
    }
    setConfirmDelete(null);
    setError("");
    try {
      await deleteProvider(provider.id);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleToggleProvider(provider: Provider) {
    setError("");
    try {
      await updateProvider(provider.id, { enabled: !provider.enabled });
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleAddModel(e: React.FormEvent) {
    e.preventDefault();
    if (!manualModel) return;
    setError("");
    try {
      await createModel({
        provider_id: manualModel.providerId,
        model_id: manualModel.modelId.trim(),
        model_type: manualModel.modelType,
      });
      setManualModel(null);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleDeleteModel(model: Model) {
    if (confirmDelete?.kind !== "model" || confirmDelete.id !== model.id) {
      setConfirmDelete({ kind: "model", id: model.id });
      return;
    }
    setConfirmDelete(null);
    setError("");
    try {
      await deleteModel(model.id);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleToggleModel(model: Model) {
    const provider = providers.find((p) => p.id === model.provider_id);
    if (!model.enabled && provider && !provider.enabled) {
      setError(
        `无法启用模型：Provider「${provider.name}」当前已禁用，请先启用该 Provider`,
      );
      return;
    }
    setError("");
    try {
      await updateModel(model.id, { enabled: !model.enabled });
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleDefault(model: Model) {
    if (model.model_type === "llm") return;
    setError("");
    try {
      await setDefaultModel(model.id, model.model_type);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function toggleBuiltin(provider: Provider) {
    if (builtinOpen === provider.id) {
      setBuiltinOpen(null);
      return;
    }
    setBuiltinOpen(provider.id);
    if (!provider.preset_key || builtin[provider.id]) return;
    setBuiltinBusy(provider.id);
    try {
      const list = await getPresetModels(provider.preset_key);
      setBuiltin((prev) => ({ ...prev, [provider.id]: list }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBuiltinBusy(null);
    }
  }

  async function addBuiltinModels(provider: Provider, ids: string[]) {
    if (ids.length === 0) return;
    setError("");
    try {
      await bulkAddModels(provider.id, ids);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const selectedPreset = presets.find((p) => p.key === formPreset);
  const isCustom = formPreset === CUSTOM_KEY;
  const showKeyField = editing
    ? formNeedsKey
    : isCustom
      ? formNeedsKey
      : (selectedPreset?.needs_key ?? false);

  return (
    <div className="page">
      <div className="page-head">
        <h2>设置</h2>
        <button type="button" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "取消" : "添加 Provider"}
        </button>
      </div>

      <p className="muted">
        API Key 仅保存在本机系统凭据管理器中，不会进入项目文件或日志。
        模型能力由规则自动推断（可手动调整），「测试连接」可验证 API Key 与模型可用性。
      </p>

      {error && <p className="error">{error}</p>}
      {notice && <p className="muted">{notice}</p>}

      {showForm && (
        <form className="card" onSubmit={handleSubmit}>
          <h3>{editing ? `编辑：${editing.name}` : "添加 Provider"}</h3>
          {!editing && (
            <label>
              厂商
              <select
                value={formPreset}
                onChange={(e) => {
                  const next = e.target.value;
                  const nextPreset = presets.find((p) => p.key === next);
                  setFormPreset(next);
                  setFormName("");
                  setFormBaseUrl("");
                  setFormProtocol(nextPreset?.protocol ?? "openai_compat");
                  setFormNeedsKey(true);
                  setFormApiKey("");
                }}
                required
              >
                <option value="">选择厂商</option>
                {presets.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.name}
                  </option>
                ))}
                <option value={CUSTOM_KEY}>自定义 Provider</option>
              </select>
            </label>
          )}

          {(isCustom || editing) && (
            <label>
              名称
              <input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                required={!editing}
              />
            </label>
          )}

          {(isCustom || editing) && (
            <label>
              协议类型
              <InfoTip text="OpenAI 兼容适合大多数 OpenAI 风格接口；阿里云百炼 / DashScope 使用百炼原生视频与图片协议。" />
              <select
                value={formProtocol}
                onChange={(e) =>
                  setFormProtocol(e.target.value as ProviderProtocol)
                }
              >
                {(Object.keys(PROTOCOL_LABELS) as ProviderProtocol[]).map(
                  (protocol) => (
                    <option key={protocol} value={protocol}>
                      {PROTOCOL_LABELS[protocol]}
                    </option>
                  ),
                )}
              </select>
            </label>
          )}

          {isCustom && (
            <label>
              API Base URL
              <InfoTip text="通常形如 https://api.example.com/v1，在提供商官方文档中查找" />
              <input
                value={formBaseUrl}
                onChange={(e) => setFormBaseUrl(e.target.value)}
                placeholder="https://api.example.com/v1"
                required
              />
            </label>
          )}

          {editing && (
            <label>
              API Base URL
              <InfoTip text="通常形如 https://api.example.com/v1，在提供商官方文档中查找；阿里云百炼国内站 https://dashscope.aliyuncs.com/compatible-mode/v1，国际站 https://dashscope-intl.aliyuncs.com/compatible-mode/v1" />
              <input
                value={formBaseUrl}
                onChange={(e) => setFormBaseUrl(e.target.value)}
              />
            </label>
          )}

          {(isCustom || editing) && (
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={formNeedsKey}
                onChange={(e) => setFormNeedsKey(e.target.checked)}
              />
              需要 API Key
            </label>
          )}

          {showKeyField && (
            <label>
              API Key
              <InfoTip text="在提供商的开发者控制台创建：OpenAI → platform.openai.com/api-keys；阿里云百炼 → 百炼控制台 API Key 管理；Ollama 本地无需 Key" />
              <input
                type="password"
                value={formApiKey}
                onChange={(e) => setFormApiKey(e.target.value)}
                placeholder={editing ? "留空则不修改" : "粘贴 API Key"}
                autoComplete="off"
              />
            </label>
          )}

          {!editing && !isCustom && selectedPreset && (
            <p className="muted">
              Base URL：{selectedPreset.base_url}
              {selectedPreset.needs_key ? "" : "（无需 API Key）"}
            </p>
          )}
          {!editing && !isCustom && selectedPreset?.key === "bailian" && (
            <p className="muted">
              国内站 Key 在百炼控制台（国内）获取；国际站 Key 请选择
              「阿里云百炼（国际站）」预设。
            </p>
          )}
          {!editing && !isCustom && selectedPreset?.key === "bailian-intl" && (
            <p className="muted">
              国际站 Key 在阿里云国际站百炼控制台获取；国内站 Key 请选择
              「阿里云百炼（国内站）」预设。
            </p>
          )}
          {!editing && !isCustom && selectedPreset && !selectedPreset.discoverable && (
            <p className="muted">
              此厂商不支持自动拉取模型列表，保存后请手动添加模型（填模型 ID 即可）。
            </p>
          )}

          <button type="submit" className="btn-primary">
            {editing ? "保存" : "添加并拉取模型"}
          </button>
        </form>
      )}

      <div className="card">
        <h3>AI Provider</h3>
        <div className="tabs">
          {(["all", "llm", "image", "video"] as const).map((filter) => (
            <button
              key={filter}
              type="button"
              className={modelFilter === filter ? "tab active" : "tab"}
              onClick={() => setModelFilter(filter)}
            >
              {filter === "all"
                ? "全部模型"
                : filter === "llm"
                  ? "文本模型"
                  : filter === "image"
                    ? "图片模型"
                    : "视频模型"}
            </button>
          ))}
        </div>
        {providers.length === 0 ? (
          <p className="muted">还没有 Provider，点击右上角添加。</p>
        ) : (
          <div className="provider-list">
            {providers.map((provider) => (
              <div key={provider.id} className="provider-card">
                <div className="provider-head">
                  <strong>{provider.name}</strong>
                  <span className="badge">
                    {provider.preset_key
                      ? presets.find((p) => p.key === provider.preset_key)?.name ??
                        provider.preset_key
                      : "自定义"}
                  </span>
                  <span className="muted">{PROTOCOL_LABELS[provider.protocol]}</span>
                  <span className="muted">
                    {provider.has_api_key ? "密钥已配置" : "密钥未配置"}
                  </span>
                </div>
                <p className="muted">
                  Base URL：{provider.api_base_url || "（未设置）"} ·{" "}
                  {provider.model_count} 个模型
                </p>
                <div className="actions">
                  <button
                    type="button"
                    onClick={() => handleToggleProvider(provider)}
                  >
                    {provider.enabled ? "已启用" : "已禁用"}
                  </button>
                  <button type="button" onClick={() => startEdit(provider)}>
                    编辑
                  </button>
                  <button
                    type="button"
                    onClick={() => discover(provider.id, false)}
                    disabled={discoveringId === provider.id}
                  >
                    {discoveringId === provider.id ? "拉取中…" : "拉取模型"}
                  </button>
                  <button
                    type="button"
                    onClick={() => runTest(provider)}
                    disabled={testingId === provider.id}
                  >
                    {testingId === provider.id ? "测试中…" : "测试连接"}
                  </button>
                  {confirmDelete?.kind === "provider" &&
                  confirmDelete.id === provider.id ? (
                    <>
                      <button
                        type="button"
                        className="button-danger"
                        onClick={() => handleDeleteProvider(provider)}
                      >
                        确认删除
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDelete(null)}
                      >
                        取消
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="button-danger button-ghost"
                      onClick={() => handleDeleteProvider(provider)}
                    >
                      删除
                    </button>
                  )}
                </div>

                {testResults[provider.id] && (
                  <div className="test-result">
                    <div className="test-result-head">
                      <p className={testResults[provider.id].ok ? "ok" : "error"}>
                        {testResults[provider.id].ok
                          ? "连接测试通过"
                          : "连接测试未通过"}
                      </p>
                      <button
                        type="button"
                        onClick={() =>
                          setCollapsedTests((prev) => ({
                            ...prev,
                            [provider.id]: !prev[provider.id],
                          }))
                        }
                      >
                        {collapsedTests[provider.id] ? "展开" : "收起"}
                      </button>
                    </div>
                    {!collapsedTests[provider.id] && (
                      <ul className="check-list">
                        {testResults[provider.id].checks.map((c, i) => (
                          <li key={i} className={`check-${c.status}`}>
                            <span className="check-mark">
                              {c.status === "ok"
                                ? "✓"
                                : c.status === "fail"
                                  ? "✕"
                                  : "–"}
                            </span>
                            {c.label}：{c.detail}
                          </li>
                        ))}
                        {testResults[provider.id].model_checks.map((m) => (
                          <li
                            key={m.model_id}
                            className={m.ok ? "check-ok" : "check-fail"}
                          >
                            <span className="check-mark">{m.ok ? "✓" : "✕"}</span>
                            {m.model_id}：{m.detail}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                <div className="models">
                  {!provider.enabled && (
                    <p className="muted provider-disabled-tip">
                      此 Provider 已禁用，其模型不会出现在生成 / 创作界面。
                      启用 Provider 后即可使用。
                    </p>
                  )}
                  {models
                    .filter((m) => m.provider_id === provider.id)
                    .filter(
                      (m) => modelFilter === "all" || m.model_type === modelFilter,
                    )
                    .map((model) => (
                      <Fragment key={model.id}>
                        <div className="model-block">
                          <div className="model-head">
                            <span className="model-name">{model.model_id}</span>
                            <span className={`badge badge-${model.model_type}`}>
                              {TYPE_LABEL[model.model_type]}
                            </span>
                            {model.is_default_image && (
                              <span className="badge badge-default">默认 Image</span>
                            )}
                            {model.is_default_video && (
                              <span className="badge badge-default">默认 Video</span>
                            )}
                            <span className="cap-badges">
                              {(model.model_type === "image"
                                ? IMAGE_CAPABILITIES
                                : model.model_type === "video"
                                  ? VIDEO_CAPABILITIES
                                  : []
                              ).map((cap) => (
                                <span
                                  key={cap}
                                  className={
                                    model.capabilities.includes(cap)
                                      ? "cap-badge cap-on"
                                      : "cap-badge cap-off"
                                  }
                                >
                                  {model.capabilities.includes(cap) ? "✓" : "✕"}{" "}
                                  {CAPABILITY_LABELS[cap]}
                                </span>
                              ))}
                              {model.model_type !== "llm" && (
                                <span className="muted">
                                  {model.capability_source === "manual" ? "手动" : "自动"}
                                </span>
                              )}
                            </span>
                          </div>
                          <div className="actions">
                            <button
                              type="button"
                              onClick={() => handleToggleModel(model)}
                            >
                              {model.enabled ? "禁用" : "启用"}
                            </button>
                            {model.model_type !== "llm" && (
                              <button type="button" onClick={() => handleDefault(model)}>
                                设默认
                              </button>
                            )}
                            {model.model_type !== "llm" && (
                              <button type="button" onClick={() => openGenPanel(model)}>
                                生成测试
                              </button>
                            )}
                            {model.model_type !== "llm" && (
                              <button
                                type="button"
                                onClick={() =>
                                  capEdit?.modelId === model.id
                                    ? setCapEdit(null)
                                    : setCapEdit({
                                        modelId: model.id,
                                        caps: model.capabilities,
                                      })
                                }
                              >
                                编辑能力
                              </button>
                            )}
                            {confirmDelete?.kind === "model" &&
                            confirmDelete.id === model.id ? (
                              <>
                                <button
                                  type="button"
                                  className="button-danger"
                                  onClick={() => handleDeleteModel(model)}
                                >
                                  确认删除
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setConfirmDelete(null)}
                                >
                                  取消
                                </button>
                              </>
                            ) : (
                              <button
                                type="button"
                                className="button-danger button-ghost"
                                onClick={() => handleDeleteModel(model)}
                              >
                                删除
                              </button>
                            )}
                          </div>
                          {capEdit?.modelId === model.id && (
                            <form
                              className="cap-edit-form"
                              onSubmit={handleSaveCapabilities}
                            >
                              <span className="cap-edit-list">
                                {(model.model_type === "image"
                                  ? IMAGE_CAPABILITIES
                                  : VIDEO_CAPABILITIES
                                ).map((cap) => (
                                  <label key={cap} className="checkbox-row">
                                    <input
                                      type="checkbox"
                                      checked={capEdit.caps.includes(cap)}
                                      onChange={(e) =>
                                        toggleCap(cap, e.target.checked)
                                      }
                                    />
                                    {CAPABILITY_LABELS[cap]}
                                  </label>
                                ))}
                              </span>
                              <button type="submit">保存</button>
                              <button
                                type="button"
                                onClick={() => handleResetCapabilities(model)}
                              >
                                重置为自动
                              </button>
                              <button type="button" onClick={() => setCapEdit(null)}>
                                取消
                              </button>
                            </form>
                          )}
                          {genPanel?.modelId === model.id && (
                            <form className="gen-test-panel" onSubmit={startGenTest}>
                              <label>
                                提示词
                                <input
                                  value={genPanel.prompt}
                                  onChange={(e) =>
                                    setGenPanel({ ...genPanel, prompt: e.target.value })
                                  }
                                  placeholder="描述要生成的内容"
                                  required
                                />
                              </label>
                              <label>
                                能力
                                <select
                                  value={genPanel.capability}
                                  onChange={(e) =>
                                    setGenPanel({
                                      ...genPanel,
                                      capability: e.target.value,
                                    })
                                  }
                                >
                                  {model.capabilities.map((cap) => (
                                    <option key={cap} value={cap}>
                                      {CAPABILITY_LABELS[cap as CapabilityKey]}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <button type="submit" disabled={genBusy}>
                                {genBusy ? "提交中…" : "确认生成（会产生真实费用）"}
                              </button>
                              <button type="button" onClick={closeGenPanel}>
                                关闭
                              </button>
                              {genErrors[model.id] && (
                                <p className="error gen-error">
                                  {genErrors[model.id]}
                                </p>
                              )}
                              {genJobs[model.id] && (
                                <div className="gen-result">
                                  <p className="muted">
                                    状态：{GEN_STATUS_LABEL[genJobs[model.id].status]}
                                  </p>
                                  {genJobs[model.id].error && (
                                    <p className="error">{genJobs[model.id].error}</p>
                                  )}
                                  {genJobs[model.id].result?.urls.map((u, i) => {
                                    const isVideo =
                                      genJobs[model.id].capability === "text_to_video" ||
                                      genJobs[model.id].capability === "image_to_video" ||
                                      /\.(mp4|webm|mov)(\?|$)/i.test(u);
                                    return isVideo ? (
                                      <video
                                        key={i}
                                        src={u}
                                        controls
                                        className="gen-media"
                                      />
                                    ) : (
                                      <img
                                        key={i}
                                        src={u}
                                        alt="生成结果"
                                        className="gen-media"
                                      />
                                    );
                                  })}
                                </div>
                              )}
                            </form>
                          )}
                        </div>
                      </Fragment>
                    ))}
                </div>

                {manualModel?.providerId === provider.id ? (
                  <form className="toolbar" onSubmit={handleAddModel}>
                    <input
                      value={manualModel.modelId}
                      onChange={(e) =>
                        setManualModel({ ...manualModel, modelId: e.target.value })
                      }
                      placeholder="模型 ID（如 gpt-4o）"
                      required
                    />
                    <select
                      value={manualModel.modelType}
                      onChange={(e) =>
                        setManualModel({
                          ...manualModel,
                          modelType: e.target.value as ModelType,
                        })
                      }
                    >
                      <option value="llm">文本模型（LLM）</option>
                      <option value="image">图片模型（Image）</option>
                      <option value="video">视频模型（Video）</option>
                    </select>
                    <button type="submit">添加</button>
                    <button
                      type="button"
                      onClick={() => setManualModel(null)}
                    >
                      取消
                    </button>
                  </form>
                ) : (
                  <button
                    type="button"
                    className="button-like"
                    onClick={() =>
                      setManualModel({
                        providerId: provider.id,
                        modelId: "",
                        modelType: "llm",
                      })
                    }
                  >
                    手动添加模型
                  </button>
                )}

                {provider.preset_key && (
                  <div className="builtin-section">
                    <button
                      type="button"
                      className="button-like"
                      onClick={() => toggleBuiltin(provider)}
                    >
                      {builtinOpen === provider.id ? "收起内置模型" : "内置模型列表"}
                    </button>
                    {builtinOpen === provider.id && (
                      <div className="builtin-list">
                        {builtinBusy === provider.id ? (
                          <p className="muted">加载中…</p>
                        ) : (builtin[provider.id] ?? []).length === 0 ? (
                          <p className="muted">该厂商暂无内置模型，请手动添加或拉取。</p>
                        ) : (
                          <>
                            <div className="actions">
                              <button
                                type="button"
                                onClick={() =>
                                  addBuiltinModels(
                                    provider,
                                    (builtin[provider.id] ?? [])
                                      .map((m) => m.id)
                                      .filter(
                                        (id) =>
                                          !models.some(
                                            (x) =>
                                              x.provider_id === provider.id &&
                                              x.model_id === id,
                                          ),
                                      ),
                                  )
                                }
                              >
                                全部添加
                              </button>
                            </div>
                            <ul className="builtin-items">
                              {(builtin[provider.id] ?? []).map((m) => {
                                const added = models.some(
                                  (x) =>
                                    x.provider_id === provider.id &&
                                    x.model_id === m.id,
                                );
                                return (
                                  <li key={m.id} className="model-row">
                                    <span className="model-name">{m.id}</span>
                                    <span className={`badge badge-${m.type}`}>
                                      {TYPE_LABEL[m.type]}
                                    </span>
                                    <span className="muted">
                                      {m.capabilities
                                        .map((c) => CAPABILITY_LABELS[c])
                                        .join("、") || "—"}
                                    </span>
                                    <button
                                      type="button"
                                      disabled={added}
                                      onClick={() => addBuiltinModels(provider, [m.id])}
                                    >
                                      {added ? "已添加" : "添加"}
                                    </button>
                                  </li>
                                );
                              })}
                            </ul>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

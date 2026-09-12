import { useEffect, useMemo, useState, type ReactNode } from "react";
import { getEpisodePipelinePlan, startEpisodePipeline } from "../api/pipeline";
import { listModels } from "../api/providers";
import {
  applyWorkflowTemplate,
  createWorkflowTemplate,
  deleteWorkflowTemplate,
  getEpisodeWorkflowConfig,
  listWorkflowTemplates,
  previewWorkflowTemplate,
  saveEpisodeWorkflowConfig,
  updateWorkflowTemplate,
  type WorkflowConfig,
  type WorkflowPreview,
  type WorkflowTemplate,
} from "../api/workflowTemplates";
import type { JobOut } from "../types/job";
import type { Model } from "../types/provider";
import { GenerationParameterFields } from "./GenerationParameterFields";
import {
  unsupportedParameterKeys,
  useGenerationParameterSchema,
} from "./generationParameters";

const VALUE_LABEL: Record<string, string> = {
  true: "开启",
  false: "关闭",
  shot: "按镜头",
  fixed: "固定时长",
  text_to_image: "文生图",
  reference_image: "参考图生成",
  image_to_image: "图生图",
  image_to_video: "图生视频",
};

function formatValue(value: string | number | boolean) {
  return VALUE_LABEL[String(value)] ?? String(value || "未设置");
}

export function EpisodeWorkflowConfig({
  projectId,
  episodeId,
  episodeTitle,
  onStarted,
}: {
  projectId: string;
  episodeId: string;
  episodeTitle: string;
  onStarted: (job: JobOut) => void;
}) {
  const [config, setConfig] = useState<WorkflowConfig | null>(null);
  const [revision, setRevision] = useState(0);
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [templateName, setTemplateName] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [selectedTemplateName, setSelectedTemplateName] = useState("");
  const [deleteArmed, setDeleteArmed] = useState(false);
  const [preview, setPreview] = useState<WorkflowPreview | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setConfig(null);
    setPreview(null);
    setSelected([]);
    setDirty(false);
    setError("");
    Promise.all([
      getEpisodeWorkflowConfig(projectId, episodeId),
      listWorkflowTemplates(projectId),
      listModels(),
    ])
      .then(([saved, items, available]) => {
        if (cancelled) return;
        setConfig(saved.config);
        setRevision(saved.revision);
        setTemplates(items);
        setModels(available);
        setTemplateId(items[0]?.id ?? "");
      })
      .catch((reason: Error) => !cancelled && setError(reason.message));
    return () => {
      cancelled = true;
    };
  }, [projectId, episodeId]);

  const byType = useMemo(
    () => ({
      llm: models.filter((model) => model.model_type === "llm"),
      image: models.filter((model) => model.model_type === "image"),
      video: models.filter((model) => model.model_type === "video"),
    }),
    [models],
  );

  const selectedTemplate = templates.find((template) => template.id === templateId);
  const imageParameters = useGenerationParameterSchema(
    config?.shot_images.enabled ? config.shot_images.model_id : "",
    config?.shot_images.capability ?? "text_to_image",
  );
  const videoParameters = useGenerationParameterSchema(
    config?.videos.enabled ? config.videos.model_id : "",
    "image_to_video",
  );
  const loadedImageSchema = imageParameters.schema;
  const loadedVideoSchema = videoParameters.schema;
  const imageSchema =
    loadedImageSchema &&
    loadedImageSchema.model_id === config?.shot_images.model_id &&
    loadedImageSchema.capability === config?.shot_images.capability
      ? loadedImageSchema
      : null;
  const videoSchema =
    loadedVideoSchema &&
    loadedVideoSchema.model_id === config?.videos.model_id &&
    loadedVideoSchema.capability === "image_to_video"
      ? loadedVideoSchema
      : null;
  const imageParameterFields = (imageSchema?.fields ?? []).filter(
    (field) => field.key === "aspect_ratio",
  );
  const videoParameterFields = (videoSchema?.fields ?? []).filter(
    (field) =>
      field.key === "aspect_ratio" ||
      (field.key === "duration" && config?.videos.duration_mode === "fixed"),
  );
  const unsupportedParameters = config
    ? [
        ...unsupportedParameterKeys(imageParameterFields, {
          aspect_ratio: config.shot_images.aspect_ratio,
        }),
        ...(imageSchema &&
        !imageParameterFields.some((field) => field.key === "aspect_ratio") &&
        config.shot_images.aspect_ratio
          ? ["aspect_ratio"]
          : []),
        ...unsupportedParameterKeys(videoParameterFields, {
          aspect_ratio: config.videos.aspect_ratio,
          duration: config.videos.duration,
        }),
        ...(videoSchema &&
        !videoParameterFields.some((field) => field.key === "aspect_ratio") &&
        config.videos.aspect_ratio
          ? ["aspect_ratio"]
          : []),
        ...(videoSchema &&
        config.videos.duration_mode === "fixed" &&
        !videoParameterFields.some((field) => field.key === "duration")
          ? ["duration"]
          : []),
      ]
    : [];
  const parametersLoading = imageParameters.loading || videoParameters.loading;
  const parametersUnavailable = Boolean(imageParameters.error || videoParameters.error);

  useEffect(() => {
    setSelectedTemplateName(selectedTemplate?.name ?? "");
    setDeleteArmed(false);
  }, [selectedTemplate?.id, selectedTemplate?.name]);

  function change(next: WorkflowConfig) {
    setConfig(next);
    setDirty(true);
    setNotice("");
    setPreview(null);
  }

  async function save() {
    if (!config) return;
    if (unsupportedParameters.length) {
      setError("当前模型不支持已保存的生成参数，请先重新选择标记项。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const saved = await saveEpisodeWorkflowConfig(projectId, episodeId, {
        expected_revision: revision,
        config,
      });
      setConfig(saved.config);
      setRevision(saved.revision);
      setDirty(false);
      setNotice("本集制作配置已保存。");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createTemplate() {
    if (!config || !templateName.trim()) return;
    setBusy(true);
    setError("");
    try {
      const item = await createWorkflowTemplate(projectId, {
        name: templateName.trim(),
        config,
      });
      setTemplates((current) => [item, ...current]);
      setTemplateId(item.id);
      setTemplateName("");
      setNotice(`已保存模板“${item.name}”。`);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function updateTemplate(input: { name?: string; config?: WorkflowConfig }) {
    if (!selectedTemplate) return;
    setBusy(true);
    setError("");
    try {
      const updated = await updateWorkflowTemplate(projectId, selectedTemplate.id, {
        expected_revision: selectedTemplate.revision,
        ...input,
      });
      setTemplates((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice(
        input.config
          ? `模板“${updated.name}”已更新为当前配置。`
          : `模板已重命名为“${updated.name}”。`,
      );
      setPreview(null);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function removeTemplate() {
    if (!selectedTemplate) return;
    if (!deleteArmed) {
      setDeleteArmed(true);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await deleteWorkflowTemplate(projectId, selectedTemplate.id);
      const remaining = templates.filter((item) => item.id !== selectedTemplate.id);
      setTemplates(remaining);
      setTemplateId(remaining[0]?.id ?? "");
      setPreview(null);
      setNotice(`模板“${selectedTemplate.name}”已删除；已应用到剧集的配置不受影响。`);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
      setDeleteArmed(false);
    }
  }

  async function openPreview() {
    if (!templateId || dirty) return;
    setBusy(true);
    setError("");
    try {
      setPreview(await previewWorkflowTemplate(projectId, episodeId, templateId));
      setSelected([]);
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function applyTemplate() {
    if (!preview || !selected.length) return;
    setBusy(true);
    setError("");
    try {
      const saved = await applyWorkflowTemplate(projectId, episodeId, {
        template_id: preview.template_id,
        template_revision: preview.template_revision,
        config_revision: preview.config_revision,
        selected_fields: selected,
      });
      setConfig(saved.config);
      setRevision(saved.revision);
      setPreview(null);
      setSelected([]);
      setDirty(false);
      setNotice("已应用所选配置。");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    if (dirty) {
      setError("请先保存本集配置，再开始生成。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const plan = await getEpisodePipelinePlan(projectId, episodeId);
      if (!plan.can_start) {
        const blocked = plan.stages.find((stage) => stage.status === "not_ready");
        throw new Error(blocked?.missing_reason || "本集没有可执行阶段。");
      }
      const job = await startEpisodePipeline(projectId, episodeId, revision);
      onStarted(job);
      setNotice("本集生产任务已创建。");
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!config)
    return (
      <section className="card workflow-config">
        <p className="muted">正在读取本集配置…</p>
      </section>
    );

  return (
    <section className="card workflow-config" aria-labelledby="workflow-config-title">
      <div className="workflow-config-head">
        <div>
          <h3 id="workflow-config-title">本集制作配置</h3>
          <p className="muted">{episodeTitle || "未命名剧集"} · 配置只作用于当前剧集</p>
        </div>
        <label className="workflow-auto">
          <input
            type="checkbox"
            checked={config.auto_continue}
            onChange={(event) =>
              change({ ...config, auto_continue: event.target.checked })
            }
          />
          阶段完成后自动继续
        </label>
      </div>

      <div className="workflow-stages">
        <StageRow
          label="生成分镜"
          enabled={config.storyboard.enabled}
          onEnabled={(enabled) =>
            change({ ...config, storyboard: { ...config.storyboard, enabled } })
          }
        >
          <ModelSelect
            label="文本模型"
            value={config.storyboard.model_id}
            models={byType.llm}
            onChange={(model_id) =>
              change({ ...config, storyboard: { ...config.storyboard, model_id } })
            }
          />
        </StageRow>
        <StageRow
          label="生成关键帧"
          enabled={config.shot_images.enabled}
          onEnabled={(enabled) =>
            change({ ...config, shot_images: { ...config.shot_images, enabled } })
          }
        >
          <label>
            生成方式
            <select
              value={config.shot_images.capability}
              onChange={(event) => {
                const capability = event.target
                  .value as WorkflowConfig["shot_images"]["capability"];
                const currentModel = byType.image.find(
                  (model) => model.id === config.shot_images.model_id,
                );
                change({
                  ...config,
                  shot_images: {
                    ...config.shot_images,
                    capability,
                    model_id: currentModel?.capabilities.includes(capability)
                      ? config.shot_images.model_id
                      : "",
                  },
                });
              }}
            >
              <option value="text_to_image">文生图</option>
              <option value="reference_image">参考图生成</option>
              <option value="image_to_image">图生图</option>
            </select>
          </label>
          <ModelSelect
            label="图片模型"
            value={config.shot_images.model_id}
            models={byType.image.filter((model) =>
              model.capabilities.includes(config.shot_images.capability),
            )}
            onChange={(model_id) =>
              change({ ...config, shot_images: { ...config.shot_images, model_id } })
            }
          />
          {imageParameterFields.length ? (
            <GenerationParameterFields
              fields={imageParameterFields}
              values={{ aspect_ratio: config.shot_images.aspect_ratio }}
              onChange={(_, value) =>
                change({
                  ...config,
                  shot_images: {
                    ...config.shot_images,
                    aspect_ratio: String(value),
                  },
                })
              }
            />
          ) : (
            <label>
              画面比例
              <select
                value={config.shot_images.aspect_ratio}
                aria-invalid={
                  Boolean(imageSchema) && Boolean(config.shot_images.aspect_ratio)
                }
                onChange={(event) =>
                  change({
                    ...config,
                    shot_images: {
                      ...config.shot_images,
                      aspect_ratio: event.target.value,
                    },
                  })
                }
              >
                <option value="">使用模型默认</option>
                {imageSchema && config.shot_images.aspect_ratio ? (
                  <option value={config.shot_images.aspect_ratio}>
                    当前值 {config.shot_images.aspect_ratio}（不支持）
                  </option>
                ) : (
                  !config.shot_images.model_id && (
                    <>
                      <option value="16:9">16:9</option>
                      <option value="9:16">9:16</option>
                      <option value="1:1">1:1</option>
                    </>
                  )
                )}
              </select>
            </label>
          )}
        </StageRow>
        <StageRow
          label="生成视频"
          enabled={config.videos.enabled}
          onEnabled={(enabled) =>
            change({ ...config, videos: { ...config.videos, enabled } })
          }
        >
          <ModelSelect
            label="视频模型"
            value={config.videos.model_id}
            models={byType.video.filter((model) =>
              model.capabilities.includes("image_to_video"),
            )}
            onChange={(model_id) =>
              change({ ...config, videos: { ...config.videos, model_id } })
            }
          />
          {!videoParameterFields.some((field) => field.key === "aspect_ratio") && (
            <label>
              视频规格
              <select
                value={config.videos.aspect_ratio}
                aria-invalid={Boolean(videoSchema) && Boolean(config.videos.aspect_ratio)}
                onChange={(event) =>
                  change({
                    ...config,
                    videos: { ...config.videos, aspect_ratio: event.target.value },
                  })
                }
              >
                <option value="">使用模型默认</option>
                {videoSchema && config.videos.aspect_ratio ? (
                  <option value={config.videos.aspect_ratio}>
                    当前值 {config.videos.aspect_ratio}（不支持）
                  </option>
                ) : (
                  !config.videos.model_id && (
                    <>
                      <option value="720P">720P</option>
                      <option value="1080P">1080P</option>
                      <option value="16:9">16:9</option>
                      <option value="9:16">9:16</option>
                    </>
                  )
                )}
              </select>
            </label>
          )}
          <label>
            视频时长
            <select
              value={config.videos.duration_mode}
              onChange={(event) =>
                change({
                  ...config,
                  videos: {
                    ...config.videos,
                    duration_mode: event.target.value as "shot" | "fixed",
                  },
                })
              }
            >
              <option value="shot">按镜头设置</option>
              <option value="fixed">固定时长</option>
            </select>
          </label>
          {config.videos.duration_mode === "fixed" &&
            !videoParameterFields.some((field) => field.key === "duration") && (
              <label>
                固定秒数
                <select
                  value={config.videos.duration}
                  aria-invalid={Boolean(videoSchema)}
                  onChange={(event) =>
                    change({
                      ...config,
                      videos: {
                        ...config.videos,
                        duration: Number(event.target.value) as 5 | 10 | 15,
                      },
                    })
                  }
                >
                  {videoSchema ? (
                    <option value={config.videos.duration}>
                      当前值 {config.videos.duration} 秒（不支持，请改为按镜头设置）
                    </option>
                  ) : (
                    <>
                      <option value={5}>5 秒</option>
                      <option value={10}>10 秒</option>
                      <option value={15}>15 秒</option>
                    </>
                  )}
                </select>
              </label>
            )}
          {!!videoParameterFields.length && (
            <GenerationParameterFields
              fields={videoParameterFields}
              values={{
                aspect_ratio: config.videos.aspect_ratio,
                duration: config.videos.duration,
              }}
              onChange={(key, value) =>
                change({
                  ...config,
                  videos: {
                    ...config.videos,
                    ...(key === "duration"
                      ? { duration: Number(value) as 5 | 10 | 15 }
                      : { aspect_ratio: String(value) }),
                  },
                })
              }
            />
          )}
        </StageRow>
      </div>

      <div className="workflow-actions">
        <button
          type="button"
          onClick={() => void save()}
          disabled={
            busy ||
            !dirty ||
            parametersLoading ||
            parametersUnavailable ||
            !!unsupportedParameters.length
          }
        >
          {dirty ? "保存本集配置" : "配置已保存"}
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void start()}
          disabled={
            busy ||
            dirty ||
            parametersLoading ||
            parametersUnavailable ||
            !!unsupportedParameters.length
          }
        >
          开始制作本集
        </button>
      </div>

      <div className="workflow-template-tools">
        <div className="workflow-template-row">
          <label>
            保存模板
            <input
              value={templateName}
              maxLength={80}
              placeholder="例如：竖屏快速制作"
              onChange={(event) => setTemplateName(event.target.value)}
            />
          </label>
          <button
            type="button"
            disabled={
              busy ||
              !templateName.trim() ||
              parametersLoading ||
              parametersUnavailable ||
              !!unsupportedParameters.length
            }
            onClick={() => void createTemplate()}
          >
            保存当前配置
          </button>
        </div>
        <div className="workflow-template-row">
          <label>
            使用模板
            <select
              value={templateId}
              onChange={(event) => {
                setTemplateId(event.target.value);
                setPreview(null);
              }}
            >
              <option value="">选择当前项目模板</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={busy || dirty || !templateId}
            title={dirty ? "请先保存当前配置" : undefined}
            onClick={() => void openPreview()}
          >
            比较配置
          </button>
        </div>
        {selectedTemplate && (
          <details className="workflow-template-manage">
            <summary>管理所选模板</summary>
            <div className="workflow-template-row">
              <label>
                模板名称
                <input
                  value={selectedTemplateName}
                  maxLength={80}
                  onChange={(event) => setSelectedTemplateName(event.target.value)}
                />
              </label>
              <button
                type="button"
                disabled={
                  busy ||
                  !selectedTemplateName.trim() ||
                  selectedTemplateName.trim() === selectedTemplate.name
                }
                onClick={() => void updateTemplate({ name: selectedTemplateName.trim() })}
              >
                重命名
              </button>
              <button
                type="button"
                disabled={
                  busy ||
                  !config ||
                  parametersLoading ||
                  parametersUnavailable ||
                  !!unsupportedParameters.length
                }
                onClick={() => void updateTemplate({ config: config! })}
              >
                以当前配置更新
              </button>
              <button
                type="button"
                className={deleteArmed ? "button-danger" : "button-ghost"}
                disabled={busy}
                onClick={() => void removeTemplate()}
              >
                {deleteArmed ? "确认删除模板" : "删除模板"}
              </button>
            </div>
          </details>
        )}
      </div>

      {preview && (
        <div className="workflow-diff" aria-label="模板配置差异">
          <div className="workflow-diff-head">
            <strong>选择要应用的配置</strong>
            <span>{selected.length} 项已选择</span>
          </div>
          {preview.differences.length ? (
            preview.differences.map((item) => (
              <label
                key={item.field_path}
                className={!item.compatible ? "workflow-diff-blocked" : ""}
              >
                <input
                  type="checkbox"
                  disabled={!item.compatible}
                  checked={selected.includes(item.field_path)}
                  onChange={(event) =>
                    setSelected((current) =>
                      event.target.checked
                        ? [...current, item.field_path]
                        : current.filter((path) => path !== item.field_path),
                    )
                  }
                />
                <span>
                  <strong>{item.label}</strong>
                  <small>
                    {formatValue(item.current_value)} → {formatValue(item.template_value)}
                  </small>
                  {item.reason && <small>{item.reason}</small>}
                  {!!item.candidates?.length && (
                    <small>
                      可选模型：
                      {item.candidates.map((candidate) => candidate.name).join("、")}
                    </small>
                  )}
                </span>
              </label>
            ))
          ) : (
            <p className="muted">当前配置与模板一致。</p>
          )}
          <div className="workflow-actions">
            <button
              type="button"
              className="btn-primary"
              disabled={busy || !selected.length}
              onClick={() => void applyTemplate()}
            >
              应用所选配置
            </button>
            <button type="button" onClick={() => setPreview(null)}>
              取消
            </button>
          </div>
        </div>
      )}
      {notice && (
        <p className="success" role="status">
          {notice}
        </p>
      )}
      {(imageParameters.error || videoParameters.error) && (
        <p className="error">
          无法读取所选模型的参数能力：
          {imageParameters.error || videoParameters.error}
        </p>
      )}
      {!!unsupportedParameters.length && (
        <p className="error" role="alert">
          当前模型不支持已保存的
          {unsupportedParameters
            .map((key) => (key === "duration" ? "视频时长" : "画面规格"))
            .join("、")}
          ，请逐项重新选择后再保存。
        </p>
      )}
      {error && <p className="error">{error}</p>}
    </section>
  );
}

function StageRow({
  label,
  enabled,
  onEnabled,
  children,
}: {
  label: string;
  enabled: boolean;
  onEnabled: (enabled: boolean) => void;
  children: ReactNode;
}) {
  return (
    <div className={`workflow-stage${enabled ? "" : " workflow-stage-disabled"}`}>
      <label className="workflow-stage-toggle">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => onEnabled(event.target.checked)}
        />
        <strong>{label}</strong>
      </label>
      <div className="workflow-stage-fields">{children}</div>
    </div>
  );
}

function ModelSelect({
  label,
  value,
  models,
  onChange,
}: {
  label: string;
  value: string;
  models: Model[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">选择模型</option>
        {models.map((model) => {
          const available =
            model.enabled &&
            model.provider_enabled !== false &&
            (!model.provider_needs_key || model.provider_has_api_key);
          return (
            <option key={model.id} value={model.id} disabled={!available}>
              {model.model_id}
              {available ? "" : "（不可用）"}
            </option>
          );
        })}
      </select>
    </label>
  );
}

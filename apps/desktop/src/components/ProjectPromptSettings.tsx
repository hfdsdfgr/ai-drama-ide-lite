import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { getProject } from "../api/projects";
import {
  getProjectPromptSettings,
  previewProjectPromptStage,
  saveProjectPromptStage,
  type ProjectPromptSettings as PromptSettings,
  type PromptRulePreview,
  type PromptStage,
} from "../api/promptSettings";
import "./ProjectPromptSettings.css";

interface Editor {
  settings: PromptSettings | null;
  projectName: string;
  stageId: string;
  rules: string;
  negativePrompt: string | null;
  negativeMode: "default" | "custom" | "none";
  preview: PromptRulePreview | null;
  loading: boolean;
  busy: "" | "save" | "reset" | "preview";
  error: string;
  notice: string;
}

const EMPTY_EDITOR: Editor = {
  settings: null,
  projectName: "",
  stageId: "",
  rules: "",
  negativePrompt: null,
  negativeMode: "default",
  preview: null,
  loading: false,
  busy: "",
  error: "",
  notice: "",
};

function stageDraft(stage: PromptStage) {
  return {
    stageId: stage.id,
    rules: stage.rules,
    negativePrompt:
      stage.negative_prompt === stage.default_negative_prompt
        ? null
        : stage.negative_prompt,
    negativeMode: (stage.negative_prompt === stage.default_negative_prompt
      ? "default"
      : stage.negative_prompt === ""
        ? "none"
        : "custom") as Editor["negativeMode"],
    preview: {
      stage_id: stage.id,
      rules: stage.rules,
      negative_prompt: stage.negative_prompt,
      system_prompt: stage.preview,
      contract: stage.contract,
    },
  };
}

function isDirty(editor: Editor) {
  const stage = editor.settings?.stages.find((item) => item.id === editor.stageId);
  return Boolean(
    stage &&
    (editor.rules !== stage.rules ||
      (editor.negativePrompt ?? stage.default_negative_prompt) !== stage.negative_prompt),
  );
}

export function ProjectPromptSettings({
  projectId,
  active = true,
  onChooseProject,
}: {
  projectId: string;
  active?: boolean;
  onChooseProject: () => void;
}) {
  // Keep unsaved drafts when users visit another project or another module.
  const [editors, setEditors] = useState<Record<string, Editor>>({});
  const [refreshKey, setRefreshKey] = useState(0);
  const editor = editors[projectId] ?? EMPTY_EDITOR;
  const editorRef = useRef(editor);
  const pending = useRef(new Set<string>());
  editorRef.current = editor;
  const stage = editor.settings?.stages.find((item) => item.id === editor.stageId);
  const dirty = isDirty(editor);
  const blocked = editor.loading || Boolean(editor.busy);
  const validRules = Boolean(stage?.allow_empty_rules || editor.rules.trim());

  const update = useCallback((id: string, patch: Partial<Editor>) => {
    setEditors((previous) => ({
      ...previous,
      [id]: { ...(previous[id] ?? EMPTY_EDITOR), ...patch },
    }));
  }, []);

  useEffect(() => {
    if (!active || !projectId || isDirty(editorRef.current) || editorRef.current.busy) {
      return;
    }
    let cancelled = false;
    update(projectId, { loading: true, error: "" });
    Promise.all([getProjectPromptSettings(projectId), getProject(projectId)])
      .then(([settings, project]) => {
        if (cancelled) return;
        const selected =
          settings.stages.find((item) => item.id === editorRef.current.stageId) ??
          settings.stages[0];
        update(projectId, {
          settings,
          projectName: project.name,
          ...(selected ? stageDraft(selected) : {}),
          loading: false,
          error: "",
        });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          update(projectId, {
            loading: false,
            error: `读取项目提示词失败：${(error as Error).message}。请重试。`,
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [active, projectId, refreshKey, update]);

  async function save(restore = false) {
    if (!stage || !editor.settings || blocked || pending.current.has(projectId)) return;
    const id = projectId;
    const stageId = stage.id;
    pending.current.add(id);
    update(id, { busy: restore ? "reset" : "save", error: "", notice: "" });
    try {
      const settings = await saveProjectPromptStage(id, stageId, {
        expected_revision: editor.settings.revision,
        rules: restore ? null : editor.rules,
        ...(stage.default_negative_prompt !== null && !restore
          ? { negative_prompt: editor.negativePrompt }
          : {}),
      });
      const savedStage = settings.stages.find((item) => item.id === stageId);
      update(id, {
        settings,
        ...(savedStage ? stageDraft(savedStage) : {}),
        notice: restore ? "已恢复本环节默认规则。" : "已保存，仅影响后续生成。",
      });
    } catch (error) {
      update(id, {
        error:
          error instanceof ApiError && error.status === 409
            ? "项目提示词已被其他操作修改。你的编辑已保留，请复制需要保留的内容，再放弃编辑并刷新后重新保存。"
            : `保存提示词失败：${(error as Error).message}`,
      });
    } finally {
      pending.current.delete(id);
      update(id, { busy: "" });
    }
  }

  async function preview() {
    if (!stage || blocked || pending.current.has(projectId)) return;
    const id = projectId;
    pending.current.add(id);
    update(id, { busy: "preview", error: "", notice: "" });
    try {
      const result = await previewProjectPromptStage(id, stage.id, {
        rules: editor.rules,
        ...(stage.default_negative_prompt !== null
          ? { negative_prompt: editor.negativePrompt }
          : {}),
      });
      update(id, { preview: result });
    } catch (error) {
      update(id, { error: `预览规则失败：${(error as Error).message}` });
    } finally {
      pending.current.delete(id);
      update(id, { busy: "" });
    }
  }

  function discard() {
    if (!stage || blocked) return;
    update(projectId, { ...stageDraft(stage), error: "", notice: "" });
    setRefreshKey((key) => key + 1);
  }

  return (
    <section className="project-prompt-settings" aria-labelledby="project-prompt-title">
      <div className="project-prompt-head">
        <div>
          <h3 id="project-prompt-title">项目提示词</h3>
          <p className="muted">
            各环节的自定义规则替换默认创作规则。保存和预览均在本地完成。
          </p>
        </div>
        {projectId && (
          <span className="muted">当前项目：{editor.projectName || projectId}</span>
        )}
      </div>

      {!projectId ? (
        <div className="toolbar">
          <p className="muted">先在主页选择项目，再配置该项目的提示词。</p>
          <button type="button" onClick={onChooseProject}>
            选择项目
          </button>
        </div>
      ) : (
        <>
          {editor.error && (
            <p className="error" role="alert">
              {editor.error}
            </p>
          )}
          {editor.loading && (
            <p className="muted" role="status">
              正在读取提示词…
            </p>
          )}
          {!editor.settings && !editor.loading && (
            <button type="button" onClick={() => setRefreshKey((key) => key + 1)}>
              重试读取
            </button>
          )}
          {editor.settings && !editor.settings.stages.length && (
            <p className="muted">当前没有可配置的创作环节，请刷新或检查后端版本。</p>
          )}
          {stage && (
            <>
              <div className="project-prompt-stage-row">
                <label>
                  创作环节
                  <select
                    value={stage.id}
                    disabled={blocked || dirty}
                    title={dirty ? "请先保存或放弃编辑，再切换环节" : undefined}
                    onChange={(event) => {
                      const selected = editor.settings!.stages.find(
                        (item) => item.id === event.target.value,
                      );
                      if (selected)
                        update(projectId, {
                          ...stageDraft(selected),
                          error: "",
                          notice: "",
                        });
                    }}
                  >
                    {[...new Set(editor.settings!.stages.map((item) => item.group))].map(
                      (group) => (
                        <optgroup key={group} label={group}>
                          {editor
                            .settings!.stages.filter((item) => item.group === group)
                            .map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.label}
                                {item.customized ? " · 自定义" : ""}
                              </option>
                            ))}
                        </optgroup>
                      ),
                    )}
                  </select>
                </label>
                <span
                  className={dirty ? "project-prompt-unsaved" : "muted"}
                  role="status"
                >
                  {dirty
                    ? "有未保存的编辑"
                    : stage.customized
                      ? "已保存自定义规则"
                      : "正在使用默认规则"}
                </span>
                <button
                  type="button"
                  disabled={blocked || dirty}
                  onClick={() => setRefreshKey((key) => key + 1)}
                >
                  刷新
                </button>
              </div>
              <p className="muted">{stage.description}</p>
              <div className="project-prompt-workspace">
                <div className="project-prompt-editor">
                  <label>
                    创作规则
                    <textarea
                      rows={12}
                      maxLength={12000}
                      value={editor.rules}
                      disabled={blocked}
                      onChange={(event) =>
                        update(projectId, {
                          rules: event.target.value,
                          preview: null,
                          notice: "",
                        })
                      }
                    />
                  </label>
                  {!validRules && (
                    <p className="field-help">
                      此环节的创作规则不能为空，请填写后保存或预览。
                    </p>
                  )}
                  {stage.allow_empty_rules && (
                    <p className="field-help">可清空创作规则，仅使用具体素材内容生成。</p>
                  )}
                  {stage.default_negative_prompt !== null && (
                    <>
                      <label>
                        负向提示词
                        <select
                          value={editor.negativeMode}
                          disabled={blocked}
                          onChange={(event) =>
                            update(projectId, {
                              negativeMode: event.target.value as Editor["negativeMode"],
                              negativePrompt:
                                event.target.value === "default"
                                  ? null
                                  : event.target.value === "none"
                                    ? ""
                                    : stage.default_negative_prompt,
                              preview: null,
                              notice: "",
                            })
                          }
                        >
                          <option value="default">使用默认负向词</option>
                          <option value="custom">自定义负向词</option>
                          <option value="none">不使用负向词</option>
                        </select>
                      </label>
                      {editor.negativeMode === "custom" && (
                        <label>
                          自定义负向词内容
                          <textarea
                            rows={3}
                            maxLength={1000}
                            value={editor.negativePrompt ?? ""}
                            disabled={blocked}
                            onChange={(event) =>
                              update(projectId, {
                                negativePrompt: event.target.value,
                                preview: null,
                                notice: "",
                              })
                            }
                          />
                        </label>
                      )}
                    </>
                  )}
                  <div className="toolbar">
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={blocked || !dirty || !validRules}
                      onClick={() => void save()}
                    >
                      {editor.busy === "save" ? "保存中…" : "保存本环节"}
                    </button>
                    <button
                      type="button"
                      disabled={blocked || !validRules}
                      onClick={() => void preview()}
                    >
                      {editor.busy === "preview" ? "预览中…" : "预览规则"}
                    </button>
                    <button
                      type="button"
                      disabled={blocked || dirty || !stage.customized}
                      title={dirty ? "请先保存或放弃当前编辑" : undefined}
                      onClick={() => void save(true)}
                    >
                      {editor.busy === "reset" ? "恢复中…" : "恢复默认"}
                    </button>
                    {dirty && (
                      <button type="button" disabled={blocked} onClick={discard}>
                        放弃编辑并刷新
                      </button>
                    )}
                  </div>
                  {dirty && (
                    <p className="field-help">
                      请先保存或放弃编辑，再切换环节。切换页面或项目会保留本次编辑。
                    </p>
                  )}
                  {editor.notice && (
                    <p className="project-prompt-notice" role="status">
                      {editor.notice}
                    </p>
                  )}
                </div>
                <div className="project-prompt-inspector">
                  <h4>规则预览</h4>
                  <p className="field-help">
                    这里展示本环节生效的规则。生成时会加入当前项目的小说、剧本、资产或镜头内容。
                  </p>
                  {editor.preview ? (
                    <>
                      <pre
                        className="project-prompt-preview"
                        tabIndex={0}
                        aria-label="组装后的规则"
                      >
                        {editor.preview.system_prompt}
                      </pre>
                      {editor.preview.negative_prompt && (
                        <details>
                          <summary>生效的负向提示词</summary>
                          <pre>{editor.preview.negative_prompt}</pre>
                        </details>
                      )}
                    </>
                  ) : (
                    <p className="muted">规则已修改，点击「预览规则」查看当前编辑。</p>
                  )}
                  {stage.contract && (
                    <details>
                      <summary>固定输出要求（只读）</summary>
                      <pre>{stage.contract}</pre>
                    </details>
                  )}
                  <details>
                    <summary>查看默认创作规则</summary>
                    <pre>{stage.default_rules}</pre>
                  </details>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}

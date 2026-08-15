import { useCallback, useEffect, useState } from "react";

import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  rectSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { listAssets } from "../api/assets";
import { getCurrentAssetVersion } from "../api/asset_versions";
import { getApiBase } from "../api/client";
import {
  generateImage,
  getCurrentImageVersion,
  getImageJob,
} from "../api/images";
import { listNovels } from "../api/novels";
import { listProjects } from "../api/projects";
import { listModels } from "../api/providers";
import {
  deleteShot,
  getEpisodeDetail,
  getSceneDetail,
  listEpisodes,
  reorderShots,
  updateShot,
} from "../api/script";
import type { AssetVersion } from "../types/asset_version";
import type { GenerationJob } from "../types/generation";
import type { Novel } from "../types/novel";
import type { Project } from "../types/project";
import type { Model } from "../types/provider";
import type { AssetCard, AssetType } from "../types/story";
import type {
  Episode,
  EpisodeDetail,
  SceneDetail,
  Shot,
} from "../types/script";

const ASSET_TYPE_LABELS: Record<AssetType, string> = {
  character: "角色",
  location: "场景",
  prop: "道具",
};

interface ReferenceAsset {
  asset: AssetCard;
  version: AssetVersion;
}

function SortableShotCard({
  shot,
  sceneId,
  isSelected,
  imageUrl,
  generating,
  onOpen,
}: {
  shot: Shot;
  sceneId: string;
  isSelected: boolean;
  imageUrl: string | null;
  generating: boolean;
  onOpen: (sceneId: string, shot: Shot) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: shot.id });

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
      }}
      className={[
        "shot-card",
        isSelected ? "active" : "",
        isDragging ? "shot-card-dragging" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      onClick={() => onOpen(sceneId, shot)}
      {...attributes}
      {...listeners}
    >
      <div className="shot-frame">
        {imageUrl ? (
          <img src={imageUrl} alt={`Shot ${shot.shot_number ?? "-"}`} />
        ) : (
          <span>{generating ? "生成中…" : "待生成"}</span>
        )}
      </div>
      <div className="shot-meta">
        <span className="shot-number">Shot {shot.shot_number ?? "-"}</span>
        {shot.shot_type && <span className="shot-type">{shot.shot_type}</span>}
      </div>
      <div className="shot-submeta">
        {shot.duration ? <span>{shot.duration}s</span> : null}
        {shot.camera ? <span>{shot.camera}</span> : null}
      </div>
      <span
        className={
          imageUrl
            ? "shot-status shot-status-completed"
            : generating
              ? "shot-status shot-status-running"
              : "shot-status shot-status-pending"
        }
      >
        {imageUrl ? "已完成" : generating ? "生成中" : "待生成"}
      </span>
    </div>
  );
}

export function StoryboardPage({ active }: { active: boolean }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novelId, setNovelId] = useState("");
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState<string | null>(null);
  const [episodeDetail, setEpisodeDetail] = useState<EpisodeDetail | null>(null);
  const [sceneDetails, setSceneDetails] = useState<Record<string, SceneDetail>>({});
  const [selectedShotSceneId, setSelectedShotSceneId] = useState<string | null>(
    null,
  );
  const [selectedShotId, setSelectedShotId] = useState<string | null>(null);
  const [shotDetailDraft, setShotDetailDraft] = useState<Shot | null>(null);
  const [confirmShotDeleteId, setConfirmShotDeleteId] = useState<string | null>(
    null,
  );
  const [error, setError] = useState("");
  const [imageModels, setImageModels] = useState<Model[]>([]);
  const [imageModelId, setImageModelId] = useState("");
  const [shotVersions, setShotVersions] = useState<Record<string, AssetVersion>>(
    {},
  );
  const [imageJob, setImageJob] = useState<GenerationJob | null>(null);
  const [generatingShotId, setGeneratingShotId] = useState<string | null>(null);
  const [apiBase, setApiBase] = useState("");
  const [referenceAssets, setReferenceAssets] = useState<ReferenceAsset[]>([]);
  const [selectedReferenceAssetIds, setSelectedReferenceAssetIds] = useState<
    string[]
  >([]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  useEffect(() => {
    if (!active) return;
    listProjects()
      .then(setProjects)
      .catch((e) => setError((e as Error).message));
    void getApiBase().then(setApiBase).catch(() => {});
    listModels({ model_type: "image", enabled_only: true })
      .then((models) => {
        const usable = models
          .filter(
            (m) =>
              m.capabilities.includes("text_to_image") ||
              m.capabilities.includes("reference_image") ||
              m.capabilities.includes("image_to_image"),
          )
          .sort((a, b) => Number(b.is_default_image) - Number(a.is_default_image));
        setImageModels(usable);
        setImageModelId((prev) =>
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
    setShotVersions({});
    setGeneratingShotId(null);
    setImageJob(null);
    setReferenceAssets([]);
    setSelectedReferenceAssetIds([]);
    setNovelId("");
    setEpisodes([]);
    setEpisodeDetail(null);
    void refreshNovels(projectId);
  }, [projectId, refreshNovels]);

  useEffect(() => {
    if (!projectId || !apiBase) return;
    setError("");
    listAssets(projectId)
      .then(async (assets) => {
        const references: ReferenceAsset[] = [];
        const results = await Promise.allSettled(
          assets.map((asset) =>
            getCurrentAssetVersion(projectId, asset.asset_id),
          ),
        );
        results.forEach((result, index) => {
          if (result.status === "fulfilled" && result.value) {
            references.push({
              asset: assets[index],
              version: result.value,
            });
          }
        });
        setReferenceAssets(references);
      })
      .catch((e) => setError((e as Error).message));
  }, [projectId, apiBase]);

  useEffect(() => {
    if (!projectId || !novelId) return;
    setEpisodes([]);
    setEpisodeDetail(null);
    listEpisodes(projectId, novelId)
      .then(setEpisodes)
      .catch((e) => setError((e as Error).message));
  }, [projectId, novelId]);

  const loadEpisodeDetail = useCallback(
    async (episodeId: string) => {
      if (!projectId) return;
      setError("");
      setSelectedShotSceneId(null);
      setSelectedShotId(null);
      setShotDetailDraft(null);
      setConfirmShotDeleteId(null);
      try {
        const detail = await getEpisodeDetail(projectId, episodeId);
        setEpisodeDetail(detail);
        const sceneMap: Record<string, SceneDetail> = {};
        for (const scene of detail.scenes) {
          sceneMap[scene.id] = await getSceneDetail(projectId, scene.id);
        }
        setSceneDetails(sceneMap);
        const shots = Object.values(sceneMap).flatMap((scene) => scene.shots);
        const versionMap: Record<string, AssetVersion> = {};
        const results = await Promise.allSettled(
          shots.map((shot) =>
            getCurrentImageVersion(projectId, "shot", shot.id),
          ),
        );
        results.forEach((result, index) => {
          if (result.status === "fulfilled" && result.value) {
            versionMap[shots[index].id] = result.value;
          }
        });
        setShotVersions(versionMap);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [projectId],
  );

  async function selectEpisode(episodeId: string) {
    setSelectedEpisodeId(episodeId);
    await loadEpisodeDetail(episodeId);
  }

  function openShotDetail(sceneId: string, shot: Shot) {
    setSelectedShotSceneId(sceneId);
    setSelectedShotId(shot.id);
    setShotDetailDraft({ ...shot });
    setConfirmShotDeleteId(null);
    setImageJob(null);
    setSelectedReferenceAssetIds([]);
  }

  function closeShotDetail() {
    setSelectedShotSceneId(null);
    setSelectedShotId(null);
    setShotDetailDraft(null);
    setConfirmShotDeleteId(null);
  }

  async function saveShotDetail() {
    if (
      !projectId ||
      !selectedShotSceneId ||
      !selectedShotId ||
      !shotDetailDraft
    ) {
      return;
    }
    setError("");
    try {
      await updateShot(projectId, selectedShotSceneId, selectedShotId, {
        shot_type: shotDetailDraft.shot_type,
        camera: shotDetailDraft.camera,
        characters: shotDetailDraft.characters,
        action: shotDetailDraft.action,
        lighting: shotDetailDraft.lighting,
        dialogue: shotDetailDraft.dialogue,
        duration: shotDetailDraft.duration,
        prompt: shotDetailDraft.prompt,
      });
      const detail = await getSceneDetail(projectId, selectedShotSceneId);
      setSceneDetails((prev) => ({ ...prev, [selectedShotSceneId]: detail }));
      closeShotDetail();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function runShotImageGeneration() {
    if (!projectId || !selectedShotId || !imageModelId) return;
    setGeneratingShotId(selectedShotId);
    setImageJob(null);
    setError("");
    try {
      const job = await generateImage(projectId, {
        target_type: "shot",
        target_id: selectedShotId,
        model_id: imageModelId,
        capability: "text_to_image",
        reference_asset_ids: selectedReferenceAssetIds,
      });
      setImageJob(job);
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const updated = await getImageJob(projectId, job.job_id);
        setImageJob(updated);
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          if (updated.status === "completed") {
            const version = await getCurrentImageVersion(
              projectId,
              "shot",
              selectedShotId,
            );
            if (version) {
              setShotVersions((prev) => ({
                ...prev,
                [selectedShotId]: version,
              }));
            }
          }
          break;
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGeneratingShotId((prev) =>
        prev === selectedShotId ? null : prev,
      );
    }
  }

  async function handleDeleteSelectedShot() {
    if (!projectId || !selectedShotSceneId || !selectedShotId) return;
    if (confirmShotDeleteId !== selectedShotId) {
      setConfirmShotDeleteId(selectedShotId);
      return;
    }
    setConfirmShotDeleteId(null);
    setError("");
    try {
      await deleteShot(projectId, selectedShotSceneId, selectedShotId);
      const detail = await getSceneDetail(projectId, selectedShotSceneId);
      setSceneDetails((prev) => ({ ...prev, [selectedShotSceneId]: detail }));
      setShotVersions((prev) => {
        const next = { ...prev };
        delete next[selectedShotId];
        return next;
      });
      closeShotDetail();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function persistReorder(sceneId: string, shotIds: string[]) {
    if (!projectId) return;
    setError("");
    try {
      const detail = await reorderShots(projectId, sceneId, shotIds);
      setSceneDetails((prev) => ({ ...prev, [sceneId]: detail }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function handleDragEnd(sceneId: string, event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const shots = sceneDetails[sceneId]?.shots ?? [];
    const oldIndex = shots.findIndex((s) => s.id === active.id);
    const newIndex = shots.findIndex((s) => s.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const reordered = arrayMove(shots, oldIndex, newIndex);
    setSceneDetails((prev) => ({
      ...prev,
      [sceneId]: { ...prev[sceneId], shots: reordered },
    }));
    void persistReorder(sceneId, reordered.map((s) => s.id));
  }

  return (
    <div className="page storyboard-page">
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
              <p className="muted">还没有分集，请在「剧本」页生成。</p>
            ) : (
              <ul className="chapter-tree">
                {episodes.map((ep) => (
                  <li key={ep.id}>
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
                  const shots = sceneDetails[scene.id]?.shots ?? [];
                  return (
                    <div className="card" key={scene.id}>
                      <div className="scene-head">
                        <strong>{scene.slugline || scene.title}</strong>
                        <span className="badge">{shots.length} 个镜头</span>
                      </div>
                      {shots.length === 0 ? (
                        <p className="muted">
                          该场景还没有镜头，请在「剧本」页生成分镜。
                        </p>
                      ) : (
                        <DndContext
                          sensors={sensors}
                          collisionDetection={closestCenter}
                          onDragEnd={(event) => handleDragEnd(scene.id, event)}
                        >
                          <SortableContext
                            items={shots.map((s) => s.id)}
                            strategy={rectSortingStrategy}
                          >
                            <div className="shot-board">
                              {shots.map((shot) => {
                                const version = shotVersions[shot.id];
                                const imageUrl = version
                                  ? `${apiBase}${version.file_url}`
                                  : null;
                                return (
                                  <SortableShotCard
                                    key={shot.id}
                                    shot={shot}
                                    sceneId={scene.id}
                                    isSelected={selectedShotId === shot.id}
                                    imageUrl={imageUrl}
                                    generating={generatingShotId === shot.id}
                                    onOpen={openShotDetail}
                                  />
                                );
                              })}
                            </div>
                          </SortableContext>
                        </DndContext>
                      )}
                    </div>
                  );
                })
              )}
            </>
          ) : (
            <div className="novel-empty">
              <p className="muted">从左侧选择项目和分集查看分镜板。</p>
            </div>
          )}
        </section>

        <aside className="novel-inspector">
          {selectedShotId && shotDetailDraft ? (
            <div className="card inspector-card shot-detail">
              <div className="panel-head">
                <h3>镜头详情</h3>
                <p className="muted">Shot {shotDetailDraft.shot_number ?? "-"}</p>
              </div>
              <label>
                景别
                <input
                  value={shotDetailDraft.shot_type}
                  onChange={(e) =>
                    setShotDetailDraft({
                      ...shotDetailDraft,
                      shot_type: e.target.value,
                    })
                  }
                  placeholder="远景 / 全景 / 中景 / 近景 / 特写"
                />
              </label>
              <label>
                运镜
                <input
                  value={shotDetailDraft.camera}
                  onChange={(e) =>
                    setShotDetailDraft({
                      ...shotDetailDraft,
                      camera: e.target.value,
                    })
                  }
                  placeholder="推 / 拉 / 摇 / 移 / 跟 / 升降"
                />
              </label>
              <label>
                角色
                <input
                  value={shotDetailDraft.characters}
                  onChange={(e) =>
                    setShotDetailDraft({
                      ...shotDetailDraft,
                      characters: e.target.value,
                    })
                  }
                />
              </label>
              <label>
                动作
                <textarea
                  value={shotDetailDraft.action}
                  onChange={(e) =>
                    setShotDetailDraft({
                      ...shotDetailDraft,
                      action: e.target.value,
                    })
                  }
                  rows={2}
                />
              </label>
              <label>
                光影
                <input
                  value={shotDetailDraft.lighting}
                  onChange={(e) =>
                    setShotDetailDraft({
                      ...shotDetailDraft,
                      lighting: e.target.value,
                    })
                  }
                />
              </label>
              <label>
                台词
                <textarea
                  value={shotDetailDraft.dialogue}
                  onChange={(e) =>
                    setShotDetailDraft({
                      ...shotDetailDraft,
                      dialogue: e.target.value,
                    })
                  }
                  rows={2}
                />
              </label>
              <label>
                时长（秒）
                <input
                  type="number"
                  min={0.5}
                  max={120}
                  step={0.5}
                  value={shotDetailDraft.duration}
                  onChange={(e) =>
                    setShotDetailDraft({
                      ...shotDetailDraft,
                      duration: Number(e.target.value) || 0,
                    })
                  }
                />
              </label>
              <label>
                提示词
                <textarea
                  value={shotDetailDraft.prompt}
                  onChange={(e) =>
                    setShotDetailDraft({
                      ...shotDetailDraft,
                      prompt: e.target.value,
                    })
                  }
                  rows={3}
                  placeholder="视觉提示词（后续生图使用）"
                />
              </label>
              <div className="card image-generate-card">
                <div className="sidebar-head">
                  <h3>分镜图片</h3>
                </div>
                {imageModels.length > 0 ? (
                  <label>
                    图片模型
                    <select
                      value={imageModelId}
                      onChange={(e) => setImageModelId(e.target.value)}
                      disabled={generatingShotId === selectedShotId}
                    >
                      {imageModels.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.model_id}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <p className="muted">
                    还没有可用的图片模型，请先在「设置」启用一个支持文生图的模型。
                  </p>
                )}
                <div className="reference-picker">
                  <div className="sidebar-head">
                    <h4>参考图（可选）</h4>
                  </div>
                  {referenceAssets.length === 0 ? (
                    <p className="muted">
                      暂无可用的资产图片参考图。先在「资产」页生成角色或场景图片。
                    </p>
                  ) : (
                    referenceAssets.map((ref) => (
                      <label
                        key={ref.asset.asset_id}
                        className="reference-option"
                      >
                        <input
                          type="checkbox"
                          checked={selectedReferenceAssetIds.includes(
                            ref.asset.asset_id,
                          )}
                          onChange={(e) => {
                            const id = ref.asset.asset_id;
                            setSelectedReferenceAssetIds((prev) =>
                              e.target.checked
                                ? [...prev, id]
                                : prev.filter((item) => item !== id),
                            );
                          }}
                        />
                        <img
                          src={`${apiBase}${ref.version.file_url}`}
                          alt={ref.asset.name}
                        />
                        <span>
                          {ASSET_TYPE_LABELS[ref.asset.asset_type]} ·{" "}
                          {ref.asset.name}
                        </span>
                      </label>
                    ))
                  )}
                </div>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={
                    !imageModelId || generatingShotId === selectedShotId
                  }
                  onClick={runShotImageGeneration}
                >
                  {generatingShotId === selectedShotId ? "生成中…" : "生成图片"}
                </button>
                <p className="muted">生成会调用 API，可能产生费用。</p>
                {imageJob && imageJob.status !== "completed" && (
                  <p className="muted">
                    {imageJob.status === "running"
                      ? "生成中……"
                      : imageJob.status === "failed"
                        ? "生成失败"
                        : imageJob.status === "cancelled"
                          ? "已取消"
                          : "排队中"}
                    {imageJob.error ? ` · ${imageJob.error}` : ""}
                  </p>
                )}
              </div>
              <div className="toolbar">
                <button
                  type="button"
                  className="btn-primary"
                  onClick={saveShotDetail}
                >
                  保存
                </button>
                <button type="button" onClick={closeShotDetail}>
                  取消
                </button>
                {confirmShotDeleteId === selectedShotId ? (
                  <>
                    <button
                      type="button"
                      className="button-danger"
                      onClick={handleDeleteSelectedShot}
                    >
                      确认删除
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmShotDeleteId(null)}
                    >
                      取消
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    className="button-danger button-ghost"
                    onClick={handleDeleteSelectedShot}
                  >
                    删除
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="panel-head">
              <h3>镜头详情</h3>
              <p className="muted">点击左侧镜头卡片查看和编辑。</p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

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

import { listNovels } from "../api/novels";
import { listProjects } from "../api/projects";
import {
  deleteShot,
  getEpisodeDetail,
  getSceneDetail,
  listEpisodes,
  reorderShots,
  updateShot,
} from "../api/script";
import type { Novel } from "../types/novel";
import type { Project } from "../types/project";
import type {
  Episode,
  EpisodeDetail,
  SceneDetail,
  Shot,
} from "../types/script";

function SortableShotCard({
  shot,
  sceneId,
  isSelected,
  onOpen,
}: {
  shot: Shot;
  sceneId: string;
  isSelected: boolean;
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
      <div className="shot-frame">待生成</div>
      <div className="shot-meta">
        <span className="shot-number">Shot {shot.shot_number ?? "-"}</span>
        {shot.shot_type && <span className="shot-type">{shot.shot_type}</span>}
      </div>
      <div className="shot-submeta">
        {shot.duration ? <span>{shot.duration}s</span> : null}
        {shot.camera ? <span>{shot.camera}</span> : null}
      </div>
      <span className="shot-status shot-status-pending">待生成</span>
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

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  useEffect(() => {
    if (!active) return;
    listProjects()
      .then(setProjects)
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
                              {shots.map((shot) => (
                                <SortableShotCard
                                  key={shot.id}
                                  shot={shot}
                                  sceneId={scene.id}
                                  isSelected={selectedShotId === shot.id}
                                  onOpen={openShotDetail}
                                />
                              ))}
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

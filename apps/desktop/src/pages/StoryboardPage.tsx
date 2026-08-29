import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
} from "react";

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
import {
  decideDialogueReview,
  listDialogueReviews,
  runDialogueReview,
  submitManualReview,
  type DialogueReview,
} from "../api/dialogue_reviews";
import {
  decideVisualReview,
  listVisualReviews,
  runVisualReview,
  submitManualVisualReview,
  type VisualReview,
  type VisualReviewType,
} from "../api/visual_reviews";
import {
  decideStoryReview,
  listStoryReviews,
  runStoryReview,
  submitManualStoryReview,
  type StoryReview,
} from "../api/story_reviews";
import {
  composeVideos,
  dubShot,
  getComposeJob,
  getComposedVideoVersion,
  generateVideo,
  getCurrentVoicedVersion,
  getCurrentVideoVersion,
  getVideoJob,
  uploadAudioFile,
} from "../api/videos";
import { getJob } from "../api/jobs";
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
import type { JobOut } from "../types/job";
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
  videoUrl,
  onOpen,
  onPlayVideo,
}: {
  shot: Shot;
  sceneId: string;
  isSelected: boolean;
  imageUrl: string | null;
  generating: boolean;
  videoUrl: string | null;
  onOpen: (sceneId: string, shot: Shot) => void;
  onPlayVideo: () => void;
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
        {videoUrl && (
          <button
            type="button"
            className="shot-video-badge"
            title="播放视频"
            onClick={(e) => {
              e.stopPropagation();
              onPlayVideo();
            }}
            onPointerDown={(e) => e.stopPropagation()}
          >
            ▶
          </button>
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

export function StoryboardPage({
  active,
  jumpToShotId = null,
  onJumpConsumed,
}: {
  active: boolean;
  jumpToShotId?: string | null;
  onJumpConsumed?: () => void;
}) {
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
  const [videoModels, setVideoModels] = useState<Model[]>([]);
  const [videoModelId, setVideoModelId] = useState("");
  const [videoPrompt, setVideoPrompt] = useState("");
  const [videoDuration, setVideoDuration] = useState(5);
  const [withAudio, setWithAudio] = useState(false);
  const [audioModels, setAudioModels] = useState<Model[]>([]);
  const [llmModels, setLlmModels] = useState<Model[]>([]);
  const [reviewMode, setReviewMode] = useState<"model" | "manual">("model");
  const [asrModelId, setAsrModelId] = useState("");
  const [reviewScriptModelId, setReviewScriptModelId] = useState("");
  const [manualDetected, setManualDetected] = useState("");
  const [latestReview, setLatestReview] = useState<DialogueReview | null>(null);
  const [reviewingJob, setReviewingJob] = useState<JobOut | null>(null);
  const [reviewDeciding, setReviewDeciding] = useState(false);
  const [visionModels, setVisionModels] = useState<Model[]>([]);
  const [visualModelId, setVisualModelId] = useState("");
  const [visualReviewType, setVisualReviewType] =
    useState<VisualReviewType>("character");
  const [visualMode, setVisualMode] = useState<"model" | "manual">("model");
  const [latestVisualReview, setLatestVisualReview] =
    useState<VisualReview | null>(null);
  const [visualReviewingJob, setVisualReviewingJob] = useState<JobOut | null>(
    null,
  );
  const [visualManualIssue, setVisualManualIssue] = useState("");
  const [visualDeciding, setVisualDeciding] = useState(false);
  const [storyReviewingJob, setStoryReviewingJob] = useState<JobOut | null>(
    null,
  );
  const [latestStoryReview, setLatestStoryReview] =
    useState<StoryReview | null>(null);
  const [storyModelId, setStoryModelId] = useState("");
  const [storyManualIssue, setStoryManualIssue] = useState("");
  const [storyDeciding, setStoryDeciding] = useState(false);
  const [voiceModelId, setVoiceModelId] = useState("");
  const [shotVersions, setShotVersions] = useState<Record<string, AssetVersion>>(
    {},
  );
  const [shotVideoVersions, setShotVideoVersions] = useState<
    Record<string, AssetVersion>
  >({});
  const [shotVoicedVersions, setShotVoicedVersions] = useState<
    Record<string, AssetVersion>
  >({});
  const [composedVersions, setComposedVersions] = useState<
    Record<string, AssetVersion>
  >({});
  const [composingSceneId, setComposingSceneId] = useState("");
  const [shotVideoVersion, setShotVideoVersion] =
    useState<AssetVersion | null>(null);
  const [shotVoicedVersion, setShotVoicedVersion] =
    useState<AssetVersion | null>(null);
  const [imageJob, setImageJob] = useState<GenerationJob | null>(null);
  const [videoJob, setVideoJob] = useState<GenerationJob | null>(null);
  const [dubJob, setDubJob] = useState<JobOut | null>(null);
  const [audioFilePath, setAudioFilePath] = useState("");
  const [audioFileName, setAudioFileName] = useState("");
  const [generatingShotId, setGeneratingShotId] = useState<string | null>(null);
  const [generatingVideoShotId, setGeneratingVideoShotId] = useState<
    string | null
  >(null);
  const [generatingDubShotId, setGeneratingDubShotId] = useState<string | null>(
    null,
  );
  const [apiBase, setApiBase] = useState("");
  const [referenceAssets, setReferenceAssets] = useState<ReferenceAsset[]>([]);
  const [selectedReferenceAssetIds, setSelectedReferenceAssetIds] = useState<
    string[]
  >([]);
  const [zoomImageUrl, setZoomImageUrl] = useState<string | null>(null);
  const [zoomVideoUrl, setZoomVideoUrl] = useState<string | null>(null);
  const autoMatchedShotIdRef = useRef<string | null>(null);

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
    listModels({ model_type: "video", enabled_only: true })
      .then((models) => {
        const usable = models
          .filter((m) => m.capabilities.includes("image_to_video"))
          .sort((a, b) => Number(b.is_default_video) - Number(a.is_default_video));
        setVideoModels(usable);
        setVideoModelId((prev) =>
          usable.some((m) => m.id === prev) ? prev : (usable[0]?.id ?? ""),
        );
      })
      .catch((e) => setError((e as Error).message));
    listModels({ model_type: "audio", enabled_only: true })
      .then((models) => {
        const usable = models.filter((m) =>
          m.capabilities.includes("text_to_speech"),
        );
        setAudioModels(usable);
        setVoiceModelId((prev) =>
          usable.some((m) => m.id === prev) ? prev : (usable[0]?.id ?? ""),
        );
      })
      .catch((e) => setError((e as Error).message));
    listModels({ model_type: "llm", enabled_only: true })
      .then((models) => {
        setLlmModels(models);
        const vision = models.filter((m) => m.capabilities.includes("vision"));
        setVisionModels(vision);
        setVisualModelId((prev) =>
          vision.some((m) => m.id === prev) ? prev : (vision[0]?.id ?? ""),
        );
        setReviewScriptModelId((prev) =>
          models.some((m) => m.id === prev) ? prev : (models[0]?.id ?? ""),
        );
        setStoryModelId((prev) =>
          models.some((m) => m.id === prev) ? prev : (models[0]?.id ?? ""),
        );
      })
      .catch((e) => setError((e as Error).message));
  }, [active]);

  useEffect(() => {
    if (!jumpToShotId || !projectId) return;
    let cancelled = false;
    (async () => {
      try {
        for (const sceneId of Object.keys(sceneDetails)) {
          const shot = sceneDetails[sceneId]?.shots.find(
            (s) => s.id === jumpToShotId,
          );
          if (shot) {
            openShotDetail(sceneId, shot);
            onJumpConsumed?.();
            return;
          }
        }
        const episodes = await listEpisodes(projectId);
        for (const episode of episodes) {
          const detail = await getEpisodeDetail(projectId, episode.id);
          for (const scene of detail.scenes) {
            const sceneDetail = await getSceneDetail(projectId, scene.id);
            const shot = sceneDetail.shots.find(
              (s) => s.id === jumpToShotId,
            );
            if (shot && !cancelled) {
              await selectEpisode(episode.id);
              openShotDetail(scene.id, shot);
              onJumpConsumed?.();
              return;
            }
          }
        }
      } catch {
        // 跳转失败不阻塞页面
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jumpToShotId, projectId]);

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
    setShotVideoVersions({});
    setShotVoicedVersions({});
    setShotVideoVersion(null);
    setShotVoicedVersion(null);
    setGeneratingShotId(null);
    setGeneratingVideoShotId(null);
    setGeneratingDubShotId(null);
    setImageJob(null);
    setVideoJob(null);
    setDubJob(null);
    setAudioFilePath("");
    setAudioFileName("");
    setVideoPrompt("");
    setVideoDuration(5);
    setReferenceAssets([]);
    setSelectedReferenceAssetIds([]);
    setNovelId("");
    setEpisodes([]);
    setEpisodeDetail(null);
    void refreshNovels(projectId);
  }, [projectId, refreshNovels]);

  useEffect(() => {
    if (!active || !projectId) return;
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
  }, [active, projectId]);

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
        const videoMap: Record<string, AssetVersion> = {};
        const videoResults = await Promise.allSettled(
          shots.map((shot) => getCurrentVideoVersion(projectId, shot.id)),
        );
        videoResults.forEach((result, index) => {
          if (result.status === "fulfilled" && result.value) {
            videoMap[shots[index].id] = result.value;
          }
        });
        setShotVideoVersions(videoMap);
        const voicedMap: Record<string, AssetVersion> = {};
        const voicedResults = await Promise.allSettled(
          shots.map((shot) => getCurrentVoicedVersion(projectId, shot.id)),
        );
        voicedResults.forEach((result, index) => {
          if (result.status === "fulfilled" && result.value) {
            voicedMap[shots[index].id] = result.value;
          }
        });
        setShotVoicedVersions(voicedMap);
        const composedMap: Record<string, AssetVersion> = {};
        const composedResults = await Promise.allSettled(
          detail.scenes.map((scene) =>
            getComposedVideoVersion(projectId, "scene_video", scene.id),
          ),
        );
        composedResults.forEach((result, index) => {
          if (result.status === "fulfilled" && result.value) {
            composedMap[detail.scenes[index].id] = result.value;
          }
        });
        setComposedVersions(composedMap);
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

  const autoMatchReferenceAssets = useCallback(
    (sceneId: string, shot: Shot): string[] => {
      const scene = sceneDetails[sceneId];
      const shotText = shot.characters || "";
      const sceneText = `${scene?.scene.slugline || ""} ${scene?.scene.action || ""}`;
      return referenceAssets
        .filter((ref) => {
          const name = ref.asset.name;
          if (!name) return false;
          if (ref.asset.asset_type === "character") {
            return shotText.includes(name);
          }
          if (ref.asset.asset_type === "location") {
            return sceneText.includes(name);
          }
          return false;
        })
        .map((ref) => ref.asset.asset_id);
    },
    [sceneDetails, referenceAssets],
  );

  function openShotDetail(sceneId: string, shot: Shot) {
    setSelectedShotSceneId(sceneId);
    setSelectedShotId(shot.id);
    setShotDetailDraft({ ...shot });
    setConfirmShotDeleteId(null);
    setImageJob(null);
    setVideoJob(null);
    setVideoPrompt(shot.prompt || shot.action || "");
    setVideoDuration(Math.max(5, Math.min(15, Math.round(shot.duration || 5))));
    setSelectedReferenceAssetIds(autoMatchReferenceAssets(sceneId, shot));
    autoMatchedShotIdRef.current = null;
    setShotVideoVersion(null);
    setShotVoicedVersion(null);
    setDubJob(null);
    setAudioFilePath("");
    setAudioFileName("");
    setLatestReview(null);
    setReviewingJob(null);
    setManualDetected("");
    setLatestVisualReview(null);
    setVisualReviewingJob(null);
    setVisualManualIssue("");
    setLatestStoryReview(null);
    setStoryReviewingJob(null);
    setStoryManualIssue("");
    void getCurrentVideoVersion(projectId, shot.id)
      .then(setShotVideoVersion)
      .catch(() => setShotVideoVersion(null));
    void getCurrentVoicedVersion(projectId, shot.id)
      .then(setShotVoicedVersion)
      .catch(() => setShotVoicedVersion(null));
    void listDialogueReviews(projectId, shot.id)
      .then((reviews) => {
        if (reviews.length > 0) setLatestReview(reviews[0]);
      })
      .catch(() => setLatestReview(null));
    void listVisualReviews(projectId, shot.id)
      .then((reviews) => {
        if (reviews.length > 0) setLatestVisualReview(reviews[0]);
      })
      .catch(() => setLatestVisualReview(null));
    void listStoryReviews(projectId, shot.id)
      .then((reviews) => {
        if (reviews.length > 0) setLatestStoryReview(reviews[0]);
      })
      .catch(() => setLatestStoryReview(null));
  }

  function closeShotDetail() {
    setSelectedShotSceneId(null);
    setSelectedShotId(null);
    setShotDetailDraft(null);
    setConfirmShotDeleteId(null);
    setVideoJob(null);
    setShotVideoVersion(null);
    setShotVoicedVersion(null);
    setDubJob(null);
  }

  useEffect(() => {
    if (!selectedShotId || !selectedShotSceneId || !shotDetailDraft) return;
    if (autoMatchedShotIdRef.current === selectedShotId) return;
    if (referenceAssets.length === 0) return;
    setSelectedReferenceAssetIds(
      autoMatchReferenceAssets(selectedShotSceneId, shotDetailDraft),
    );
    autoMatchedShotIdRef.current = selectedShotId;
  }, [
    selectedShotId,
    selectedShotSceneId,
    shotDetailDraft,
    referenceAssets,
    autoMatchReferenceAssets,
  ]);

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

  async function runShotVideoGeneration() {
    if (!projectId || !selectedShotId || !videoModelId) return;
    const prompt = videoPrompt.trim();
    if (!prompt) {
      setError("请输入视频生成提示词");
      return;
    }
    setGeneratingVideoShotId(selectedShotId);
    setVideoJob(null);
    setError("");
    try {
      const videoModel = videoModels.find((m) => m.id === videoModelId);
      const supportsAudio =
        videoModel?.capabilities.includes("video_audio") ?? false;
      const supportsDialogue =
        videoModel?.capabilities.includes("video_dialogue") ?? false;
      const job = await generateVideo(projectId, {
        target_id: selectedShotId,
        model_id: videoModelId,
        prompt,
        duration: videoDuration,
        with_audio: (supportsAudio || supportsDialogue) && withAudio,
        reference_asset_ids: selectedReferenceAssetIds,
      });
      setVideoJob(job);
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const updated = await getVideoJob(projectId, job.job_id);
        setVideoJob(updated);
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          if (updated.status === "completed") {
            const version = await getCurrentVideoVersion(
              projectId,
              selectedShotId,
            );
            setShotVideoVersion(version);
          }
          break;
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGeneratingVideoShotId((prev) =>
        prev === selectedShotId ? null : prev,
      );
    }
  }

  useEffect(() => {
    // 切换视频模型时同步“带音频”开关：
    // 支持原生对白/台词的模型默认开启；只支持音效或不支持的模型默认无声。
    const model = videoModels.find((m) => m.id === videoModelId);
    setWithAudio(model?.capabilities.includes("video_dialogue") ?? false);
  }, [videoModelId, videoModels]);

  async function handleComposeScene(sceneId: string) {
    if (!projectId || composingSceneId) return;
    setComposingSceneId(sceneId);
    setError("");
    try {
      const job = await composeVideos(projectId, { scene_id: sceneId });
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const updated = await getComposeJob(projectId, job.job_id);
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          if (updated.status === "completed") {
            const version = await getComposedVideoVersion(
              projectId,
              "scene_video",
              sceneId,
            );
            if (version) {
              setComposedVersions((prev) => ({
                ...prev,
                [sceneId]: version,
              }));
            }
          } else if (updated.error) {
            setError(updated.error);
          }
          break;
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setComposingSceneId("");
    }
  }

  const asrModels = audioModels.filter((m) =>
    m.capabilities.includes("speech_to_text"),
  );

  async function handleRunModelReview() {
    if (!projectId || !selectedShotId || !asrModelId || !reviewScriptModelId) {
      setError("请选择语音转写模型和文本比对模型");
      return;
    }
    setReviewingJob(null);
    setError("");
    try {
      const job = await runDialogueReview(projectId, {
        shot_id: selectedShotId,
        model_id: asrModelId,
        script_model_id: reviewScriptModelId,
      });
      setReviewingJob(job);
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const updated = await getJob(job.job_id);
        setReviewingJob(updated);
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          if (updated.status === "completed") {
            const reviews = await listDialogueReviews(
              projectId,
              selectedShotId,
            );
            setLatestReview(reviews[0] ?? null);
          } else if (updated.error) {
            setError(updated.error);
          }
          break;
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setReviewingJob(null);
    }
  }

  async function handleSubmitManualReview(consistent: boolean) {
    if (!projectId || !selectedShotId) return;
    setError("");
    try {
      const review = await submitManualReview(projectId, {
        shot_id: selectedShotId,
        consistent,
        detected_speech: manualDetected,
      });
      setLatestReview(review);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleReviewDecision(
    decision: "regenerate" | "delete_shot" | "keep",
  ) {
    if (!projectId || !latestReview) return;
    setReviewDeciding(true);
    setError("");
    try {
      const updated = await decideDialogueReview(
        projectId,
        latestReview.id,
        decision,
      );
      setLatestReview(updated);
      if (decision === "delete_shot") {
        handleDeleteSelectedShot();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setReviewDeciding(false);
    }
  }

  async function handleRunVisualReview() {
    if (!projectId || !selectedShotId || !visualModelId) {
      setError("请选择视觉审核模型");
      return;
    }
    setVisualReviewingJob(null);
    setError("");
    try {
      const job = await runVisualReview(projectId, {
        shot_id: selectedShotId,
        model_id: visualModelId,
        review_type: visualReviewType,
      });
      setVisualReviewingJob(job);
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const updated = await getJob(job.job_id);
        setVisualReviewingJob(updated);
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          if (updated.status === "completed") {
            const reviews = await listVisualReviews(
              projectId,
              selectedShotId,
            );
            setLatestVisualReview(reviews[0] ?? null);
          } else if (updated.error) {
            setError(updated.error);
          }
          break;
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setVisualReviewingJob(null);
    }
  }

  async function handleSubmitManualVisualReview(consistent: boolean) {
    if (!projectId || !selectedShotId) return;
    setError("");
    try {
      const review = await submitManualVisualReview(projectId, {
        shot_id: selectedShotId,
        review_type: visualReviewType,
        consistent,
        issue: visualManualIssue,
      });
      setLatestVisualReview(review);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleVisualDecision(
    decision: "regenerate" | "delete_shot" | "keep",
  ) {
    if (!projectId || !latestVisualReview) return;
    setVisualDeciding(true);
    setError("");
    try {
      const updated = await decideVisualReview(
        projectId,
        latestVisualReview.id,
        decision,
      );
      setLatestVisualReview(updated);
      if (decision === "delete_shot") {
        handleDeleteSelectedShot();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setVisualDeciding(false);
    }
  }

  async function handleRunStoryReview() {
    if (!projectId || !selectedShotId || !storyModelId) {
      setError("请选择文本模型");
      return;
    }
    setStoryReviewingJob(null);
    setError("");
    try {
      const job = await runStoryReview(projectId, {
        shot_id: selectedShotId,
        model_id: storyModelId,
      });
      setStoryReviewingJob(job);
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const updated = await getJob(job.job_id);
        setStoryReviewingJob(updated);
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          if (updated.status === "completed") {
            const reviews = await listStoryReviews(
              projectId,
              selectedShotId,
            );
            setLatestStoryReview(reviews[0] ?? null);
          } else if (updated.error) {
            setError(updated.error);
          }
          break;
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStoryReviewingJob(null);
    }
  }

  async function handleSubmitManualStoryReview(consistent: boolean) {
    if (!projectId || !selectedShotId) return;
    setError("");
    try {
      const review = await submitManualStoryReview(projectId, {
        shot_id: selectedShotId,
        consistent,
        issue: storyManualIssue,
      });
      setLatestStoryReview(review);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleStoryDecision(
    decision: "regenerate" | "delete_shot" | "keep",
  ) {
    if (!projectId || !latestStoryReview) return;
    setStoryDeciding(true);
    setError("");
    try {
      const updated = await decideStoryReview(
        projectId,
        latestStoryReview.id,
        decision,
      );
      setLatestStoryReview(updated);
      if (decision === "delete_shot") {
        handleDeleteSelectedShot();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStoryDeciding(false);
    }
  }

  async function runDub() {
    if (!projectId || !selectedShotId) return;
    const hasDialogue = Boolean(shotDetailDraft?.dialogue?.trim());
    if (hasDialogue && !voiceModelId) {
      setError("请先选择语音模型");
      return;
    }
    setGeneratingDubShotId(selectedShotId);
    setDubJob(null);
    setError("");
    try {
      const job = await dubShot(projectId, selectedShotId, {
        voice_model_id: hasDialogue ? voiceModelId : "",
        bgm_path: audioFilePath || undefined,
      });
      setDubJob(job);
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        const updated = await getJob(job.job_id);
        setDubJob(updated);
        if (["completed", "failed", "cancelled"].includes(updated.status)) {
          if (updated.status === "completed") {
            const version = await getCurrentVoicedVersion(
              projectId,
              selectedShotId,
            );
            setShotVoicedVersion(version);
            setShotVoicedVersions((prev) => {
              const next = { ...prev };
              if (version) next[selectedShotId] = version;
              else delete next[selectedShotId];
              return next;
            });
          }
          break;
        }
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGeneratingDubShotId((prev) =>
        prev === selectedShotId ? null : prev,
      );
    }
  }

  async function handleAudioFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;
    setError("");
    try {
      const uploaded = await uploadAudioFile(projectId, file);
      setAudioFilePath(uploaded.file_path);
      setAudioFileName(uploaded.file_name);
    } catch (err) {
      setError((err as Error).message);
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

  const hasDialogue = Boolean(shotDetailDraft?.dialogue?.trim());

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
                        <button
                          type="button"
                          className="scene-compose-btn"
                          disabled={composingSceneId !== ""}
                          onClick={() => void handleComposeScene(scene.id)}
                        >
                          {composingSceneId === scene.id
                            ? "合成中…"
                            : composedVersions[scene.id]
                              ? "重新合成"
                              : "合成场景视频"}
                        </button>
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
                                const voiced = shotVoicedVersions[shot.id];
                                const silent = shotVideoVersions[shot.id];
                                const playVersion = voiced ?? silent;
                                const videoUrl = playVersion
                                  ? `${apiBase}${playVersion.file_url}`
                                  : null;
                                return (
                                  <SortableShotCard
                                    key={shot.id}
                                    shot={shot}
                                    sceneId={scene.id}
                                    isSelected={selectedShotId === shot.id}
                                    imageUrl={imageUrl}
                                    generating={generatingShotId === shot.id}
                                    videoUrl={videoUrl}
                                    onOpen={openShotDetail}
                                    onPlayVideo={() =>
                                      setZoomVideoUrl(videoUrl)
                                    }
                                  />
                                );
                              })}
                            </div>
                          </SortableContext>
                        </DndContext>
                      )}
                      {composedVersions[scene.id] && (
                        <div className="composed-preview">
                          <span className="muted">场景成片</span>
                          <video
                            controls
                            src={`${apiBase}${composedVersions[scene.id].file_url}`}
                          />
                        </div>
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
                    <h4>参考图</h4>
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
                          className="reference-thumb"
                          title="点击放大"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setZoomImageUrl(`${apiBase}${ref.version.file_url}`);
                          }}
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
              <div className="card image-generate-card">
                <div className="sidebar-head">
                  <h3>分镜视频</h3>
                </div>
                {videoModels.length > 0 ? (
                  <>
                    <label>
                      视频模型
                      <select
                        value={videoModelId}
                        onChange={(e) => setVideoModelId(e.target.value)}
                        disabled={generatingVideoShotId === selectedShotId}
                      >
                        {videoModels.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.model_id}
                          </option>
                        ))}
                      </select>
                    </label>
                    {videoModelId && (
                      <p className="muted">
                        {videoModels.find((m) => m.id === videoModelId)
                          ?.capabilities.includes("video_dialogue")
                          ? "该模型支持原生对白：开启后视频将直接带台词生成。"
                          : videoModels
                                .find((m) => m.id === videoModelId)
                                ?.capabilities.includes("video_audio")
                            ? "该模型仅支持原生音效（不含台词），默认无声生成。"
                            : "该模型生成无声视频。"}
                      </p>
                    )}
                    <label>
                      视频提示词
                      <textarea
                        value={videoPrompt}
                        onChange={(e) => setVideoPrompt(e.target.value)}
                        rows={3}
                        placeholder="描述这张图片应如何动起来，例如镜头推进、人物回头、风吹动衣角"
                        disabled={generatingVideoShotId === selectedShotId}
                      />
                    </label>
                    <label>
                      时长（秒）
                      <select
                        value={videoDuration}
                        onChange={(e) =>
                          setVideoDuration(Number(e.target.value))
                        }
                        disabled={generatingVideoShotId === selectedShotId}
                      >
                        {[5, 10, 15].map((value) => (
                          <option key={value} value={value}>
                            {value} 秒
                          </option>
                        ))}
                      </select>
                    </label>
                    {(() => {
                      const videoModel = videoModels.find(
                        (m) => m.id === videoModelId,
                      );
                      const supportsDialogue =
                        videoModel?.capabilities.includes("video_dialogue") ??
                        false;
                      const supportsAudio =
                        videoModel?.capabilities.includes("video_audio") ??
                        false;
                      if (!supportsDialogue && !supportsAudio) return null;
                      return (
                        <label>
                          <input
                            type="checkbox"
                            checked={withAudio}
                            onChange={(e) => setWithAudio(e.target.checked)}
                            disabled={generatingVideoShotId === selectedShotId}
                          />
                          {supportsDialogue
                            ? "带台词/对白生成"
                            : "带原生音效生成（仅音效，不含台词）"}
                        </label>
                      );
                    })()}
                    {shotVersions[selectedShotId] ? (
                      <button
                        type="button"
                        className="btn-primary"
                        disabled={
                          !videoModelId ||
                          generatingVideoShotId === selectedShotId
                        }
                        onClick={runShotVideoGeneration}
                      >
                        {generatingVideoShotId === selectedShotId
                          ? "生成中…"
                          : "生成视频"}
                      </button>
                    ) : (
                      <p className="muted">
                        请先生成该镜头的分镜图片，再进行图生视频。
                      </p>
                    )}
                    {videoJob && videoJob.status !== "completed" && (
                      <p className="muted">
                        {videoJob.status === "running"
                          ? "生成中……"
                          : videoJob.status === "failed"
                            ? "生成失败"
                            : videoJob.status === "cancelled"
                              ? "已取消"
                              : "排队中"}
                        {videoJob.error ? ` · ${videoJob.error}` : ""}
                      </p>
                    )}
                    {shotVideoVersion && (
                      <video
                        className="video-preview"
                        controls
                        src={`${apiBase}${shotVideoVersion.file_url}`}
                      />
                    )}
                  </>
                ) : (
                  <p className="muted">
                    还没有可用的视频模型，请先在「设置」启用一个支持图生视频的模型。
                  </p>
                )}
              </div>
              <div className="card image-generate-card">
                <div className="sidebar-head">
                  <h3>台词审核</h3>
                </div>
                {shotVideoVersion ? (
                  hasDialogue ? (
                    <>
                      <label>
                        审核方式
                        <select
                          value={reviewMode}
                          onChange={(e) =>
                            setReviewMode(e.target.value as "model" | "manual")
                          }
                          disabled={reviewingJob !== null}
                        >
                          <option value="model">多模态模型审核</option>
                          <option value="manual">人工审核</option>
                        </select>
                      </label>
                      {reviewMode === "model" ? (
                        <>
                          {asrModels.length > 0 ? (
                            <label>
                              语音转写模型
                              <select
                                value={asrModelId}
                                onChange={(e) => setAsrModelId(e.target.value)}
                                disabled={reviewingJob !== null}
                              >
                                <option value="">请选择</option>
                                {asrModels.map((m) => (
                                  <option key={m.id} value={m.id}>
                                    {m.model_id}
                                  </option>
                                ))}
                              </select>
                            </label>
                          ) : (
                            <p className="muted">
                              没有可用的语音转写模型，请先在「设置」启用（如
                              whisper / qwen3-asr / GLM-ASR）。
                            </p>
                          )}
                          {llmModels.length > 0 ? (
                            <label>
                              文本比对模型
                              <select
                                value={reviewScriptModelId}
                                onChange={(e) =>
                                  setReviewScriptModelId(e.target.value)
                                }
                                disabled={reviewingJob !== null}
                              >
                                {llmModels.map((m) => (
                                  <option key={m.id} value={m.id}>
                                    {m.model_id}
                                  </option>
                                ))}
                              </select>
                            </label>
                          ) : (
                            <p className="muted">
                              没有可用的文本模型，请先在「设置」启用。
                            </p>
                          )}
                          <button
                            type="button"
                            className="btn-primary"
                            disabled={
                              !asrModelId ||
                              !reviewScriptModelId ||
                              reviewingJob !== null
                            }
                            onClick={() => void handleRunModelReview()}
                          >
                            {reviewingJob ? "审核中…" : "开始审核"}
                          </button>
                          {reviewingJob && (
                            <p className="muted">正在语音转写并比对台词…</p>
                          )}
                          <p className="muted">
                            审核会调用语音转写与文本模型 API，可能产生费用。
                          </p>
                        </>
                      ) : (
                        <>
                          <p className="muted">
                            播放上方视频，对照剧本台词判断是否一致。
                          </p>
                          <p className="muted">
                            <strong>剧本台词：</strong>
                            {shotDetailDraft?.dialogue || "（无）"}
                          </p>
                          <label>
                            实际听到的台词（不一致时填写）
                            <textarea
                              value={manualDetected}
                              onChange={(e) => setManualDetected(e.target.value)}
                              rows={3}
                              placeholder="听到但与剧本不符的台词"
                            />
                          </label>
                          <div className="review-actions">
                            <button
                              type="button"
                              className="btn-primary"
                              onClick={() => void handleSubmitManualReview(true)}
                            >
                              台词一致
                            </button>
                            <button
                              type="button"
                              className="button-ghost"
                              onClick={() => void handleSubmitManualReview(false)}
                            >
                              台词不一致
                            </button>
                          </div>
                        </>
                      )}
                      {latestReview && (
                        <div
                          className={`review-result review-${latestReview.status}`}
                        >
                          {latestReview.status === "flagged" ? (
                            <>
                              <p className="review-issue">
                                检测到异常：
                                {latestReview.issue || "实际台词与剧本不一致"}
                              </p>
                              <p className="muted">
                                剧本：{latestReview.expected_dialogue}
                              </p>
                              <p className="muted">
                                实际：
                                {latestReview.detected_speech || "（未记录）"}
                              </p>
                              <div className="review-actions">
                                <button
                                  type="button"
                                  disabled={reviewDeciding}
                                  onClick={() =>
                                    void handleReviewDecision("regenerate")
                                  }
                                >
                                  重新生成
                                </button>
                                <button
                                  type="button"
                                  disabled={reviewDeciding}
                                  onClick={() =>
                                    void handleReviewDecision("delete_shot")
                                  }
                                >
                                  删除分镜
                                </button>
                                <button
                                  type="button"
                                  disabled={reviewDeciding}
                                  onClick={() =>
                                    void handleReviewDecision("keep")
                                  }
                                >
                                  继续沿用
                                </button>
                              </div>
                              {latestReview.decision && (
                                <p className="muted">
                                  已选择：
                                  {latestReview.decision === "regenerate"
                                    ? "重新生成（请在上方视频区域重新生成）"
                                    : latestReview.decision === "delete_shot"
                                      ? "删除分镜"
                                      : "继续沿用"}
                                </p>
                              )}
                            </>
                          ) : (
                            <p className="review-passed">
                              台词一致 ✓（
                              {latestReview.mode === "model"
                                ? "模型审核"
                                : "人工审核"}
                              ）
                            </p>
                          )}
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="muted">该镜头没有剧本台词，无需审核。</p>
                  )
                ) : (
                  <p className="muted">
                    请先生成该镜头的视频，再进行台词审核。
                  </p>
                )}
              </div>
              <div className="card image-generate-card">
                <div className="sidebar-head">
                  <h3>视觉一致性检查</h3>
                </div>
                {shotVersions[selectedShotId] ? (
                  <>
                    <label>
                      检查类型
                      <select
                        value={visualReviewType}
                        onChange={(e) =>
                          setVisualReviewType(
                            e.target.value as VisualReviewType,
                          )
                        }
                        disabled={visualReviewingJob !== null}
                      >
                        <option value="character">角色与角色卡</option>
                        <option value="scene">场景与设定</option>
                        <option value="continuity">与前一镜头连续性</option>
                        <option value="costume">服装一致性</option>
                      </select>
                    </label>
                    <label>
                      审核方式
                      <select
                        value={visualMode}
                        onChange={(e) =>
                          setVisualMode(e.target.value as "model" | "manual")
                        }
                        disabled={visualReviewingJob !== null}
                      >
                        <option value="model">多模态模型审核</option>
                        <option value="manual">人工审核</option>
                      </select>
                    </label>
                    {visualMode === "model" ? (
                      <>
                        {visionModels.length > 0 ? (
                          <label>
                            视觉模型
                            <select
                              value={visualModelId}
                              onChange={(e) =>
                                setVisualModelId(e.target.value)
                              }
                              disabled={visualReviewingJob !== null}
                            >
                              {visionModels.map((m) => (
                                <option key={m.id} value={m.id}>
                                  {m.model_id}
                                </option>
                              ))}
                            </select>
                          </label>
                        ) : (
                          <p className="muted">
                            没有可用的视觉模型，请先在「设置」启用（如
                            qwen-vl-plus / glm-4v-plus / gpt-4o）。
                          </p>
                        )}
                        <button
                          type="button"
                          className="btn-primary"
                          disabled={
                            !visualModelId || visualReviewingJob !== null
                          }
                          onClick={() => void handleRunVisualReview()}
                        >
                          {visualReviewingJob ? "审核中…" : "开始审核"}
                        </button>
                        {visualReviewingJob && (
                          <p className="muted">正在比对分镜图与参考图…</p>
                        )}
                        <p className="muted">
                          审核会调用视觉模型 API，可能产生费用。
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="muted">
                          对照上方分镜图与角色卡 / 场景设定 / 前一镜头判断是否一致。
                        </p>
                        <label>
                          问题说明（不一致时填写）
                          <textarea
                            value={visualManualIssue}
                            onChange={(e) => setVisualManualIssue(e.target.value)}
                            rows={3}
                            placeholder="例如：角色服装与角色卡不一致"
                          />
                        </label>
                        <div className="review-actions">
                          <button
                            type="button"
                            className="btn-primary"
                            onClick={() =>
                              void handleSubmitManualVisualReview(true)
                            }
                          >
                            视觉一致
                          </button>
                          <button
                            type="button"
                            className="button-ghost"
                            onClick={() =>
                              void handleSubmitManualVisualReview(false)
                            }
                          >
                            视觉不一致
                          </button>
                        </div>
                      </>
                    )}
                    {latestVisualReview && (
                      <div
                        className={`review-result review-${latestVisualReview.status}`}
                      >
                        {latestVisualReview.status === "flagged" ? (
                          <>
                            <p className="review-issue">
                              检测到异常：
                              {latestVisualReview.issue || "视觉要素不一致"}
                            </p>
                            <div className="review-actions">
                              <button
                                type="button"
                                disabled={visualDeciding}
                                onClick={() =>
                                  void handleVisualDecision("regenerate")
                                }
                              >
                                重新生成
                              </button>
                              <button
                                type="button"
                                disabled={visualDeciding}
                                onClick={() =>
                                  void handleVisualDecision("delete_shot")
                                }
                              >
                                删除分镜
                              </button>
                              <button
                                type="button"
                                disabled={visualDeciding}
                                onClick={() =>
                                  void handleVisualDecision("keep")
                                }
                              >
                                继续沿用
                              </button>
                            </div>
                            {latestVisualReview.decision && (
                              <p className="muted">
                                已选择：
                                {latestVisualReview.decision === "regenerate"
                                  ? "重新生成（请在上方图片区域重新生成）"
                                  : latestVisualReview.decision === "delete_shot"
                                    ? "删除分镜"
                                    : "继续沿用"}
                              </p>
                            )}
                          </>
                        ) : (
                          <p className="review-passed">
                            视觉一致 ✓（
                            {latestVisualReview.mode === "model"
                              ? "模型审核"
                              : "人工审核"}
                            ）
                          </p>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <p className="muted">
                    请先生成该镜头的分镜图，再进行视觉一致性检查。
                  </p>
                )}
              </div>
              <div className="card image-generate-card">
                <div className="sidebar-head">
                  <h3>剧情一致性检查</h3>
                </div>
                {llmModels.length > 0 ? (
                  <>
                    <label>
                      文本模型
                      <select
                        value={storyModelId}
                        onChange={(e) => setStoryModelId(e.target.value)}
                        disabled={storyReviewingJob !== null}
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
                      disabled={storyReviewingJob !== null}
                      onClick={() => void handleRunStoryReview()}
                    >
                      {storyReviewingJob ? "审核中…" : "检查剧情衔接"}
                    </button>
                    {storyReviewingJob && (
                      <p className="muted">正在对比前后镜头剧情…</p>
                    )}
                    <p className="muted">
                      检查该镜头与前后镜头的动作 / 台词衔接是否合理（会调用文本模型
                      API）。
                    </p>
                    <p className="muted">
                      <strong>人工审核：</strong>播放视频或查看上下镜头，判断剧情是否连贯。
                    </p>
                    <label>
                      问题说明（人工审核不一致时填写）
                      <textarea
                        value={storyManualIssue}
                        onChange={(e) => setStoryManualIssue(e.target.value)}
                        rows={2}
                        placeholder="例如：台词与动作矛盾"
                      />
                    </label>
                    <div className="review-actions">
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() =>
                          void handleSubmitManualStoryReview(true)
                        }
                      >
                        剧情一致
                      </button>
                      <button
                        type="button"
                        className="button-ghost"
                        onClick={() =>
                          void handleSubmitManualStoryReview(false)
                        }
                      >
                        剧情不一致
                      </button>
                    </div>
                    {latestStoryReview && (
                      <div
                        className={`review-result review-${latestStoryReview.status}`}
                      >
                        {latestStoryReview.status === "flagged" ? (
                          <>
                            <p className="review-issue">
                              检测到异常：
                              {latestStoryReview.issue || "剧情衔接不一致"}
                            </p>
                            <div className="review-actions">
                              <button
                                type="button"
                                disabled={storyDeciding}
                                onClick={() =>
                                  void handleStoryDecision("regenerate")
                                }
                              >
                                重新生成
                              </button>
                              <button
                                type="button"
                                disabled={storyDeciding}
                                onClick={() =>
                                  void handleStoryDecision("delete_shot")
                                }
                              >
                                删除分镜
                              </button>
                              <button
                                type="button"
                                disabled={storyDeciding}
                                onClick={() =>
                                  void handleStoryDecision("keep")
                                }
                              >
                                继续沿用
                              </button>
                            </div>
                            {latestStoryReview.decision && (
                              <p className="muted">
                                已选择：
                                {latestStoryReview.decision === "regenerate"
                                  ? "重新生成"
                                  : latestStoryReview.decision === "delete_shot"
                                    ? "删除分镜"
                                    : "继续沿用"}
                              </p>
                            )}
                          </>
                        ) : (
                          <p className="review-passed">
                            剧情一致 ✓（
                            {latestStoryReview.mode === "model"
                              ? "模型审核"
                              : "人工审核"}
                            ）
                          </p>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <p className="muted">
                    没有可用的文本模型，请先在「设置」启用。
                  </p>
                )}
              </div>
              <div className="card image-generate-card">
                <div className="sidebar-head">
                  <h3>声音</h3>
                  <p className="muted">对白自动配音；音效 / BGM 可导入本地音频统一混音。</p>
                </div>
                {shotVideoVersion ? (
                  <>
                    {hasDialogue ? (
                      audioModels.length > 0 ? (
                        <label>
                          语音模型
                          <select
                            value={voiceModelId}
                            onChange={(e) => setVoiceModelId(e.target.value)}
                            disabled={generatingDubShotId === selectedShotId}
                          >
                            {audioModels.map((m) => (
                              <option key={m.id} value={m.id}>
                                {m.model_id}
                              </option>
                            ))}
                          </select>
                        </label>
                      ) : (
                        <p className="muted">
                          该镜头有台词，但还没有可用语音模型，请先在「设置」启用。
                        </p>
                      )
                    ) : (
                      <p className="muted">该镜头没有台词，可只导入音效或背景音乐。</p>
                    )}
                    <label>
                      音效 / BGM（可选）
                      <input
                        type="file"
                        accept="audio/*"
                        onChange={handleAudioFileChange}
                        disabled={generatingDubShotId === selectedShotId}
                      />
                      {audioFileName && (
                        <span className="muted">已选：{audioFileName}</span>
                      )}
                    </label>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={
                        (hasDialogue && !voiceModelId) ||
                        generatingDubShotId === selectedShotId
                      }
                      onClick={runDub}
                    >
                      {generatingDubShotId === selectedShotId
                        ? "合成中…"
                        : "生成声音"}
                    </button>
                    {dubJob && dubJob.status !== "completed" && (
                      <p className="muted">
                        {dubJob.status === "running"
                          ? "配音中……"
                          : dubJob.status === "failed"
                            ? "配音失败"
                            : dubJob.status === "cancelled"
                              ? "已取消"
                              : "排队中"}
                        {dubJob.error ? ` · ${dubJob.error}` : ""}
                      </p>
                    )}
                    {shotVoicedVersion && (
                      <video
                        className="video-preview"
                        controls
                        src={`${apiBase}${shotVoicedVersion.file_url}`}
                      />
                    )}
                    <p className="muted">
                      有台词时合成会调用语音合成 API，可能产生费用。
                    </p>
                  </>
                ) : (
                  <p className="muted">
                    请先生成该镜头的分镜视频，再进行声音合成。
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
      {zoomImageUrl && (
        <div
          className="image-lightbox"
          onClick={() => setZoomImageUrl(null)}
        >
          <div
            className="image-lightbox-inner"
            onClick={(e) => e.stopPropagation()}
          >
            <img src={zoomImageUrl} alt="参考图放大预览" />
            <button
              type="button"
              className="button-ghost"
              onClick={() => setZoomImageUrl(null)}
            >
              关闭
            </button>
          </div>
        </div>
      )}
      {zoomVideoUrl && (
        <div
          className="image-lightbox"
          onClick={() => setZoomVideoUrl(null)}
        >
          <div
            className="image-lightbox-inner"
            onClick={(e) => e.stopPropagation()}
          >
            <video
              className="video-lightbox-player"
              controls
              autoPlay
              src={zoomVideoUrl}
            />
            <button
              type="button"
              className="button-ghost"
              onClick={() => setZoomVideoUrl(null)}
            >
              关闭
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

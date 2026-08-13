import type {
  AiEpisodeScriptResult,
  AiShotsResult,
  Episode,
  EpisodeDetail,
  Scene,
  SceneDetail,
  Shot,
} from "../types/script";
import { request } from "./client";

export function listEpisodes(
  projectId: string,
  novelId?: string,
): Promise<Episode[]> {
  const suffix = novelId ? `?novel_id=${encodeURIComponent(novelId)}` : "";
  return request<Episode[]>(`/projects/${projectId}/script/episodes${suffix}`);
}

export function getEpisodeDetail(
  projectId: string,
  episodeId: string,
): Promise<EpisodeDetail> {
  return request<EpisodeDetail>(
    `/projects/${projectId}/script/episodes/${episodeId}`,
  );
}

export function getSceneDetail(
  projectId: string,
  sceneId: string,
): Promise<SceneDetail> {
  return request<SceneDetail>(
    `/projects/${projectId}/script/scenes/${sceneId}`,
  );
}

export function generateEpisodeScript(
  projectId: string,
  input: {
    novel_id: string;
    model_id: string;
    chapter_index?: number;
    user_instruction?: string;
  },
): Promise<AiEpisodeScriptResult> {
  return request<AiEpisodeScriptResult>(
    `/projects/${projectId}/script/generate-episode`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function saveEpisodeScript(
  projectId: string,
  payload: {
    novel_id: string;
    chapter_index?: number | null;
    episode: { title: string; summary: string };
    scenes: {
      title: string;
      slugline: string;
      action: string;
      dialogue: string;
    }[];
  },
): Promise<EpisodeDetail> {
  return request<EpisodeDetail>(
    `/projects/${projectId}/script/save-episode-script`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function generateShots(
  projectId: string,
  sceneId: string,
  input: { model_id: string; scene_id: string; user_instruction?: string },
): Promise<AiShotsResult> {
  return request<AiShotsResult>(
    `/projects/${projectId}/script/scenes/${sceneId}/generate-shots`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function saveSceneShots(
  projectId: string,
  sceneId: string,
  payload: { shots: unknown[] },
): Promise<SceneDetail> {
  return request<SceneDetail>(
    `/projects/${projectId}/script/scenes/${sceneId}/save-shots`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function updateScene(
  projectId: string,
  sceneId: string,
  input: {
    title?: string;
    slugline?: string;
    action?: string;
    dialogue?: string;
  },
): Promise<Scene> {
  return request<Scene>(
    `/projects/${projectId}/script/scenes/${sceneId}`,
    {
      method: "PUT",
      body: JSON.stringify(input),
    },
  );
}

export function updateShot(
  projectId: string,
  sceneId: string,
  shotId: string,
  input: {
    shot_type?: string;
    camera?: string;
    characters?: string;
    action?: string;
    lighting?: string;
    dialogue?: string;
    duration?: number;
    prompt?: string;
  },
): Promise<Shot> {
  return request<Shot>(
    `/projects/${projectId}/script/scenes/${sceneId}/shots/${shotId}`,
    {
      method: "PUT",
      body: JSON.stringify(input),
    },
  );
}

export function deleteShot(
  projectId: string,
  sceneId: string,
  shotId: string,
): Promise<void> {
  return request<void>(
    `/projects/${projectId}/script/scenes/${sceneId}/shots/${shotId}`,
    { method: "DELETE" },
  );
}

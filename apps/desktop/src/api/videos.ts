import type { AssetVersion } from "../types/asset_version";
import type { GenerationJob } from "../types/generation";
import type { JobOut } from "../types/job";
import { request } from "./client";

export interface VideoGenerateInput {
  target_id: string;
  model_id: string;
  prompt: string;
  duration?: number;
  aspect_ratio?: string;
  with_audio?: boolean;
}

export function generateVideo(
  projectId: string,
  input: VideoGenerateInput,
): Promise<GenerationJob> {
  return request<GenerationJob>(
    `/projects/${projectId}/videos/generate`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function getVideoJob(
  projectId: string,
  jobId: string,
): Promise<GenerationJob> {
  return request<GenerationJob>(
    `/projects/${projectId}/videos/jobs/${jobId}`,
  );
}

export function getCurrentVideoVersion(
  projectId: string,
  shotId: string,
): Promise<AssetVersion | null> {
  return request<AssetVersion | null>(
    `/projects/${projectId}/videos/current?shot_id=${shotId}`,
  );
}

export interface AudioDubInput {
  voice_model_id?: string;
  script_model_id?: string;
  voice?: string;
  bgm_path?: string;
}

export function dubShot(
  projectId: string,
  shotId: string,
  input: AudioDubInput,
): Promise<JobOut> {
  return request<JobOut>(`/projects/${projectId}/videos/${shotId}/dub`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getCurrentVoicedVersion(
  projectId: string,
  shotId: string,
): Promise<AssetVersion | null> {
  return request<AssetVersion | null>(
    `/projects/${projectId}/videos/voiced/current?shot_id=${shotId}`,
  );
}

export function uploadAudioFile(
  projectId: string,
  file: File,
): Promise<{ file_path: string; file_name: string }> {
  const form = new FormData();
  form.append("file", file);
  return request<{ file_path: string; file_name: string }>(
    `/projects/${projectId}/videos/audio-files`,
    {
      method: "POST",
      headers: {},
      body: form,
    },
  );
}

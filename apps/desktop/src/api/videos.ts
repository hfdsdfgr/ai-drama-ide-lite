import type { AssetVersion } from "../types/asset_version";
import type { GenerationJob } from "../types/generation";
import { request } from "./client";

export interface VideoGenerateInput {
  target_id: string;
  model_id: string;
  prompt: string;
  duration?: number;
  aspect_ratio?: string;
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

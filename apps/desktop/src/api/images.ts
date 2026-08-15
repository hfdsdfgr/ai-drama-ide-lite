import type { AssetVersion } from "../types/asset_version";
import type { GenerationJob } from "../types/generation";
import { request } from "./client";

export interface ImageGenerateInput {
  target_type: "asset" | "shot";
  target_id: string;
  model_id: string;
  capability?: string;
  aspect_ratio?: string;
  art_style?: string;
  negative_prompt?: string;
  reference_asset_ids?: string[];
}

export function generateImage(
  projectId: string,
  input: ImageGenerateInput,
): Promise<GenerationJob> {
  return request<GenerationJob>(
    `/projects/${projectId}/images/generate`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function getImageJob(
  projectId: string,
  jobId: string,
): Promise<GenerationJob> {
  return request<GenerationJob>(
    `/projects/${projectId}/images/jobs/${jobId}`,
  );
}

export function listImageVersions(
  projectId: string,
  targetType: "asset" | "shot",
  targetId: string,
): Promise<AssetVersion[]> {
  return request<AssetVersion[]>(
    `/projects/${projectId}/images/versions?target_type=${targetType}&target_id=${targetId}`,
  );
}

export function getCurrentImageVersion(
  projectId: string,
  targetType: "asset" | "shot",
  targetId: string,
): Promise<AssetVersion | null> {
  return request<AssetVersion | null>(
    `/projects/${projectId}/images/current?target_type=${targetType}&target_id=${targetId}`,
  );
}

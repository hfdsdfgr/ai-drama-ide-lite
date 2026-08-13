import type {
  AssetCard,
  AssetGenerateJob,
  AssetImageSpec,
  AssetType,
} from "../types/story";
import { request } from "./client";

export function listAssets(projectId: string): Promise<AssetCard[]> {
  return request<AssetCard[]>(`/projects/${projectId}/assets`);
}

export function getAssetSpecs(
  projectId: string,
): Promise<{ specs: Record<AssetType, AssetImageSpec> }> {
  return request<{ specs: Record<AssetType, AssetImageSpec> }>(
    `/projects/${projectId}/assets/specs`,
  );
}

export function updateAsset(
  projectId: string,
  input: { asset_type: AssetType; name: string; patch: Record<string, string> },
): Promise<AssetCard> {
  return request<AssetCard>(`/projects/${projectId}/assets`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function deleteAsset(
  projectId: string,
  input: { asset_type: AssetType; name: string },
): Promise<void> {
  return request<void>(`/projects/${projectId}/assets`, {
    method: "DELETE",
    body: JSON.stringify(input),
  });
}

export function startAssetGeneration(
  projectId: string,
  modelId: string,
): Promise<AssetGenerateJob> {
  return request<AssetGenerateJob>(
    `/projects/${projectId}/assets/generate`,
    {
      method: "POST",
      body: JSON.stringify({ model_id: modelId }),
    },
  );
}

export function getAssetGeneration(
  projectId: string,
  jobId: string,
): Promise<AssetGenerateJob> {
  return request<AssetGenerateJob>(
    `/projects/${projectId}/assets/generate/${jobId}`,
  );
}

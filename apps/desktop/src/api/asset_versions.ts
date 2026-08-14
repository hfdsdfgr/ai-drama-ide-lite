import type { AssetVersion } from "../types/asset_version";
import { request } from "./client";

export function listAssetVersions(
  projectId: string,
  assetId: string,
): Promise<AssetVersion[]> {
  return request<AssetVersion[]>(
    `/projects/${projectId}/assets/${assetId}/versions`,
  );
}

export function getCurrentAssetVersion(
  projectId: string,
  assetId: string,
): Promise<AssetVersion | null> {
  return request<AssetVersion | null>(
    `/projects/${projectId}/assets/${assetId}/versions/current`,
  );
}

export function promoteAssetVersion(
  projectId: string,
  assetId: string,
  versionId: string,
): Promise<AssetVersion> {
  return request<AssetVersion>(
    `/projects/${projectId}/assets/${assetId}/versions/${versionId}/promote`,
    { method: "POST" },
  );
}

export function deleteAssetVersion(
  projectId: string,
  assetId: string,
  versionId: string,
): Promise<void> {
  return request<void>(
    `/projects/${projectId}/assets/${assetId}/versions/${versionId}`,
    { method: "DELETE" },
  );
}

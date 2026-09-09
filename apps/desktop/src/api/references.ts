import type { AssetVersion } from "../types/asset_version";
import { request } from "./client";

export interface ReferenceMedia {
  id: string;
  name: string;
  created_at: string;
  version: AssetVersion;
}

export function listReferences(projectId: string): Promise<ReferenceMedia[]> {
  return request<ReferenceMedia[]>(`/projects/${projectId}/references`);
}

export function importReference(projectId: string, file: File): Promise<ReferenceMedia> {
  const form = new FormData();
  form.append("file", file);
  return request<ReferenceMedia>(`/projects/${projectId}/references/import`, {
    method: "POST",
    headers: {},
    body: form,
  });
}

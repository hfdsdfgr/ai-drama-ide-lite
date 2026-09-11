import { request } from "./client";

export interface AffectedNode {
  type: string;
  id: string;
  relation: string;
}

export interface AffectedNodesResponse {
  changed_node: { type: string; id: string };
  affected: AffectedNode[];
}

export interface RegenerationPlanItem {
  shot_id: string;
  label: string;
  reason: string;
  dependency_state?: string;
}

export interface RegenerationPlanResponse {
  changed_node: { type: string; id: string };
  image_shots: RegenerationPlanItem[];
  video_shots: RegenerationPlanItem[];
}

export interface DependencyViewNode {
  id: string;
  entity_type: string;
  entity_id: string;
  label: string;
  version: number | null;
  current_version: number | null;
  state: "none" | "current" | "stale" | "pinned" | "unknown" | "broken";
  target: { type?: "asset" | "shot"; id?: string; media?: "image" | "video" };
}

export interface DependencyViewShot {
  shot_id: string;
  label: string;
  nodes: DependencyViewNode[];
  edges: { source: string; target: string; relation: string }[];
  issues: { state: string; label: string; media: "image" | "video" }[];
}

export interface DependencyViewResponse {
  project_id: string;
  scope: { type: "shot" | "scene"; id: string };
  shots: DependencyViewShot[];
  total: number;
}

export function getAffectedNodes(
  projectId: string,
  nodeType: string,
  nodeId: string,
): Promise<AffectedNodesResponse> {
  const query = new URLSearchParams({ node_type: nodeType, node_id: nodeId });
  return request<AffectedNodesResponse>(
    `/projects/${projectId}/graph/affected?${query.toString()}`,
  );
}

export function getRegenerationPlan(
  projectId: string,
  nodeType: string,
  nodeId: string,
): Promise<RegenerationPlanResponse> {
  const query = new URLSearchParams({ node_type: nodeType, node_id: nodeId });
  return request<RegenerationPlanResponse>(
    `/projects/${projectId}/graph/regeneration-plan?${query.toString()}`,
  );
}

export function getDependencyView(
  projectId: string,
  scope: { shotId: string } | { sceneId: string },
  page: { limit?: number; offset?: number } = {},
): Promise<DependencyViewResponse> {
  const query = new URLSearchParams(
    "shotId" in scope ? { shot_id: scope.shotId } : { scene_id: scope.sceneId },
  );
  if (page.limit !== undefined) query.set("limit", String(page.limit));
  if (page.offset !== undefined) query.set("offset", String(page.offset));
  return request<DependencyViewResponse>(
    `/projects/${projectId}/graph/view?${query.toString()}`,
  );
}

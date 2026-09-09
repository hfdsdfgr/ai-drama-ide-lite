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
}

export interface RegenerationPlanResponse {
  changed_node: { type: string; id: string };
  image_shots: RegenerationPlanItem[];
  video_shots: RegenerationPlanItem[];
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

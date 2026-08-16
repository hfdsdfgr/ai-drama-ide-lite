import type { ProjectOverview } from "../types/overview";
import { request } from "./client";

export function getProjectOverview(projectId: string): Promise<ProjectOverview> {
  return request<ProjectOverview>(`/projects/${projectId}/overview`);
}

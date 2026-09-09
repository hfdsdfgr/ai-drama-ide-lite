import type {
  EpisodePrepareResult,
  EpisodeWorkspace,
  ProjectOverview,
} from "../types/overview";
import { request } from "./client";

export function getProjectOverview(projectId: string): Promise<ProjectOverview> {
  return request<ProjectOverview>(`/projects/${projectId}/overview`);
}

export function getEpisodeWorkspace(projectId: string): Promise<EpisodeWorkspace> {
  return request<EpisodeWorkspace>(`/projects/${projectId}/overview/episodes`);
}

export function prepareEpisode(
  projectId: string,
  episodeId: string,
): Promise<EpisodePrepareResult> {
  return request<EpisodePrepareResult>(
    `/projects/${projectId}/overview/episodes/${episodeId}/prepare`,
    { method: "POST" },
  );
}

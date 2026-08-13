import type {
  CreateProjectInput,
  Project,
  UpdateProjectInput,
} from "../types/project";
import { request } from "./client";

export function listProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export function createProject(input: CreateProjectInput): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getProject(id: string): Promise<Project> {
  return request<Project>(`/projects/${id}`);
}

export function updateProject(
  id: string,
  input: UpdateProjectInput,
): Promise<Project> {
  return request<Project>(`/projects/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

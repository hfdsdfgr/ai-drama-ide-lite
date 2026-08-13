import type {
  CreateProjectInput,
  Project,
  UpdateProjectInput,
} from "../types/project";
import { request, requestBlob } from "./client";

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

export function deleteProject(id: string): Promise<void> {
  return request<void>(`/projects/${id}`, { method: "DELETE" });
}

export async function exportProject(id: string): Promise<void> {
  const blob = await requestBlob(`/projects/${id}/export`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `project-${id}.zip`;
  link.click();
  URL.revokeObjectURL(url);
}

export function importProject(file: File): Promise<Project> {
  return request<Project>("/projects/import", {
    method: "POST",
    headers: { "Content-Type": "application/zip" },
    body: file,
  });
}

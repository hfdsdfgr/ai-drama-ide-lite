import type {
  Chapter,
  Novel,
  NovelDetail,
} from "../types/novel";
import { request } from "./client";

export type NovelAiAction = "continue" | "expand" | "rewrite";

export function listNovels(projectId: string, q = ""): Promise<Novel[]> {
  const query = q ? `?q=${encodeURIComponent(q)}` : "";
  return request<Novel[]>(`/projects/${projectId}/novels${query}`);
}

export function createNovel(projectId: string, title: string): Promise<Novel> {
  return request<Novel>(`/projects/${projectId}/novels`, {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export function getNovel(projectId: string, novelId: string): Promise<NovelDetail> {
  return request<NovelDetail>(`/projects/${projectId}/novels/${novelId}`);
}

export function updateNovel(
  projectId: string,
  novelId: string,
  input: { title?: string },
): Promise<Novel> {
  return request<Novel>(`/projects/${projectId}/novels/${novelId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function deleteNovel(projectId: string, novelId: string): Promise<void> {
  return request<void>(`/projects/${projectId}/novels/${novelId}`, {
    method: "DELETE",
  });
}

export function addChapter(
  projectId: string,
  novelId: string,
  input: { title?: string; content?: string },
): Promise<Chapter> {
  return request<Chapter>(`/projects/${projectId}/novels/${novelId}/chapters`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateChapter(
  projectId: string,
  novelId: string,
  chapterId: string,
  input: { title?: string; content?: string },
): Promise<Chapter> {
  return request<Chapter>(
    `/projects/${projectId}/novels/${novelId}/chapters/${chapterId}`,
    { method: "PUT", body: JSON.stringify(input) },
  );
}

export function deleteChapter(
  projectId: string,
  novelId: string,
  chapterId: string,
): Promise<void> {
  return request<void>(
    `/projects/${projectId}/novels/${novelId}/chapters/${chapterId}`,
    { method: "DELETE" },
  );
}

export function importNovel(projectId: string, file: File): Promise<Novel> {
  return request<Novel>(
    `/projects/${projectId}/novels/import?filename=${encodeURIComponent(file.name)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    },
  );
}

export function generateNovelText(
  projectId: string,
  novelId: string,
  chapterId: string,
  action: NovelAiAction,
  modelId: string,
): Promise<{ text: string }> {
  return request<{ text: string }>(
    `/projects/${projectId}/novels/${novelId}/ai/${action}`,
    {
      method: "POST",
      body: JSON.stringify({ chapter_id: chapterId, model_id: modelId }),
    },
  );
}

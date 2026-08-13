/**
 * 统一的 API 请求封装。
 * 后端错误响应格式：{ "error": { "code", "message", "details?" } }
 * 失败时抛出 ApiError，UI 直接展示可操作的 message。
 *
 * 地址策略：Tauri 生产环境直连 sidecar 后端（动态端口，经 get_backend_port）；
 * 浏览器 / Vite 开发环境走相对路径（由 Vite 代理转发到 8000）。
 */

import { invoke, isTauri } from "@tauri-apps/api/core";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function parseErrorResponse(response: Response): Promise<ApiError> {
  let payload: ApiErrorBody | undefined;
  try {
    payload = (await response.json()) as ApiErrorBody;
  } catch {
    // 响应体不是 JSON 时忽略，使用兜底信息
  }
  const message =
    payload?.error?.message ??
    `请求失败（HTTP ${response.status}），请稍后重试或检查服务是否已启动`;
  return new ApiError(
    response.status,
    payload?.error?.code ?? "unknown_error",
    message,
  );
}

let basePromise: Promise<string> | null = null;

export function getApiBase(): Promise<string> {
  if (!basePromise) {
    basePromise = (async () => {
      if (isTauri()) {
        try {
          const port = await invoke<number | null>("get_backend_port");
          if (port) {
            return `http://127.0.0.1:${port}`;
          }
        } catch {
          // 拿不到端口时回退到相对路径（开发模式）
        }
      }
      return "";
    })();
  }
  return basePromise;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = await getApiBase();
  const response = await fetch(`${base}/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    throw await parseErrorResponse(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function requestBlob(
  path: string,
  init?: RequestInit,
): Promise<Blob> {
  const base = await getApiBase();
  const response = await fetch(`${base}/api${path}`, { ...init });
  if (!response.ok) {
    throw await parseErrorResponse(response);
  }
  return response.blob();
}

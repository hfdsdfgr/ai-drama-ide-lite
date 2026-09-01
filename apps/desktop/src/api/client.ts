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
          // 拿不到端口时按环境处理（见下）
        }
        // 生产环境拿不到后端端口说明 sidecar 未启动，给出明确错误而非模糊的“请求失败”；
        // Tauri dev 模式由外部启动后端，回退相对路径走 Vite 代理。
        if (!import.meta.env.DEV) {
          throw new ApiError(
            503,
            "backend_not_started",
            "后端服务未启动，请重启应用后重试",
          );
        }
      }
      return "";
    })();
  }
  return basePromise;
}

/**
 * 安装版后端 sidecar 是 PyInstaller onefile，启动需要解压 + 起 uvicorn，
 * 通常要几秒才监听端口。首次请求前轮询 /api/health，避免「启动后立刻操作」
 * 打空端口导致 Failed to fetch。开发模式（base 为空）直接跳过。
 */
const BACKEND_READY_TIMEOUT_MS = 15000;
const BACKEND_READY_POLL_MS = 500;
const HEALTH_FETCH_TIMEOUT_MS = 2000;

let backendReady = false;
let readyPromise: Promise<void> | null = null;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForBackend(base: string): Promise<void> {
  const deadline = Date.now() + BACKEND_READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      // 端口已监听即视为就绪：uvicorn 监听前会先完成 DB 初始化，
      // 能建立 HTTP 连接说明后端进程已可用（任何状态码都算可达）。
      await fetch(`${base}/api/health`, {
        signal: AbortSignal.timeout(HEALTH_FETCH_TIMEOUT_MS),
      });
      return;
    } catch {
      // 端口未监听 / 仍在启动，继续轮询
    }
    await sleep(BACKEND_READY_POLL_MS);
  }
  throw new ApiError(
    503,
    "backend_not_ready",
    "后端服务启动超时，请重启应用后重试",
  );
}

function ensureBackendReady(): Promise<void> {
  if (backendReady) return Promise.resolve();
  if (!readyPromise) {
    readyPromise = (async () => {
      const base = await getApiBase();
      if (!base) {
        backendReady = true;
        return;
      }
      await waitForBackend(base);
      backendReady = true;
    })();
    readyPromise.catch(() => {
      // 等待失败后允许下一次请求重新尝试
      readyPromise = null;
    });
  }
  return readyPromise;
}

async function fetchWithReady(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  await ensureBackendReady();
  const base = await getApiBase();
  try {
    return await fetch(`${base}/api${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch (e) {
    if (e instanceof TypeError) {
      throw new ApiError(
        0,
        "network_error",
        "无法连接后端服务，可能仍在启动，请稍后重试",
      );
    }
    throw e;
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchWithReady(path, init);

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
  const response = await fetchWithReady(path, init);
  if (!response.ok) {
    throw await parseErrorResponse(response);
  }
  return response.blob();
}

/** 仅供测试：重置 base / 后端就绪缓存，避免用例间串状态。 */
export function __resetApiClientForTests(): void {
  basePromise = null;
  backendReady = false;
  readyPromise = null;
}

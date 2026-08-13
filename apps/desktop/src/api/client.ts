/**
 * 统一的 API 请求封装。
 * 后端错误响应格式：{ "error": { "code", "message", "details?" } }
 * 失败时抛出 ApiError，UI 直接展示可操作的 message。
 */

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

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    let payload: ApiErrorBody | undefined;
    try {
      payload = (await response.json()) as ApiErrorBody;
    } catch {
      // 响应体不是 JSON 时忽略，使用兜底信息
    }
    const message =
      payload?.error?.message ?? `请求失败（HTTP ${response.status}）`;
    throw new ApiError(
      response.status,
      payload?.error?.code ?? "unknown_error",
      message,
    );
  }

  return response.json() as Promise<T>;
}

import { afterEach, describe, expect, it, vi } from "vitest";

import { request, requestBlob, __resetApiClientForTests } from "./client";

// 模拟 Tauri 环境：isTauri=true、get_backend_port 返回 8123，
// 使 getApiBase 返回 http://127.0.0.1:8123，走真实的后端就绪等待逻辑。
vi.mock("@tauri-apps/api/core", () => ({
  isTauri: () => true,
  invoke: async () => 8123,
}));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  __resetApiClientForTests();
});

describe("request", () => {
  it("returns parsed JSON on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
      ),
    );

    const result = await request<{ status: string }>("/health");
    expect(result.status).toBe("ok");
  });

  it("throws ApiError with the server message on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: { code: "project_not_found", message: "项目不存在" },
            }),
            { status: 404 },
          ),
      ),
    );

    const error = await request("/projects/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(Error);
    expect((error as { status: number }).status).toBe(404);
    expect((error as { code: string }).code).toBe("project_not_found");
    expect((error as { message: string }).message).toBe("项目不存在");
  });

  it("falls back to a generic message when the body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("Bad Gateway", { status: 502 })),
    );

    const error = await request("/projects/x").catch((e: unknown) => e);
    expect((error as { status: number }).status).toBe(502);
    expect((error as { message: string }).message).toContain("502");
  });

  it("returns undefined on a 204 response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 204 })),
    );

    const result = await request("/projects/x", { method: "DELETE" });
    expect(result).toBeUndefined();
  });

  it("requestBlob returns the response body as a blob", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response("zipdata", {
            status: 200,
            headers: { "Content-Type": "application/zip" },
          }),
      ),
    );

    const blob = await requestBlob("/projects/x/export");
    expect(blob).toBeInstanceOf(Blob);
    expect(await blob.text()).toBe("zipdata");
  });

  it("waits for the backend health check before the real request", async () => {
    let healthAttempts = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/api/health")) {
          healthAttempts += 1;
          if (healthAttempts === 1) {
            throw new TypeError("Failed to fetch");
          }
          return new Response("{}", { status: 200 });
        }
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }),
    );

    const result = await request<{ ok: boolean }>("/projects");
    expect(result.ok).toBe(true);
    expect(healthAttempts).toBeGreaterThan(1);
  });

  it("throws a friendly error when the backend never becomes ready", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );

    // 提前挂 catch，避免 advanceTimers 期间 rejection 无人处理
    const errorPromise = request("/projects").catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(20000);
    const error = await errorPromise;
    expect((error as { code: string }).code).toBe("backend_not_ready");
    expect((error as { message: string }).message).toContain(
      "后端服务启动超时",
    );
  });

  it("wraps network errors with an actionable message", async () => {
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls += 1;
        if (url.includes("/api/health")) {
          return new Response("{}", { status: 200 });
        }
        throw new TypeError("Failed to fetch");
      }),
    );

    const error = await request("/projects").catch((e: unknown) => e);
    expect((error as { code: string }).code).toBe("network_error");
    expect((error as { message: string }).message).toContain(
      "无法连接后端服务",
    );
    expect(calls).toBe(2);
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";

import { request, requestBlob } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
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
});

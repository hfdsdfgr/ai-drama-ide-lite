import { afterEach, describe, expect, it, vi } from "vitest";

import { importNovel } from "./novels";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("novels api", () => {
  it("importNovel posts the raw file with an encoded filename", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ id: "novel_1" }), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["content"], "第一章 测试.txt");
    const result = await importNovel("proj_1", file);
    expect(result.id).toBe("novel_1");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe(
      "/api/projects/proj_1/novels/import?filename=%E7%AC%AC%E4%B8%80%E7%AB%A0%20%E6%B5%8B%E8%AF%95.txt",
    );
    expect(init.method).toBe("POST");
    expect(init.body).toBe(file);
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";

import { __resetApiClientForTests } from "./client";
import {
  getProjectPromptSettings,
  previewProjectPromptStage,
  saveProjectPromptStage,
} from "./promptSettings";

afterEach(() => {
  vi.unstubAllGlobals();
  __resetApiClientForTests();
});

function stubFetch(body: unknown, status = 200) {
  const mock = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", mock);
  return mock;
}

describe("project prompt settings api", () => {
  it("reads the current project settings and keeps its revision", async () => {
    const mock = stubFetch({ revision: 7, stages: [] });
    const settings = await getProjectPromptSettings("project 1");
    const [url] = mock.mock.calls[0] as unknown as [string];
    expect(url).toBe("/api/projects/project%201/prompt-settings");
    expect(settings.revision).toBe(7);
  });

  it("preserves explicit empty negative prompts and uses optimistic revision", async () => {
    const mock = stubFetch({ revision: 8, stages: [] });
    await saveProjectPromptStage("p1", "shot.image", {
      expected_revision: 7,
      rules: "静态画面为主",
      negative_prompt: "",
    });
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/projects/p1/prompt-settings/shot.image");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual({
      expected_revision: 7,
      rules: "静态画面为主",
      negative_prompt: "",
    });
  });

  it("uses null rules to restore defaults without generating any output", async () => {
    const mock = stubFetch({ revision: 9, stages: [] });
    await saveProjectPromptStage("p1", "storyboard", {
      expected_revision: 8,
      rules: null,
    });
    expect(mock).toHaveBeenCalledTimes(1);
    const [, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ expected_revision: 8, rules: null });
  });

  it("keeps intentionally empty media rules distinct from restoring defaults", async () => {
    const mock = stubFetch({ revision: 10, stages: [] });
    await saveProjectPromptStage("p1", "image", {
      expected_revision: 9,
      rules: "",
    });
    const [, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ expected_revision: 9, rules: "" });
  });

  it("previews an unsaved rule with default negative prompts", async () => {
    const mock = stubFetch({ stage_id: "image", system_prompt: "规则与固定要求" });
    const preview = await previewProjectPromptStage("p1", "image", {
      rules: "水墨风格",
      negative_prompt: null,
    });
    const [url, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/projects/p1/prompt-settings/image/preview");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      rules: "水墨风格",
      negative_prompt: null,
    });
    expect(preview.system_prompt).toBe("规则与固定要求");
  });

  it("surfaces save conflicts for the editor to preserve unsaved changes", async () => {
    stubFetch(
      { error: { code: "revision_conflict", message: "配置已变更，请刷新" } },
      409,
    );
    await expect(
      saveProjectPromptStage("p1", "script", {
        expected_revision: 1,
        rules: "新规则",
      }),
    ).rejects.toMatchObject({
      status: 409,
      code: "revision_conflict",
      message: "配置已变更，请刷新",
    });
  });
});

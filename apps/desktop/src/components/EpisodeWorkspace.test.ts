import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { EpisodeWorkspace } from "./EpisodeWorkspace";
import type { EpisodeShot, EpisodeWorkspace as Workspace } from "../types/overview";

const shot: EpisodeShot = {
  shot_id: "s1",
  scene_id: "scene1",
  scene_title: "山门",
  shot_number: 1,
  order_index: 0,
  script_status: "ready",
  asset_status: "ready",
  prompt_status: "ready",
  image_status: "stale",
  video_status: "ready",
  review_status: "passed",
  assets: [],
  blockers: [],
};
function render(data: Workspace, notice = "") {
  return renderToStaticMarkup(
    createElement(EpisodeWorkspace, {
      data,
      selectedEpisodeId: "ep1",
      preparing: false,
      notice,
      onSelectEpisode() {},
      onPrepare() {},
    }),
  );
}
const data: Workspace = {
  project_id: "p1",
  episodes: [
    {
      episode_id: "ep1",
      title: "第一集",
      order_index: 0,
      scene_count: 1,
      shot_count: 1,
      completed_shots: 0,
      attention_count: 1,
      active_count: 0,
      stale_count: 1,
      shots: [shot],
    },
  ],
};

describe("dependency workspace rendering", () => {
  it("shows a textual stale status and contextual shot count", () => {
    const html = render(data);
    expect(html).toContain("待确认");
    expect(html).toContain("1 个镜头依赖待确认");
    expect(html).not.toContain("undefined");
  });
  it("keeps historical evidence in disclosure and provides media-specific action", () => {
    const html = render({
      ...data,
      episodes: [
        {
          ...data.episodes[0],
          shots: [
            {
              ...shot,
              dependency_issues: [
                {
                  state: "pinned",
                  media: "video",
                  label: "关键帧：沿用指定 v1",
                  source_id: "s1",
                  source_name: "关键帧",
                  used_version_id: "v1",
                  used_version: 1,
                  current_version_id: "v2",
                  current_version: 2,
                },
              ],
            },
          ],
        },
      ],
    });
    expect(html).toContain("<summary>沿用指定版</summary>");
    expect(html).toContain("配置视频重新生成");
    expect(html).toContain("关键帧：沿用指定 v1");
  });
  it("uses one live status when preflight notice is present", () => {
    expect(render(data, "预检完成").match(/role="status"/g)).toHaveLength(1);
  });
});

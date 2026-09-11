// Local browser acceptance for Phase 24 M2. All API calls are mocked.
// node scripts/verify-workflow-ui.mjs <playwright-module-directory> <vite-url> <output-directory>
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import assert from "node:assert/strict";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2]);
const base = process.argv[3];
const output = path.resolve(process.argv[4]);
await mkdir(output, { recursive: true });

const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const page = await browser.newPage({
    colorScheme: "dark",
    reducedMotion: "reduce",
  });
  const errors = [];
  const savedBodies = [];
  const appliedBodies = [];
  const startedBodies = [];
  const updatedTemplates = [];
  let deletedTemplates = 0;
  let revision = 0;
  let jobs = [];
  const baseConfig = {
    auto_continue: false,
    storyboard: { enabled: true, model_id: "llm1", capability: "llm" },
    shot_images: {
      enabled: true,
      model_id: "img1",
      capability: "text_to_image",
      aspect_ratio: "16:9",
    },
    videos: {
      enabled: false,
      model_id: "vid1",
      capability: "image_to_video",
      aspect_ratio: "720P",
      duration_mode: "shot",
      duration: 5,
    },
  };
  let config = structuredClone(baseConfig);
  const model = (id, model_id, model_type, capabilities) => ({
    id,
    model_id,
    model_type,
    capabilities,
    provider_id: "provider1",
    provider_name: "测试服务",
    provider_base_url: "",
    provider_needs_key: false,
    provider_has_api_key: true,
    provider_enabled: true,
    capability_source: "manual",
    enabled: true,
    is_default_image: false,
    is_default_video: false,
    created_at: "2026-09-11T00:00:00Z",
    updated_at: "2026-09-11T00:00:00Z",
  });
  const shot = {
    shot_id: "s1",
    scene_id: "scene1",
    scene_title: "山门",
    shot_number: 1,
    order_index: 0,
    script_status: "ready",
    asset_status: "ready",
    prompt_status: "ready",
    image_status: "stale",
    video_status: "missing",
    review_status: "pending",
    assets: [],
    blockers: [],
    stale_count: 1,
  };
  const workspace = {
    project_id: "qa",
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
  const job = {
    job_id: "pipe1",
    project_id: "qa",
    type: "pipeline",
    status: "queued",
    progress: 0,
    model_id: "",
    provider_id: "",
    capability: "pipeline",
    error: null,
    error_category: "",
    attempts: 0,
    target_id: "ep1",
    target_type: "episode",
    target_label: "第一集",
    batch_id: "",
    batch_label: "",
    created_at: "2026-09-11T00:00:00Z",
    started_at: null,
    completed_at: null,
    paused_at: null,
    cancelled_at: null,
  };

  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const p = url.pathname;
    let body = {};
    if (p === "/api/projects/qa/overview")
      body = { project_id: "qa", stages: [] };
    else if (p === "/api/projects/qa/overview/episodes") body = workspace;
    else if (p === "/api/projects/qa/quality")
      body = {
        project_id: "qa",
        summary: { flagged: 0, passed: 0, pending: 0, total: 0 },
        items: [],
      };
    else if (p === "/api/jobs/project-state")
      body = { project_id: "qa", paused: false };
    else if (p === "/api/jobs") body = jobs;
    else if (p === "/api/models")
      body = [
        model("llm1", "文本模型", "llm", []),
        model("img1", "图片模型", "image", ["text_to_image"]),
        model("vid1", "视频模型", "video", ["image_to_video"]),
      ];
    else if (p === "/api/projects/qa/workflow-templates")
      body = [
        {
          id: "tpl1",
          project_id: "qa",
          name: "竖屏模板",
          description: "",
          schema_version: 1,
          revision: 1,
          config: {
            ...structuredClone(baseConfig),
            auto_continue: true,
            shot_images: { ...baseConfig.shot_images, aspect_ratio: "9:16" },
          },
          created_at: "",
          updated_at: "",
        },
      ];
    else if (
      p === "/api/projects/qa/workflow-templates/tpl1" &&
      request.method() === "PATCH"
    ) {
      const input = request.postDataJSON();
      updatedTemplates.push(input);
      body = {
        id: "tpl1",
        project_id: "qa",
        name: input.name || "竖屏模板",
        description: "",
        schema_version: 1,
        revision: 2,
        config: input.config || baseConfig,
        created_at: "",
        updated_at: "now",
      };
    } else if (
      p === "/api/projects/qa/workflow-templates/tpl1" &&
      request.method() === "DELETE"
    ) {
      deletedTemplates += 1;
      return route.fulfill({ status: 204, body: "" });
    } else if (
      p === "/api/projects/qa/episodes/ep1/workflow-config" &&
      request.method() === "GET"
    )
      body = {
        project_id: "qa",
        episode_id: "ep1",
        revision,
        config,
        updated_at: null,
      };
    else if (
      p === "/api/projects/qa/episodes/ep1/workflow-config" &&
      request.method() === "PUT"
    ) {
      const input = request.postDataJSON();
      savedBodies.push(input);
      revision += 1;
      config = input.config;
      body = {
        project_id: "qa",
        episode_id: "ep1",
        revision,
        config,
        updated_at: "now",
      };
    } else if (p.endsWith("/preview-template"))
      body = {
        template_id: "tpl1",
        template_revision: 1,
        config_revision: revision,
        differences: [
          {
            field_path: "auto_continue",
            label: "自动继续",
            current_value: false,
            template_value: true,
            compatible: true,
            reason: "",
          },
          {
            field_path: "shot_images.aspect_ratio",
            label: "图片比例",
            current_value: config.shot_images.aspect_ratio,
            template_value: "9:16",
            compatible: true,
            reason: "",
          },
        ],
      };
    else if (p.endsWith("/apply-template")) {
      const input = request.postDataJSON();
      appliedBodies.push(input);
      revision += 1;
      if (input.selected_fields.includes("shot_images.aspect_ratio"))
        config.shot_images.aspect_ratio = "9:16";
      body = {
        project_id: "qa",
        episode_id: "ep1",
        revision,
        config,
        updated_at: "now",
      };
    } else if (p === "/api/projects/qa/pipeline/episodes/ep1/plan")
      body = {
        project_id: "qa",
        episode_id: "ep1",
        episode_title: "第一集",
        config_revision: revision,
        config,
        can_start: true,
        stages: [
          {
            key: "shot_images",
            label: "分镜图生成",
            kind: "image",
            status: "ready",
            model_id: "img1",
            missing_reason: "",
          },
        ],
      };
    else if (p === "/api/projects/qa/pipeline/episodes/ep1/start") {
      startedBodies.push(request.postDataJSON());
      jobs = [job];
      body = job;
    } else if (p === "/api/projects/qa/pipeline/episodes/ep1/status")
      body = {
        project_id: "qa",
        episode_id: "ep1",
        job_id: "pipe1",
        stages: [
          {
            stage_key: "shot_images",
            status: "queued",
            message: "",
            updated_at: "",
          },
        ],
      };
    else if (p === "/api/projects/qa/graph/view")
      body = {
        project_id: "qa",
        scope: {
          type: url.searchParams.has("scene_id") ? "scene" : "shot",
          id: url.searchParams.get("scene_id") || "s1",
        },
        total: 1,
        shots: [
          {
            shot_id: "s1",
            label: "山门 · 镜头 1",
            nodes: [
              {
                id: "asset-v1",
                entity_type: "character",
                entity_id: "a1",
                label: "林凡",
                version: 1,
                current_version: 2,
                state: "stale",
                target: { type: "asset", id: "a1", media: "image" },
              },
              {
                id: "shot-v1",
                entity_type: "shot",
                entity_id: "s1",
                label: "关键帧",
                version: 1,
                current_version: 1,
                state: "stale",
                target: { type: "shot", id: "s1", media: "image" },
              },
            ],
            edges: [
              {
                source: "asset-v1",
                target: "shot-v1",
                relation: "shot_references_asset",
              },
            ],
            issues: [
              {
                state: "stale",
                label: "林凡：使用 v1，当前 v2",
                media: "image",
              },
            ],
          },
        ],
      };
    else if (p === "/api/jobs/batch")
      body = { affected: 0, jobs: [], project_paused: false };
    else body = [];
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
  await page.route("**/src/main.tsx*", (route) =>
    route.fulfill({
      contentType: "application/javascript",
      body: `
    import React from '/node_modules/.vite/deps/react.js';
    import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
    import {GenerationPage} from '/src/pages/GenerationPage.tsx';
    import '/src/index.css'; import '/src/App.css';
    ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(GenerationPage,{active:true,projectId:'qa'}));
  `,
    }),
  );

  await page.goto(base);
  await page
    .getByRole("heading", { name: "本集制作配置" })
    .waitFor({ timeout: 10000 });
  const ratio = page.getByLabel("画面比例");
  await ratio.selectOption("1:1");
  assert.equal(
    startedBodies.length,
    0,
    "editing configuration must not create a job",
  );
  await page.getByRole("button", { name: "保存本集配置" }).click();
  await page.getByText("本集制作配置已保存。").waitFor();
  assert.equal(savedBodies.at(-1).config.shot_images.aspect_ratio, "1:1");

  await page.getByRole("button", { name: "比较配置" }).click();
  await page.getByText("选择要应用的配置").waitFor();
  assert.equal(
    await page.getByRole("button", { name: "应用所选配置" }).isDisabled(),
    true,
  );
  await page.getByLabel("图片比例").check();
  await page.getByRole("button", { name: "应用所选配置" }).click();
  await page.getByText("已应用所选配置。").waitFor();
  assert.deepEqual(appliedBodies.at(-1).selected_fields, [
    "shot_images.aspect_ratio",
  ]);

  await page.getByRole("button", { name: "镜头依赖" }).click();
  await page.getByRole("heading", { name: "版本依赖" }).waitFor();
  assert.match(
    await page.locator(".dependency-view").innerText(),
    /林凡 v1[\s\S]*关键帧 v1/,
  );
  await page.getByRole("button", { name: "关闭" }).click();
  await page.getByRole("button", { name: "本场依赖" }).click();
  await page.getByText("展示当前场景结果实际使用的参考版本。").waitFor();

  await page.getByText("管理所选模板").click();
  await page.getByLabel("模板名称").fill("竖屏模板 2");
  await page.getByRole("button", { name: "重命名" }).click();
  await page.getByText("模板已重命名为“竖屏模板 2”。").waitFor();
  assert.equal(updatedTemplates.at(-1).name, "竖屏模板 2");
  await page.getByRole("button", { name: "删除模板" }).click();
  await page.getByRole("button", { name: "确认删除模板" }).click();
  await page.getByText(/已删除；已应用到剧集的配置不受影响/).waitFor();
  assert.equal(deletedTemplates, 1);

  for (const width of [1440, 900]) {
    await page.setViewportSize({ width, height: 900 });
    await page.screenshot({
      path: path.join(output, `workflow-${width}.png`),
      fullPage: true,
    });
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      `${width}px must not overflow horizontally`,
    );
  }
  await page.getByRole("button", { name: "开始制作本集" }).click();
  await page.getByText("本集生产任务已创建。").waitFor();
  assert.equal(startedBodies.length, 1);
  assert.equal(startedBodies[0].expected_config_revision, revision);
  assert.deepEqual(errors, []);
  console.log(
    "PASS: workflow save/manage, explicit diff selection, shot/scene dependency view, episode start, 1440/900 layout",
  );
} finally {
  await browser.close();
}

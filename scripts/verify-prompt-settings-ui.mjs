// Offline browser acceptance. All API requests are intercepted; no provider is called.
// node scripts/verify-prompt-settings-ui.mjs <playwright-module-directory> <vite-url> <output-directory>
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2]);
const base = process.argv[3];
const output = path.resolve(process.argv[4]);
await mkdir(output, { recursive: true });

const contract = '只输出一个 JSON 对象，不要解释、不要代码块标记：{"episode": {"title": "分集标题", "summary": "分集剧情摘要"}, "scenes": [{"title": "场景标题", "slugline": "场景位置与时间", "action": "动作描写", "dialogue": "角色台词，每行：角色名：台词"}]}。';
const definitions = [
  {
    id: "script_episode",
    label: "分集剧本",
    group: "剧本与分镜",
    description: "将当前小说改编为分集剧本，保持角色与核心情节一致。",
    default_rules: "你是一位专业编剧。保持主要人物与核心事件，按场景组织戏剧冲突。\n对白贴近人物性格，动作可直接用于后续分镜制作。",
    default_negative_prompt: null,
    allow_empty_rules: false,
    contract,
  },
  {
    id: "image_shot",
    label: "分镜图片",
    group: "图片",
    description: "控制分镜画面的风格和视觉一致性。",
    default_rules: "保持角色身份、服装与场景一致，使用清晰的画面构图。",
    default_negative_prompt: "模糊，畸形，水印",
    allow_empty_rules: true,
    contract: "",
  },
  {
    id: "video_shot",
    label: "镜头视频",
    group: "视频",
    description: "控制镜头运动与画面连续性。",
    default_rules: "保持首帧主体一致，动作自然，镜头连续。",
    default_negative_prompt: null,
    allow_empty_rules: true,
    contract: "",
  },
];
const compile = (rules, fixedContract) =>
  fixedContract ? `${rules}\n\n固定输出要求：\n${fixedContract}` : rules;
const settingsFor = () => ({
  revision: 0,
  stages: definitions.map((definition) => ({
    ...definition,
    rules: definition.default_rules,
    negative_prompt: definition.default_negative_prompt,
    customized: false,
    preview: compile(definition.default_rules, definition.contract),
  })),
});
const projects = {
  "qa-a": { name: "提示词验收项目 A", settings: settingsFor() },
  "qa-b": { name: "提示词验收项目 B", settings: settingsFor() },
};
const browserErrors = [];
const consoleErrors = [];
const unexpectedApi = [];
const saves = [];
const previews = [];
const screenshots = [];
let rejectNextSave = false;
let conflictResponses = 0;
let result = "FAILED";

const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
    reducedMotion: "reduce",
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const apiPath = url.pathname;
    if (!apiPath.startsWith("/api/")) return route.continue();
    const method = request.method();
    let body;
    let status = 200;
    const match = apiPath.match(
      /^\/api\/projects\/(qa-[ab])(?:\/prompt-settings(?:\/([^/]+)(\/preview)?)?)?$/,
    );
    if (method === "GET" && apiPath === "/api/version") {
      body = { app_name: "AI Drama IDE Lite", version: "0.0.0-qa" };
    } else if (
      method === "GET" &&
      ["/api/providers/presets", "/api/providers", "/api/models"].includes(apiPath)
    ) {
      body = [];
    } else if (match) {
      const [, projectId, stageId, previewSuffix] = match;
      const project = projects[projectId];
      if (method === "GET" && !apiPath.includes("/prompt-settings")) {
        body = { id: projectId, name: project.name, description: "", created_at: "", updated_at: "" };
      } else if (method === "GET" && !stageId) {
        body = project.settings;
      } else {
        const stage = project.settings.stages.find((item) => item.id === stageId);
        const input = request.postDataJSON();
        if (!stage) {
          unexpectedApi.push(`${method} ${apiPath}`);
          status = 404;
          body = { error: { code: "unknown_stage", message: "未找到测试环节" } };
        } else if (method === "POST" && previewSuffix) {
          previews.push({ projectId, stageId, input });
          const rules = input.rules ?? stage.default_rules;
          const negative = input.negative_prompt === null
            ? stage.default_negative_prompt
            : input.negative_prompt ?? stage.negative_prompt;
          body = {
            stage_id: stageId,
            rules,
            negative_prompt: negative,
            system_prompt: compile(rules, stage.contract),
            contract: stage.contract,
          };
        } else if (method === "PUT" && !previewSuffix) {
          saves.push({ projectId, stageId, input });
          if (rejectNextSave || input.expected_revision !== project.settings.revision) {
            rejectNextSave = false;
            project.settings.revision += 1;
            conflictResponses += 1;
            status = 409;
            body = { error: { code: "revision_conflict", message: "项目提示词配置已更新，请刷新后重试" } };
          } else {
            const restoring = input.rules === null;
            stage.rules = restoring ? stage.default_rules : input.rules;
            if (restoring || input.negative_prompt === null) {
              stage.negative_prompt = stage.default_negative_prompt;
            } else if ("negative_prompt" in input) {
              stage.negative_prompt = input.negative_prompt;
            }
            stage.customized = !restoring;
            stage.preview = compile(stage.rules, stage.contract);
            project.settings.revision += 1;
            body = project.settings;
          }
        } else {
          unexpectedApi.push(`${method} ${apiPath}`);
          status = 400;
          body = { error: { code: "unexpected_request", message: "不允许的测试请求" } };
        }
      }
    } else {
      unexpectedApi.push(`${method} ${apiPath}`);
      status = 400;
      body = { error: { code: "unexpected_request", message: "所有请求应为本地配置操作" } };
    }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.route("**/src/main.tsx*", async (route) => {
    const original = await (await route.fetch()).text();
    const reactSpecifier = original.match(/["']([^"']*\/react\.js(?:\?[^"']*)?)["']/)?.[1];
    const reactDomSpecifier = original.match(/["']([^"']*\/react-dom_client\.js(?:\?[^"']*)?)["']/)?.[1];
    assert.ok(reactSpecifier && reactDomSpecifier, "Vite must expose the exact React dependency imports");
    await route.fulfill({
      contentType: "application/javascript",
      body: `
      import React from ${JSON.stringify(reactSpecifier)};
      import ReactDOM from ${JSON.stringify(reactDomSpecifier)};
      import {SettingsPage} from '/src/pages/SettingsPage.tsx';
      import '/src/index.css'; import '/src/App.css';
      function Harness() {
        const [projectId, setProjectId] = React.useState('qa-a');
        return React.createElement('div', {className:'app'},
          React.createElement('div', {className:'app-shell'},
            React.createElement('div', {className:'app-content'},
              React.createElement('nav', {className:'toolbar', style:{padding:'var(--space-3)'}},
                React.createElement('button', {onClick:()=>setProjectId('qa-a')}, '测试：项目 A'),
                React.createElement('button', {onClick:()=>setProjectId('qa-b')}, '测试：项目 B'),
                React.createElement('button', {onClick:()=>setProjectId('')}, '测试：无项目')),
              React.createElement('main', {className:'app-main'},
                React.createElement('div', {className:'view-pane active'},
                  React.createElement(SettingsPage, {projectId, active:true, onChooseProject:()=>setProjectId('qa-a')}))))));
      }
      ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(Harness));
    `,
    });
  });

  const rules = page.getByRole("textbox", { name: "创作规则", exact: true });
  const stageSelect = page.locator(".project-prompt-stage-row select");
  const save = page.getByRole("button", { name: "保存本环节", exact: true });
  const preview = page.getByRole("button", { name: "预览规则", exact: true });
  const restore = page.getByRole("button", { name: "恢复默认", exact: true });
  const rulePreview = page.getByLabel("组装后的规则", { exact: true });
  const waitRules = async (value) => {
    await page.waitForFunction((expected) => {
      const field = document.querySelector(".project-prompt-editor textarea");
      return field?.value === expected && !field.disabled;
    }, value);
  };

  await page.goto(base);
  await page.getByText("当前项目：提示词验收项目 A", { exact: true }).waitFor();
  await waitRules(definitions[0].default_rules);
  assert.equal(await save.isDisabled(), true);
  assert.equal(await rules.getAttribute("maxlength"), "12000");
  assert.match(await rulePreview.innerText(), /"episode": \{/);
  assert.match(await rulePreview.innerText(), /"scenes": \[/);
  assert.equal(await stageSelect.locator("option").count(), 3, "registry stages must render dynamically");

  const customScript = "对话采用固定机位，以角色冲突推动剧情。";
  await rules.fill(customScript);
  await page.getByText("有未保存的编辑", { exact: true }).waitFor();
  assert.equal(await stageSelect.isDisabled(), true);
  assert.equal(saves.length, 0, "editing must not save or generate automatically");
  await preview.click();
  await rulePreview.waitFor();
  assert.match(await rulePreview.innerText(), /对话采用固定机位/);
  assert.match(await rulePreview.innerText(), /"episode": \{/);
  assert.match(await rulePreview.innerText(), /"scenes": \[/);
  assert.equal(saves.length, 0, "preview must not persist drafts");
  await page.getByText("固定输出要求（只读）", { exact: true }).click();
  assert.match(await page.locator(".project-prompt-inspector").innerText(), /只输出一个 JSON 对象/);
  await save.click();
  await page.getByText("已保存，仅影响后续生成。", { exact: true }).waitFor();
  assert.deepEqual(saves.at(-1).input, { expected_revision: 0, rules: customScript });
  assert.equal(await stageSelect.isDisabled(), false);

  await stageSelect.selectOption("image_shot");
  await waitRules(definitions[1].default_rules);
  assert.equal(await page.getByText("固定输出要求（只读）", { exact: true }).count(), 0);
  const negativeMode = page.locator(".project-prompt-editor select");
  await negativeMode.selectOption("custom");
  const negative = page.getByRole("textbox", { name: "自定义负向词内容", exact: true });
  assert.equal(await negative.getAttribute("maxlength"), "1000");
  await negative.fill("");
  assert.equal(await negative.isVisible(), true, "empty custom editor must remain editable");
  await negativeMode.selectOption("none");
  await rules.fill("");
  assert.equal(await save.isDisabled(), false, "empty media creative rules are intentional");
  await preview.click();
  await rulePreview.waitFor();
  assert.equal(await rulePreview.innerText(), "");
  assert.equal(previews.at(-1).input.negative_prompt, "");
  await save.click();
  await page.getByText("已保存，仅影响后续生成。", { exact: true }).waitFor();
  assert.deepEqual(saves.at(-1).input, { expected_revision: 1, rules: "", negative_prompt: "" });
  await restore.click();
  await page.getByText("已恢复本环节默认规则。", { exact: true }).waitFor();
  await waitRules(definitions[1].default_rules);
  assert.deepEqual(saves.at(-1).input, { expected_revision: 2, rules: null });
  assert.equal(await negativeMode.inputValue(), "default");
  assert.equal(await restore.isDisabled(), true);

  await stageSelect.selectOption("video_shot");
  await waitRules(definitions[2].default_rules);
  assert.equal(await negativeMode.count(), 0, "video stages must not expose unsupported negative prompts");
  await stageSelect.selectOption("script_episode");
  await waitRules(customScript);
  await rules.fill("");
  assert.equal(await save.isDisabled(), true, "text stages must reject empty creative rules");
  assert.equal(await preview.isDisabled(), true);
  const conflictDraft = "冲突后保留的项目 A 草稿";
  await rules.fill(conflictDraft);
  rejectNextSave = true;
  await save.click();
  await page.getByRole("alert").filter({ hasText: "你的编辑已保留" }).waitFor();
  assert.equal(await rules.inputValue(), conflictDraft);
  assert.equal(await stageSelect.isDisabled(), true);

  await page.getByRole("button", { name: "测试：项目 B", exact: true }).click();
  await page.getByText("当前项目：提示词验收项目 B", { exact: true }).waitFor();
  await waitRules(definitions[0].default_rules);
  assert.equal(await stageSelect.isDisabled(), false, "project A draft must not leak into B");
  const projectBDraft = "项目 B 的独立创作规则";
  await rules.fill(projectBDraft);
  await page.getByRole("button", { name: "测试：项目 A", exact: true }).click();
  await page.getByText("当前项目：提示词验收项目 A", { exact: true }).waitFor();
  await waitRules(conflictDraft);
  assert.equal(await stageSelect.isDisabled(), true);
  await page.getByRole("button", { name: "放弃编辑并刷新", exact: true }).click();
  await waitRules(customScript);
  const refreshedScript = "刷新后按新修订保存，保留人物性格并减少冗余对白。";
  await rules.fill(refreshedScript);
  await save.click();
  await page.getByText("已保存，仅影响后续生成。", { exact: true }).waitFor();
  assert.equal(saves.at(-1).input.expected_revision, 4);

  await page.getByRole("button", { name: "测试：无项目", exact: true }).click();
  await page.getByText("先在主页选择项目，再配置该项目的提示词。", { exact: true }).waitFor();
  assert.equal(await page.getByRole("button", { name: "选择项目", exact: true }).isVisible(), true);
  assert.equal(await page.getByRole("heading", { name: "Provider 与模型", exact: true }).isVisible(), true);
  await page.getByRole("button", { name: "测试：项目 B", exact: true }).click();
  await waitRules(projectBDraft);
  assert.equal(await stageSelect.isDisabled(), true, "B draft must survive project and empty-state switches");
  await page.getByRole("button", { name: "测试：项目 A", exact: true }).click();
  await waitRules(refreshedScript);

  for (const width of [1440, 900]) {
    await page.setViewportSize({ width, height: 900 });
    await page.getByRole("heading", { name: "项目提示词", exact: true }).scrollIntoViewIfNeeded();
    const filename = `prompt-settings-${width}.png`;
    await page.screenshot({ path: path.join(output, filename), fullPage: true });
    screenshots.push(filename);
    assert.equal(
      await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      false,
      `${width}px must not overflow horizontally`,
    );
    assert.equal(
      await page.locator(".project-prompt-settings").evaluate((element) => element.scrollWidth > element.clientWidth),
      false,
      `${width}px prompt settings must not overflow its workspace`,
    );
    if (width === 900) {
      await page.getByRole("heading", { name: "规则预览", exact: true }).scrollIntoViewIfNeeded();
      const previewFilename = "prompt-settings-900-preview.png";
      await page.screenshot({ path: path.join(output, previewFilename), fullPage: true });
      screenshots.push(previewFilename);
    }
  }
  assert.equal(conflictResponses, 1);
  assert.deepEqual(unexpectedApi, [], "no generation or provider operations may be requested");
  assert.deepEqual(browserErrors, []);
  assert.deepEqual(
    consoleErrors.filter((message) => !/Failed to load resource.*409/.test(message)),
    [],
    "only the intentionally mocked HTTP 409 may report a console error",
  );
  result = "PASS";
  console.log("PASS: default/draft/preview, empty media rules and negatives, save/restore, 409 retention, project isolation, 1440/900 layout; all API calls mocked");
} finally {
  await writeFile(path.join(output, "prompt-settings-qa.json"), JSON.stringify({
    result, browserErrors, consoleErrors, unexpectedApi, conflictResponses, saves, previews, screenshots,
  }, null, 2));
  await browser.close();
}

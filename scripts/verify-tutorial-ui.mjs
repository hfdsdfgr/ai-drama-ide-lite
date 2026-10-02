// Real App acceptance, using read-only mocks; all writes/generation requests are blocked.
// node scripts/verify-tutorial-ui.mjs <playwright-module-directory> <vite-url> <output-directory>
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2]);
const base = process.argv[3];
const output = path.resolve(process.argv[4]);
await mkdir(output, { recursive: true });
const project = {
  id: "qa-real-project",
  name: "我的真实项目",
  description: "保持原样",
  created_at: "2026-10-02T00:00:00Z",
  updated_at: "2026-10-02T00:00:00Z",
};
const stage = {
  id: "script_episode",
  label: "分集剧本",
  group: "剧本",
  description: "分集剧本规则",
  allow_empty_rules: false,
  default_rules: "原有规则",
  rules: "原有规则",
  default_negative_prompt: null,
  negative_prompt: null,
  customized: false,
  contract: "只输出 JSON",
  preview: "原有规则\n只输出 JSON",
};
const blockedMutations = [];
const tutorialReads = [];
const browserErrors = [];
const screenshots = [];
let tutorialActive = false;
let offlineTutorialPassed = false;
let result = "FAILED";
const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
    reducedMotion: "reduce",
  });
  page.on("pageerror", (error) =>
    browserErrors.push(error.stack ?? error.message),
  );
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const apiPath = new URL(request.url()).pathname;
    if (!apiPath.startsWith("/api/")) return route.continue();
    if (request.method() !== "GET") {
      blockedMutations.push(`${request.method()} ${apiPath}`);
      return route.abort("blockedbyclient");
    }
    if (tutorialActive) tutorialReads.push(apiPath);
    let body = [];
    if (apiPath === "/api/projects") body = [project];
    else if (apiPath === `/api/projects/${project.id}`) body = project;
    else if (apiPath.endsWith("/prompt-settings"))
      body = { revision: 0, stages: [stage] };
    else if (apiPath.endsWith("/story/bible")) body = { bible: null };
    else if (apiPath.endsWith("/assets/specs"))
      body = { defaults: {}, aspect_ratios: [], art_styles: [] };
    else if (apiPath === "/api/version")
      body = { version: "0.0.0-qa", app_name: "AI Drama IDE Lite" };
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
  await page.goto(base);
  await page.locator(".project-item").filter({ hasText: project.name }).click();
  await page
    .locator(".app-actions")
    .getByRole("button", { name: "设置", exact: true })
    .click();
  const draft = page.locator(".project-prompt-editor textarea").first();
  await draft.fill("我的未保存创作规则，需要原样保留。");
  await page.getByText("有未保存的编辑", { exact: true }).waitFor();
  const tutorialButton = page
    .locator(".app-actions")
    .getByRole("button", { name: "教程", exact: true });
  const settingsButton = page
    .locator(".app-actions")
    .getByRole("button", { name: "设置", exact: true });
  assert.equal(
    await tutorialButton.evaluate((element) =>
      element.nextElementSibling?.getAttribute("aria-label"),
    ),
    "设置",
    "tutorial is beside settings",
  );
  const dialog = page.locator("dialog.creation-tutorial");
  const target = (id) => dialog.locator(`[data-tutorial-target="${id}"]`);
  const stepNumber = async () =>
    dialog.locator(".tutorial-coach-copy .tutorial-eyebrow").innerText();
  const checkHighlight = async (id) => {
    try {
      await page.waitForFunction(
        (targetId) => {
          const element = document.querySelector(
            `dialog [data-tutorial-target="${targetId}"]`,
          );
          const ring = document.querySelector("[data-tutorial-highlight]");
          if (!element || !ring) return false;
          const rect = element.getBoundingClientRect();
          const canvas = element
            .closest(".tutorial-canvas")
            ?.getBoundingClientRect();
          const x = Math.max(rect.left, canvas?.left ?? 0);
          const y = Math.max(rect.top, canvas?.top ?? 0);
          return (
            Math.abs(Number(ring.getAttribute("x")) - (x - 5)) < 2 &&
            Math.abs(Number(ring.getAttribute("y")) - (y - 5)) < 2 &&
            Number(ring.getAttribute("width")) > 10
          );
        },
        id,
        { timeout: 5000 },
      );
    } catch (error) {
      const debug = await page.evaluate((targetId) => {
        const element = document.querySelector(
          `dialog [data-tutorial-target="${targetId}"]`,
        );
        const canvas = element?.closest(".tutorial-canvas");
        const ring = document.querySelector("[data-tutorial-highlight]");
        return {
          targetId,
          target: element?.getBoundingClientRect().toJSON(),
          canvas: canvas?.getBoundingClientRect().toJSON(),
          scrollTop: canvas?.scrollTop,
          ring: ring?.outerHTML,
          currentStep: document.querySelector(".tutorial-coach-copy")
            ?.textContent,
        };
      }, id);
      await writeFile(
        path.join(output, "highlight-failure.json"),
        JSON.stringify(debug, null, 2),
      );
      await page.screenshot({
        path: path.join(output, "highlight-failure.png"),
      });
      throw error;
    }
  };
  const shot = async (name) => {
    await page.screenshot({ path: path.join(output, name) });
    screenshots.push(name);
    assert.equal(
      await dialog.evaluate(
        (element) => element.scrollWidth > element.clientWidth,
      ),
      false,
      "dialog must not overflow horizontally",
    );
  };
  const open = async () => {
    await tutorialButton.click();
    tutorialActive = true;
    await dialog.waitFor();
    await checkHighlight("start");
  };
  await open();
  await shot("tutorial-welcome-1440.png");
  assert.equal(await target("nav-script").isDisabled(), true);
  await target("nav-script").evaluate((element) => element.click());
  assert.match(await stepNumber(), /步骤 1 \/ 22/);
  await page.keyboard.press("Escape");
  tutorialActive = false;
  await dialog.waitFor({ state: "detached" });
  assert.equal(
    await tutorialButton.evaluate(
      (element) => document.activeElement === element,
    ),
    true,
  );
  assert.equal(await draft.inputValue(), "我的未保存创作规则，需要原样保留。");
  assert.equal(await settingsButton.getAttribute("aria-current"), "page");
  await open();
  await target("start").click();
  await checkHighlight("create-project");
  await dialog.getByRole("button", { name: "上一步", exact: true }).click();
  await checkHighlight("start");
  await target("start").click();
  await target("create-project").click();
  await checkHighlight("nav-novel");
  await target("nav-novel").click();
  await target("import-novel").click();
  await checkHighlight("novel-content");
  assert.match(await target("novel-content").innerText(), /林晚/);
  await dialog.locator(".tutorial-canvas").evaluate((element) => {
    element.scrollTop = 120;
  });
  await checkHighlight("novel-content");
  await dialog.getByRole("button", { name: "阅读完毕，继续" }).click();
  await target("nav-bible").click();
  await target("analyze-story").click();
  await checkHighlight("bible-content");
  await shot("tutorial-bible-1440.png");
  await dialog.getByRole("button", { name: "设定已核对" }).click();
  await target("nav-script").click();
  await target("generate-script").click();
  await checkHighlight("save-script");
  await target("save-script").click();
  await target("nav-assets").click();
  await target("generate-assets").click();
  await checkHighlight("asset-content");
  assert.equal(await dialog.locator(".tutorial-art-gallery img").count(), 4);
  for (const width of [1440, 900, 640]) {
    await page.setViewportSize({ width, height: 900 });
    await checkHighlight("asset-content");
    await shot(`tutorial-assets-${width}.png`);
    assert.equal(
      await dialog
        .locator(".tutorial-coach")
        .getByRole("button", { name: "参考资产已核对" })
        .isVisible(),
      true,
    );
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await dialog.getByRole("button", { name: "参考资产已核对" }).click();
  await target("nav-storyboard").click();
  await target("generate-shots").click();
  assert.equal(await dialog.locator(".tutorial-shot").count(), 4);
  await checkHighlight("generate-images");
  await target("generate-images").click();
  await checkHighlight("generate-videos");
  await shot("tutorial-storyboard-1440.png");
  await target("generate-videos").click();
  const firstClip = dialog.getByLabel("第一镜头示例视频");
  await firstClip.evaluate((video) => video.play());
  await page.waitForFunction(
    () => document.querySelector("dialog video")?.currentTime > 0.2,
  );
  assert.equal(
    Math.round(await firstClip.evaluate((video) => video.duration)),
    5,
  );
  await firstClip.evaluate((video) => video.pause());
  await target("nav-generation").click();
  await target("prepare-episode").click();
  await checkHighlight("compose-episode");
  assert.equal(await dialog.locator("tbody .tutorial-success").count(), 4);
  await target("compose-episode").click();
  await checkHighlight("finished-film");
  const film = dialog.getByLabel("末班灯火示例短片");
  await film.evaluate((video) => video.play());
  await page.waitForFunction(
    () => document.querySelector("dialog video")?.currentTime > 0.2,
  );
  assert.equal(Math.round(await film.evaluate((video) => video.duration)), 20);
  await film.evaluate((video) => {
    video.pause();
    video.currentTime = 10;
  });
  for (const width of [1440, 900, 640]) {
    await page.setViewportSize({ width, height: 900 });
    await checkHighlight("finished-film");
    await shot(`tutorial-finished-${width}.png`);
  }
  await dialog.getByRole("button", { name: "从头练习" }).click();
  await checkHighlight("start");
  assert.match(await stepNumber(), /步骤 1 \/ 22/);
  const replayTargets = [
    "start",
    "create-project",
    "nav-novel",
    "import-novel",
    "novel-content",
    "nav-bible",
    "analyze-story",
    "bible-content",
    "nav-script",
    "generate-script",
    "save-script",
    "nav-assets",
    "generate-assets",
    "asset-content",
    "nav-storyboard",
    "generate-shots",
    "generate-images",
    "generate-videos",
    "nav-generation",
    "prepare-episode",
    "compose-episode",
  ];
  for (const id of replayTargets) {
    const isButton = await target(id).evaluate(
      (element) => element.tagName === "BUTTON",
    );
    if (isButton) await target(id).click();
    else await dialog.locator(".tutorial-coach > .btn-primary").click();
  }
  await dialog.getByRole("button", { name: "完成教程", exact: true }).click();
  tutorialActive = false;
  await dialog.waitFor({ state: "detached" });
  assert.equal(await draft.inputValue(), "我的未保存创作规则，需要原样保留。");
  await open();
  // Reopening is a fresh session; exiting never changes the original project or draft.
  await dialog.getByRole("button", { name: "退出教程" }).click();
  tutorialActive = false;
  await dialog.waitFor({ state: "detached" });
  assert.equal(await draft.inputValue(), "我的未保存创作规则，需要原样保留。");
  assert.match(
    await page.locator(".project-prompt-head").innerText(),
    /我的真实项目/,
  );
  assert.equal(await settingsButton.getAttribute("aria-current"), "page");
  await open();
  assert.match(await stepNumber(), /步骤 1 \/ 22/);
  await page.keyboard.press("Tab");
  // Native dialogs may let Tab visit browser chrome; background app controls stay inert.
  assert.equal(
    await page
      .locator(".app-shell")
      .evaluate((element) => element.contains(document.activeElement)),
    false,
  );
  await page.keyboard.press("Tab");
  assert.equal(
    await dialog.evaluate((element) =>
      element.contains(document.activeElement),
    ),
    true,
  );
  await page.keyboard.press("Escape");
  tutorialActive = false;
  assert.deepEqual(
    blockedMutations,
    [],
    "tutorial must never request generation or write user data",
  );
  const offlinePage = await browser.newPage({
    viewport: { width: 900, height: 900 },
  });
  offlinePage.on("pageerror", (error) =>
    browserErrors.push(error.stack ?? error.message),
  );
  await offlinePage.route("**/api/**", (route) =>
    new URL(route.request().url()).pathname.startsWith("/api/")
      ? route.abort("blockedbyclient")
      : route.continue(),
  );
  await offlinePage.goto(base);
  await offlinePage
    .locator(".app-actions")
    .getByRole("button", { name: "教程", exact: true })
    .click();
  const offlineDialog = offlinePage.locator("dialog.creation-tutorial");
  for (const id of ["start", "create-project", "nav-novel", "import-novel"])
    await offlineDialog.locator(`[data-tutorial-target="${id}"]`).click();
  await offlineDialog.getByRole("button", { name: "阅读完毕，继续" }).click();
  for (const id of ["nav-bible", "analyze-story"])
    await offlineDialog.locator(`[data-tutorial-target="${id}"]`).click();
  assert.match(
    await offlineDialog
      .locator('[data-tutorial-target="bible-content"]')
      .innerText(),
    /陈叔/,
  );
  offlineTutorialPassed = true;
  await offlinePage.close();
  assert.ok(
    tutorialReads.every(
      (apiPath) => apiPath === "/api/projects" || apiPath === "/api/jobs",
    ),
    "only pre-existing statusbar GET polling may run behind the modal",
  );
  assert.deepEqual(browserErrors, []);
  result = "PASS";
  console.log(
    "PASS: 22-step tutorial, spotlight/scroll/resize, 5s and 20s playback, 1440/900/640 layouts, Escape/focus/back/restart, preserved project and draft, zero write or AI requests",
  );
} finally {
  await writeFile(
    path.join(output, "tutorial-qa.json"),
    JSON.stringify(
      {
        result,
        blockedMutations,
        tutorialReads,
        browserErrors,
        screenshots,
        offlineTutorialPassed,
      },
      null,
      2,
    ),
  );
  await browser.close();
}

// Local UI acceptance using synthetic data; never invokes generation providers.
// node scripts/verify-dependency-ui.mjs <playwright-module-directory> <vite-url> <output-directory>
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2]);
const base = process.argv[3];
const output = path.resolve(process.argv[4]);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const page = await browser.newPage({ colorScheme: "dark", reducedMotion: "reduce" });
  const errors = [];
  page.on("pageerror", error => { errors.push(error.message); console.error(error.message); });
  page.on("requestfailed", request => console.error(request.url(), request.failure()));
  page.on("console", message => { if (message.type() === "error") console.error(message.text()); });
  await page.route(/\/src\/main\.tsx(?:\?.*)?$/, route => route.fulfill({ contentType: "application/javascript", body: `
    import React from '/node_modules/.vite/deps/react.js';
    import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
    import {EpisodeWorkspace} from '/src/components/EpisodeWorkspace.tsx';
    import '/src/index.css'; import '/src/App.css';
    const issue = (state, media, label) => ({state, media, label, source_id:'a1',source_name:'林凡',used_version_id:'a1v1',used_version:1,current_version_id:'a1v2',current_version:2});
    const common = {scene_id:'scene1',scene_title:'山门 · 日',script_status:'ready',asset_status:'ready',prompt_status:'ready',review_status:'passed',assets:[],blockers:[]};
    const shots = [
      {...common,shot_id:'s1',shot_number:1,order_index:0,image_status:'stale',video_status:'stale',dependency_issues:[issue('stale','image','林凡：使用 v1，当前 v2，请确认'),issue('stale','video','源关键帧依赖：林凡服装已更新，请确认')],blockers:[{code:'image_dependency:0',label:'林凡：使用 v1，当前 v2，请确认',target:'storyboard'}]},
      {...common,shot_id:'s2',shot_number:2,order_index:1,image_status:'ready',video_status:'ready',dependency_issues:[issue('pinned','image','林凡：沿用指定 v1')]},
      {...common,shot_id:'s3',shot_number:3,order_index:2,image_status:'ready',video_status:'ready',dependency_issues:[issue('unknown','video','历史视频未记录源关键帧版本，请核实')]},
      {...common,shot_id:'s4',shot_number:4,order_index:3,image_status:'active',video_status:'missing',blockers:[{code:'video_missing',label:'缺少镜头视频',target:'storyboard'}]},
    ];
    window.nav=[];
    ReactDOM.createRoot(document.getElementById('root')).render(React.createElement('main',{style:{padding:'24px',height:'100vh',overflow:'auto'}},React.createElement(EpisodeWorkspace,{data:{project_id:'qa',episodes:[{episode_id:'ep1',title:'青云门初遇 · UI测试数据',order_index:0,scene_count:1,shot_count:4,completed_shots:2,attention_count:2,active_count:1,stale_count:1,pinned_dependency_count:1,unknown_dependency_count:1,shots}]},selectedEpisodeId:'ep1',preparing:false,notice:'',onSelectEpisode:()=>{},onPrepare:()=>{},onJumpToShot:(id,media)=>window.nav.push({id,media})})));
  ` }));
  await page.goto(base);
  console.log("Loaded", page.url());
  await page.getByRole("heading", { name: "剧集制作台" }).waitFor({timeout: 10000}).catch(async error => {
    console.error((await page.content()).slice(0, 2500));
    throw error;
  });
  for (const width of [1440, 900]) {
    await page.setViewportSize({ width, height: 900 });
    const first = page.locator("tbody tr").first();
    for (const detail of await first.locator("details").all()) await detail.locator("summary").click();
    await page.screenshot({ path: path.join(output, `dependency-${width}.png`), fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, "page must not overflow horizontally");
    await first.getByRole("button", { name: "配置视频重新生成" }).click();
    assert.deepEqual(await page.evaluate(() => window.nav.at(-1)), { id: "s1", media: "video" });
    for (const detail of await first.locator("details").all()) await detail.locator("summary").click();
  }
  assert.deepEqual(errors, []);
  console.log("PASS: 1440/900 layout, dependency disclosure, video navigation intent, no page errors");
  await page.close();

  const inspector = await browser.newPage({ viewport: {width:1440,height:900} });
  inspector.on('pageerror', error => console.error('Inspector:', error.message));
  inspector.on('console', message => console.error('Inspector console:', message.type(), message.text()));
  inspector.on('response', response => { if (response.request().resourceType() === 'script' && response.status() !== 200) console.error('Inspector script response:', response.status(), response.url()); });
  const shot = {id:'s1',scene_id:'sc1',shot_number:1,order_index:0,characters:'',action:'抬头',prompt:'图片提示词',duration:5,dialogue:''};
  const scene = {id:'sc1',episode_id:'ep1',title:'测试场景',order_index:0,slugline:'山门',action:'',dialogue:''};
  const episode = {id:'ep1',title:'测试集',order_index:0};
  const image = (id, number, current) => ({id,entity_type:'shot',entity_id:'s1',version:number,is_current:current,payload:{source_refs:[]},file_url:'/test.png'});
  const old = image('im1',1,false), current = image('im2',2,true);
  const video = {id:'vid1',version:1,is_current:true,payload:{user_prompt:'上一版视频运动描述',source_refs:[{type:'shot',id:'s1',version_id:'im1',selection_mode:'historical'}]},file_url:'/test.mp4'};
  const submitted = [];
  await inspector.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith('/api/')) return route.continue();
    const p = url.pathname;
    let body = [];
    if (p.endsWith('/recommendation')) body = {recommended:{model:{id:'model1',model_id:'测试模型',capabilities:['text_to_image','image_to_video']},reasons:[]},alternatives:[],message:''};
    else if (p.endsWith('/script/episodes')) body = [episode];
    else if (p.endsWith('/script/episodes/ep1')) body = {episode,scenes:[scene]};
    else if (p.endsWith('/script/scenes/sc1')) body = {scene,shots:[shot]};
    else if (p.endsWith('/images/versions')) body = [current,old];
    else if (p.endsWith('/images/current')) body = current;
    else if (p.endsWith('/videos/current')) body = video;
    else if (p.endsWith('/generate')) { submitted.push(route.request().postDataJSON()); body = {job_id:'testjob',status:'queued'}; }
    else if (p.includes('/jobs/testjob')) body = {job_id:'testjob',status:'cancelled'};
    else if (p.includes('/current')) body = null;
    await route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
  });
  await inspector.route('**/src/main.tsx*', route => route.fulfill({contentType:'application/javascript',body:`
    import React from '/node_modules/.vite/deps/react.js'; import ReactDOM from '/node_modules/.vite/deps/react-dom_client.js';
    import {StoryboardPage} from '/src/pages/StoryboardPage.tsx'; import '/src/index.css'; import '/src/App.css';
    ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(StoryboardPage,{active:true,projectId:'qa',jumpToShotId:'s1',jumpToMedia:'video'}));
  `}));
  await inspector.goto(base);
  const keyframe = inspector.getByLabel('源关键帧版本', {exact:false});
  await keyframe.waitFor({timeout:10000}).catch(async error => { console.error('Inspector body:', await inspector.locator('body').innerText()); console.error('Inspector html:', (await inspector.content()).slice(-3500)); throw error; });
  await inspector.waitForFunction(() => [...document.querySelectorAll('textarea')].some(el => el.value === '上一版视频运动描述'));
  assert.equal(await keyframe.inputValue(), 'im1', 'restore original video keyframe instead of current');
  assert.equal(submitted.length, 0, 'opening configuration must not generate');
  await keyframe.selectOption('im2');
  await inspector.getByRole('button',{name:'按以上配置重新生成视频'}).click();
  await inspector.waitForTimeout(100);
  assert.equal(submitted.at(-1).source_image_version_id, 'im2');
  assert.deepEqual(submitted.at(-1).reference_version_ids, []);
  assert.deepEqual(submitted.at(-1).pinned_version_ids, []);
  await inspector.close();
  console.log('PASS: real storyboard recipe restore, explicit current keyframe, empty references, no automatic generation');
} finally {
  await browser.close();
}

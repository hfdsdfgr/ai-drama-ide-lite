// Build authored tutorial illustrations and silent clips locally, without AI requests.
// node scripts/build-tutorial-media.mjs <playwright-module-directory> <ffmpeg-executable> <temporary-output-directory>
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { spawnSync } from "node:child_process";

const require = createRequire(import.meta.url);
const { chromium } = require(process.argv[2]);
const ffmpeg = process.argv[3];
const temporary = path.resolve(process.argv[4]);
const output = path.resolve("apps/desktop/public/tutorial");
await mkdir(output, { recursive: true });
await mkdir(temporary, { recursive: true });
const escape = (text) =>
  text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll('"', "&quot;");
const svg = (
  body,
) => `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
<defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="#172c40"/><stop offset="1" stop-color="#486576"/></linearGradient>
<linearGradient id="ground" x2="0" y2="1"><stop stop-color="#233b4b"/><stop offset="1" stop-color="#132535"/></linearGradient>
<radialGradient id="lamp"><stop stop-color="#ffdea0" stop-opacity=".6"/><stop offset="1" stop-color="#e5b96b" stop-opacity="0"/></radialGradient>
<pattern id="rain" width="88" height="78" patternUnits="userSpaceOnUse"><path d="M22 4l-12 34M61 29l-10 29" stroke="#b0d1dd" opacity=".16" stroke-width="2"/></pattern></defs>
${body}</svg>`;
const woman = (
  x,
  y,
  scale = 1,
  seated = false,
) => `<g transform="translate(${x} ${y}) scale(${scale})">
<path d="M-22 102l-6 ${seated ? 30 : 102}h17l17-${seated ? 30 : 99}M8 105l8 ${seated ? 29 : 99}h18l-7-${seated ? 33 : 104}" fill="#17262e"/>
<path d="M-35 38q32-15 65 0l17 84h-88z" fill="#718b98"/>
<path d="M-34 39l-15 76 13 3 20-70M27 41l17 71-12 4-22-68" fill="#5f7f90"/>
<ellipse cy="9" rx="24" ry="31" fill="#e2b6a0"/><path d="M-26 12q-11-45 22-45 36 3 28 48l-11-32-19 8-13 7z" fill="#18212b"/>
<path d="M-10 12h4M9 12h4" stroke="#2d303a" stroke-width="3" stroke-linecap="round"/><path d="M-4 25q5 3 10-1" fill="none" stroke="#a57770" stroke-width="2"/>
<path d="M-15 39l13 15 16-15M-2 54v65" fill="none" stroke="#a3b7bd" stroke-width="2"/></g>`;
const keeper = (
  x,
  y,
  scale = 1,
  seated = false,
) => `<g transform="translate(${x} ${y}) scale(${scale})">
<path d="M-28 117l-5 ${seated ? 29 : 88}h18l15-${seated ? 29 : 84}M8 115l10 ${seated ? 31 : 90}h19l-4-${seated ? 35 : 92}" fill="#222b30"/>
<path d="M-40 42q38-17 73 2l12 82h-91z" fill="#766357"/><path d="M-38 43l-11 65 15 4 13-62M29 44l22 64-12 6-24-59" fill="#66564f"/>
<ellipse cy="12" rx="26" ry="32" fill="#cba78f"/><path d="M-26 5q-10-33 24-36 35 2 29 38L15-14-16-12z" fill="#a8adb0"/>
<path d="M-13 12h5M10 12h5M-8 29q8 5 15-1" fill="none" stroke="#665854" stroke-width="2" stroke-linecap="round"/>
<path d="M-17 42l16 20 20-19M-1 62v60" fill="none" stroke="#a58b74" stroke-width="3"/></g>`;
const lantern = (
  x,
  y,
  scale = 1,
) => `<g transform="translate(${x} ${y}) scale(${scale})"><circle cy="-10" r="110" fill="url(#lamp)"/>
<path d="M-18-31q0-38 36 0M-18-30h36l-5 59h-27z" stroke="#584837" stroke-width="5" fill="#efc16f"/>
<path d="M-27 31h54M-22-30h44" stroke="#766044" stroke-width="7"/><path d="M0-20v41" stroke="#ffe5a6" stroke-width="8"/></g>`;
const ticket = (
  x,
  y,
  scale = 1,
) => `<g transform="translate(${x} ${y}) scale(${scale})"><rect x="-160" y="-64" width="322" height="126" rx="8" fill="#dfcca7"/>
<path d="M63-63v126" stroke="#ad9572" stroke-dasharray="6 5" stroke-width="3"/><text x="-135" y="-22" font-family="sans-serif" font-size="23" fill="#756246">青岚 → 回家</text>
<text x="-135" y="18" font-family="sans-serif" font-size="15" fill="#917c60">十二年前 · 最后一班</text><text x="85" y="12" font-size="20" fill="#756246">归</text></g>`;
const station = (
  background = true,
) => `<rect width="1280" height="720" fill="url(#sky)"/>
<path d="M0 440q180-120 340-48t350-60 330 55 260-52v385H0z" fill="#213d4b"/>
<rect y="465" width="1280" height="255" fill="url(#ground)"/>
<path d="M0 629l1280-48M0 665l1280-55M0 702l1280-58" stroke="#83919a" opacity=".4" stroke-width="4"/>
<path d="M0 470h1280" stroke="#9e9681" stroke-width="8"/>
<rect x="86" y="197" width="366" height="268" fill="#536775"/><path d="M44 204l422-40 39 48H44z" fill="#1e3440"/>
<rect x="119" y="262" width="123" height="139" fill="#d6ab6c"/><path d="M180 261v141M119 337h123" stroke="#485263" stroke-width="7"/>
<rect x="287" y="268" width="109" height="197" fill="#273e4b"/><rect x="310" y="292" width="61" height="111" fill="#ba9461"/>
<rect x="153" y="220" width="160" height="36" rx="3" fill="#d6ccaf"/><text x="233" y="247" fill="#34495c" font-size="22" text-anchor="middle" font-family="sans-serif">青岚站</text>
<path d="M776 412v54M1088 412v54" stroke="#756754" stroke-width="10"/><rect x="746" y="391" width="363" height="32" rx="3" fill="#8e795e"/>
<path d="M761 373h333M761 352h333" stroke="#8a765e" stroke-width="15"/>
${background ? '<rect width="1280" height="720" fill="url(#rain)"/>' : ""}`;
const caption = (
  number,
  title,
  dialogue,
) => `<rect x="0" y="625" width="1280" height="95" fill="#111d2c" fill-opacity=".85"/>
<text x="44" y="657" fill="#acc2d0" font-size="18" font-family="sans-serif">末班灯火 · ${number} / 4 · ${escape(title)}</text>
<text x="640" y="695" fill="#f2e4c8" font-size="25" text-anchor="middle" font-family="sans-serif">${escape(dialogue)}</text>`;
const scenes = [
  station(false) +
    woman(613, 334, 1.05) +
    lantern(339, 381, 0.7) +
    '<rect width="1280" height="720" fill="url(#rain)"/>' +
    caption(1, "雨夜的站台", "青岚站停运前的最后一晚，灯还亮着。"),
  station(false) +
    woman(676, 271, 1.42) +
    keeper(943, 282, 1.4) +
    lantern(802, 432, 1.05) +
    '<path d="M720 380l82-12 8 45-80 15z" fill="#d9c8a5"/><rect width="1280" height="720" fill="url(#rain)"/>' +
    caption(2, "提灯递信", "林晚：这张票，晚了十二年。"),
  '<rect width="1280" height="720" fill="#273d48"/><circle cx="680" cy="360" r="380" fill="url(#lamp)"/><path d="M213 470l555-220 195 220-621 88z" fill="#d9c9a9"/><path d="M213 470l378-25 177-195" fill="none" stroke="#b5a082" stroke-width="6"/>' +
    ticket(658, 379, 1.6) +
    lantern(1062, 448, 1.5) +
    caption(3, "迟到的车票", "陈叔：灯亮着，就不算晚。"),
  station(false) +
    woman(849, 299, 0.86, true) +
    keeper(997, 301, 0.84, true) +
    lantern(745, 454, 0.67) +
    '<circle cx="1213" cy="435" r="54" fill="url(#lamp)"/><circle cx="1213" cy="435" r="7" fill="#f2d398"/><rect width="1280" height="720" fill="url(#rain)"/>' +
    caption(4, "一起等最后一班", "林晚：我替他，陪您等最后一班。"),
];
const illustrations = {
  "lin-wan.svg":
    '<rect width="1280" height="720" fill="#2e4558"/><circle cx="640" cy="330" r="230" fill="#3a5769"/>' +
    woman(640, 212, 1.9) +
    '<text x="640" y="665" text-anchor="middle" fill="#d4e0e5" font-family="sans-serif" font-size="24">林晚 · 短黑发 / 蓝灰雨衣</text>',
  "chen-shu.svg":
    '<rect width="1280" height="720" fill="#3c3f41"/><circle cx="640" cy="330" r="230" fill="#555451"/>' +
    keeper(640, 212, 1.85) +
    '<text x="640" y="665" text-anchor="middle" fill="#e4d8c7" font-family="sans-serif" font-size="24">陈叔 · 灰短发 / 深褐外套</text>',
  "station.svg": station() + lantern(920, 409, 0.8),
  "ticket.svg":
    '<rect width="1280" height="720" fill="#3a4247"/><path d="M314 470l438-262 216 299-572 73z" fill="#b8a98e"/>' +
    ticket(648, 353, 1.9),
  ...Object.fromEntries(
    scenes.map((scene, index) => [`shot-${index + 1}.svg`, scene]),
  ),
};
for (const [filename, body] of Object.entries(illustrations))
  await writeFile(path.join(output, filename), svg(body));

const browser = await chromium.launch({ channel: "msedge", headless: true });
try {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1,
  });
  for (let index = 0; index < scenes.length; index++) {
    const frame = path.join(temporary, `frame-${index + 1}.png`);
    await page.setContent(
      `<style>html,body{margin:0;overflow:hidden}</style>${svg(scenes[index])}`,
    );
    await page.screenshot({ path: frame });
    const clip = path.join(output, `shot-${index + 1}.mp4`);
    const result = spawnSync(
      ffmpeg,
      [
        "-y",
        "-i",
        frame,
        "-vf",
        "zoompan=z='min(zoom+0.0006,1.06)':x='iw/2-iw/(zoom*2)':y='ih/2-ih/(zoom*2)':d=120:s=960x540:fps=24",
        "-frames:v",
        "120",
        "-c:v",
        "libx264",
        "-crf",
        "24",
        "-pix_fmt",
        "yuv420p",
        "-an",
        "-movflags",
        "+faststart",
        clip,
      ],
      { windowsHide: true, encoding: "utf8" },
    );
    assert.equal(result.status, 0, result.error?.message ?? result.stderr);
  }
} finally {
  await browser.close();
}
const concat = path.join(temporary, "clips.txt");
await writeFile(
  concat,
  scenes
    .map(
      (_, index) =>
        `file '${path.join(output, `shot-${index + 1}.mp4`).replaceAll("\\", "/")}'`,
    )
    .join("\n"),
);
const result = spawnSync(
  ffmpeg,
  [
    "-y",
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    concat,
    "-c",
    "copy",
    "-movflags",
    "+faststart",
    path.join(output, "episode.mp4"),
  ],
  { windowsHide: true, encoding: "utf8" },
);
assert.equal(result.status, 0, result.error?.message ?? result.stderr);
console.log(
  "Built 8 original SVG illustrations, four 5-second silent clips, and a 20-second episode; no AI API called.",
);

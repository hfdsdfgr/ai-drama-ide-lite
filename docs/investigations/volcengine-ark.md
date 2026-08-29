# 火山方舟（Volcengine Ark）Provider 调研

> 调研日期：2026-08-29
> 目的：为 AI Drama IDE Lite 接入面向国内的火山方舟（豆包 / Seedream / Seedance）Provider。
> 来源：火山方舟官方文档（www.volcengine.com/docs/82379）、API Explorer、官方 veadk 配置、社区成熟实现（seedance-studio、doubao-seedream 相关 MCP）交叉验证。

## 1. 基本信息

- 服务商：火山引擎方舟（Volcengine Ark），面向国内。
- Base URL：`https://ark.cn-beijing.volces.com/api/v3`（北京地域；上海等地另有地域域名）。
- 鉴权：`Authorization: Bearer <ARK_API_KEY>`，API Key 在方舟控制台获取。
- 模型调用方式：既支持官方 Model ID（如 `doubao-seed-1-6-250615`），也支持用户创建的推理接入点 Endpoint ID（`ep-xxxxx`）。
- 模型列表：方舟 **没有公开的 OpenAI 兼容 `/models` 拉取接口**，模型清单在控制台 / 官方文档维护。
  因此本项目将 volcengine 预设的 `discoverable` 设为 `False`，走「内置模型目录 + 手动填模型 ID」。

## 2. 文本模型（豆包 LLM）

- 接口：`POST {base}/chat/completions`，**OpenAI 兼容**，可直接复用 `OpenAICompatAdapter.chat / chat_stream`。
- 请求体：`model`、`messages`、`temperature` 等与 OpenAI 一致。
- 已确认的 Model ID：
  - `doubao-seed-1-6-250615`
  - `doubao-seed-2-0-pro-260215`
  - `doubao-seed-2-0-lite-260215`
- 备注：部分豆包模型支持视觉（多模态），但能力声明保守处理，默认不标 `vision`，用户可手动开启。

## 3. 图像模型（Seedream）

- 接口：`POST {base}/images/generations`，响应为 OpenAI 兼容结构 `{"data": [{"url" | "b64_json"}]}`。
- 请求参数：
  - `model`：Model ID 或 Endpoint ID。
  - `prompt`：提示词。
  - `size`：两种方式二选一
    - 档位：`1K / 2K / 3K / 4K`（模型不同支持不同档位）；
    - 宽高像素：`宽x高`，默认 `2048x2048`，总像素范围 `[3686400, 16777216]`，宽高比范围 `[1/16, 16]`。
  - `response_format`：`url`（默认）/ `b64_json`。
  - `watermark`：是否带“AI 生成”水印，默认 false。
  - `output_format`：`png / jpeg`（仅 5.0 系列支持自定义）。
  - `seed`、`guidance_scale`、`sequential_image_generation` 等可选。
- **关键约束**：Seedream 最低总像素 3686400，即 `1024x1024` 这类小尺寸会报错；
  本项目 Adapter 必须把常见宽高比映射到合法像素值（见下表），不能直接透传 `1024x1024`。

| 宽高比 | size 像素值 | 总像素 |
| --- | --- | --- |
| 1:1 | 2048x2048 | 4194304 |
| 2:3 | 2048x3072 | 6291456 |
| 3:4 | 2304x3072 | 7077888 |
| 4:3 | 3072x2304 | 7077888 |
| 16:9 | 2560x1440 | 3686400 |
| 9:16 | 1440x2560 | 3686400 |

- 已确认的 Model ID：`doubao-seedream-4-0-250828`、`doubao-seedream-5-0-260128`。
- 图生图 / 编辑：Seedream 4.0 支持图片编辑，但方舟官方请求中参考图字段的准确格式（`image` / `image_urls` 等）在本次调研中未获得官方明确文档，
  第三方聚合平台参数各异。**第一版不声明 `image_to_image` / `reference_image` 能力**，待真实 Key 实测确认后再补，避免猜接口。

## 4. 视频模型（Seedance，原生异步）

### 4.1 创建任务

- 接口：`POST {base}/contents/generations/tasks`
- 请求体：

```json
{
  "model": "doubao-seedance-2-0-260128",
  "content": [
    { "type": "text", "text": "小猫对着镜头打哈欠" },
    { "type": "image_url", "image_url": { "url": "https://... 或 data:image/png;base64,..." }, "role": "first_frame" }
  ],
  "resolution": "720p",
  "ratio": "16:9",
  "duration": 5,
  "generate_audio": false,
  "watermark": false
}
```

- `content` 支持文本 / 图片 / 音频 / 视频 / 样片任务 ID 的组合。
- 图片 URL 支持三种形式：公网 URL、**Base64 data URL**（`data:image/png;base64,...`，单图 <30MB、请求体 <64MB）、素材 ID（`asset://...`）。
  因此本地图片可直接转 data URL 上传，无需图床。
- 图生视频-首帧：1 张图片，`role` 为 `first_frame` 或省略。
- 图生视频-首尾帧：2 张图片，`role` 分别为 `first_frame` / `last_frame`。
- 多模态参考生视频（仅 2.0 系列）：1~9 张参考图，`role` 为 `reference_image`。
- 参数说明：
  - `resolution`：`480p / 720p / 1080p`（720p 全模型支持；2.0 fast 不支持 1080p）。
  - `ratio`：`16:9 / 4:3 / 1:1 / 3:4 / 9:16 / 21:9 / adaptive`；本项目把不支持的比值（如 2:3）映射为 `adaptive`。
  - `duration`：整数秒；1.0 系列 [2,12]，1.5 pro [4,12]，2.0 系列 [4,15]；本项目默认 5，透传用户值。
  - `generate_audio`：**默认 true**（仅 2.0/2.0 fast/1.5 pro 支持）。
    ⚠️ 本项目产品决定「视频默认无声」，因此 Adapter 必须显式传 `false`，仅当用户勾选带音频时才传 `true`。
  - `watermark`：默认 false。
  - `camera_fixed`、`seed`、`callback_url`、`return_last_frame`、`execution_expires_after`、`draft`、`service_tier` 可选。
- 响应：`{"id": "<task_id>"}`，任务仅保留 7 天。

### 4.2 查询任务

- 接口：`GET {base}/contents/generations/tasks/{id}`
- 状态枚举：`queued / running / cancelled / succeeded / failed / expired`。
- 成功响应关键字段：`content.video_url`（mp4，**24 小时有效**，需及时转存）、`content.last_frame_url`（需创建时 `return_last_frame=true`）、`duration`、`resolution`、`ratio`、`generate_audio`。
- 失败响应：`error.code` + `error.message`。

### 4.3 已确认的 Model ID 与能力

| Model ID | 能力 |
| --- | --- |
| `doubao-seedance-2-0-260128` | text_to_video / image_to_video / video_audio / video_dialogue |
| `doubao-seedance-2-0-fast-260128` | text_to_video / image_to_video / video_audio / video_dialogue |
| `doubao-seedance-2-5-260628` | text_to_video / image_to_video / video_audio / video_dialogue |
| `doubao-seedance-1-5-pro-251215` | text_to_video / image_to_video / video_audio / video_dialogue |
| `doubao-seedance-1-0-lite-t2v` | text_to_video |
| `doubao-seedance-1-0-lite-i2v` | image_to_video |

- 说明：`video_dialogue` 表示模型原生支持对白 / 台词（提示词中对话置于双引号内效果最佳）；`video_audio` 表示模型可生成与画面同步的声音（人声 / 音效 / BGM）。
- Seedance 2.0 系列支持对话优化与口型同步；1.5 pro 的 `generate_audio=true` 同样生成人声 + 音效 + BGM。

## 5. 本项目接入设计

1. `vendor_presets.py`：新增 `volcengine` 预设，`protocol="volcengine"`，`discoverable=False`。
2. `vendor_models.json`：新增 `volcengine` 段（上文确认的 Model ID 与能力）。
3. `capability_registry.py`：`seedream` 图像规则、`seedance` 视频规则补 `video_dialogue`。
4. `adapters/volcengine.py`：继承 `OpenAICompatAdapter`，复用 chat / 文生图；实现 Seedance 异步 `submit / poll / fetch_result`。
5. 文生图：覆写尺寸映射（上表），显式 `watermark=false`、`response_format=url`。
6. 视频：`generate_audio` 默认显式 `false`（产品要求无声），`with_audio=true` 时才为 `true`。

## 6. 不在本阶段范围

- 火山「语音技术」产品线（TTS / ASR，`openspeech.bytedance.com`）与方舟 Chat API 是不同端点、需要单独开通，第一版不接入音频。
- Seedream 图生图 / 参考图：等待真实 Key 实测确认官方参数格式后再补。
- 上海 / 其它地域域名：当前按北京 `cn-beijing` 预设，用户可在 Base URL 中自行修改。
- 火山引擎对象存储（TOS）产物转存：后续按需接入。

## 7. 参考资料

- 火山方舟模型列表：https://www.volcengine.com/docs/82379/1330310
- 视频生成任务 API（创建 / 查询）：https://www.volcengine.com/docs/82379/1521309
- API Explorer：CreateContentsGenerationsTasks / ImageGenerations
- seedance-studio（社区文档）：https://github.com/sihuangtech/seedance-studio
- 官方 veadk-python config.yaml（Model ID 交叉验证）：https://github.com/volcengine/veadk-python/blob/main/config.yaml.full

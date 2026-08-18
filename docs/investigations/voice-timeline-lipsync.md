# 调研：Voice Generation / Timeline / Lip Sync 分离方案

> 调研时间：2026-08-18。
> 结论先写在这里，后续实现以本文档为准，不直接复制任何开源实现。

## 1. 产品要求

三个概念必须严格分离：

1. Voice Generation：只负责生成音频 + 可用的 alignment 数据。
2. Timeline / Alignment：只负责把音频、台词、Shot 映射到真实时间轴。
3. Lip Sync：只负责让画面嘴型匹配已经确定好的音频，不参与生成音频或估算时长。

正确流程：

```text
Script
→ Dialogue Clips
→ TTS
→ Final Audio Asset
→ Provider Alignment 或 Forced Alignment
→ 准确的 Dialogue Timeline
→ Storyboard / Shot Timeline
→ Video Generation
→ Video + Final Audio
→ Lip Sync
→ Final Video
```

禁止：

- 用 LLM 估算台词持续时间。
- 用字符数量估算语音时长。
- 用“每句话 3 秒”等固定规则。

时间轴优先级：

1. TTS Provider 返回的真实 timestamps / alignment。
2. Provider 不提供时，对最终音频执行 Forced Alignment。
3. 两者都不可用时，只能使用音频真实 duration，不能伪造字符级时间戳。

## 2. 调研对象

### 2.1 ElevenLabs：TTS with Timestamps

官方端点：

`POST /v1/text-to-speech/{voice_id}/with-timestamps`

输入：

- `text`
- `model_id`
- `voice_id`
- 可选的 `voice_settings`
- 可选 `previous_text` / `next_text` / `previous_request_ids` / `next_request_ids`

输出：

- `audio_base64`
- `alignment`
  - 原始文本中每个字符的时间信息
  - `characters` + `character_start_times_seconds` 等字段
- `normalized_alignment`
  - 归一化后文本的字符级时间信息

特点：

- 同步请求，非异步任务。
- 提供字符级时间戳；不提供独立的 speaker / 多角色时间轴（多角色需要按句分别生成）。
- 错误主要是 HTTP 4xx / 5xx，422 表示请求体不合法。
- 商业 API，按用量计费。

来源：

- https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps

### 2.2 ElevenLabs：Forced Alignment

官方端点：

`POST /v1/forced-alignment`

输入：

- 音频文件（multipart form）
- 需要对齐的 `text`

输出：

- `characters`：字符级时间信息
- `words`：词级时间信息
- `loss`：整条 transcript 的平均对齐 loss / confidence

特点：

- 支持 29 种语言，包括中文。
- 当前不支持 diarization，多角色文本必须按单角色分句后再对齐。
- 文件上限与时长上限都很大，适合对最终音频做整段对齐。
- 同步接口；错误以 HTTP 4xx / 5xx 返回。

来源：

- https://elevenlabs.io/docs/api-reference/forced-alignment/create
- https://elevenlabs.io/docs/overview/capabilities/forced-alignment

### 2.3 Wav2Lip

输入：

- 已有视频（需要有人脸）
- 任意音频（wav / mp3 / 视频音轨均可）

输出：

- 嘴部区域被替换后的同步视频

特点：

- 零样本，不需要逐人训练。
- 同步精度高，但嘴部区域偏糊，HD 上更明显。
- 对侧脸、遮挡、多人物同框、低分辨率效果下降。
- 需要 `--pads` 调整人脸 bbox，尤其要包含下巴。
- 开源模型仅限个人 / 研究 / 非商业用途；官方 README 明确禁止商业使用。
- 商业版由 Sync Labs 提供。

来源：

- https://github.com/Rudrabha/Wav2Lip

### 2.4 LatentSync

输入：

- 已有视频
- 已准备好的音频

输出：

- 嘴部区域重新生成后的视频

特点：

- ByteDance 开源，Apache 2.0，可商用。
- 1.5 推理约 8GB VRAM；1.6 约 18GB VRAM。
- 1.6 输出人脸区域 512px；合成回原视频。
- 对正面镜头效果好；侧脸、遮挡、多角色、弱光会下降。
- 只做 lip sync，不包含 TTS / 翻译 / 音色克隆。
- 项目自 2025 年中后基本停止活跃更新。

来源：

- https://github.com/bytedance/LatentSync

### 2.5 MuseTalk

输入：

- 已有视频
- 音频

输出：

- 同步后的视频

特点：

- 腾讯音乐 Lyra Lab 开源。
- 比扩散类模型快，支持接近实时推理。
- 画质和同步质量介于 Wav2Lip 与 LatentSync 之间。
- 文档和社区比 Wav2Lip 新但成熟度略低。

### 2.6 SadTalker

输入：

- 单张照片
- 音频

输出：

- 会说话的人像视频（包含头部运动）

特点：

- Apache 2.0。
- 适合从静态图生成 talking head，不适用于修改已有视频的嘴型。
- 唇形精度不如 Wav2Lip / LatentSync。

### 2.7 VideoReTalking

输入：

- 已有视频
- 新音频

输出：

- 只修改嘴部区域后的视频

特点：

- 多阶段管线，保留原视频画质较好。
- 对侧脸 / 部分遮挡处理相对好。
- 处理慢，阶段之间可能有不一致。

### 2.8 Sync.so（Wav2Lip 团队商业 API）

输入：

- 已有视频，或单张照片
- 音频

输出：

- 同步后的完整视频

特点：

- 异步任务：create → poll / webhook。
- 官方支持 `lipsync-2`、`sync-3` 等模型。
- 输出质量明显高于开源 Wav2Lip，最高支持 4K / 60fps。
- 对侧脸、多人物、遮挡、特写更强。
- 错误处理：SDK 提供 `ApiError`，含 status code 与 body。
- 商业付费 API。

来源：

- https://github.com/Rudrabha/Wav2Lip
- https://sync.so/blog/what-is-latentsync/

### 2.9 Hedra API

输入：

- 人像 / 角色图
- 音频，或文本 + voice

输出：

- 会说话的角色视频

特点：

- 异步任务，支持 polling 与 webhook。
- GraphQL / REST 均可调用。
- 按 credits 计费，有 rate limit。
- 错误返回标准 HTTP 状态码，含 `INSUFFICIENT_CREDITS` 等业务码。
- 更适合“角色头像说话”，不完全等价于“已有视频 + 新音频”的嘴型替换。

来源：

- https://doitong.ru/en-US/developers/api/hedra

### 2.10 Forced Alignment 开源备选

- WhisperX：基于 Whisper 的 ASR + forced alignment，输出词级时间戳；对长音频可用。
- Montreal Forced Aligner（MFA）：基于 Kaldi，输出 word 与 phoneme 级对齐，需要发音词典。
- 注意：WhisperX 词级时间戳历史上出现过回归 bug，落地前要验证版本。

来源：

- https://github.com/m-bain/whisperX
- https://montreal-forced-aligner.readthedocs.io

## 3. 对比表

| 方案 | 输入 | 输出 | 时间戳 | 视频裁剪 / 人脸区域 | 多角色 | 异步 | 错误处理 | License / 商用 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ElevenLabs TTS Timestamps | text + voice + model | audio + char alignment | 字符级 | 无 | 按句拆分 | 同步 | HTTP 错误 | 商业 API |
| ElevenLabs Forced Alignment | audio + text | char / word alignment + loss | 字符 / 词级 | 无 | 不支持 diarization | 同步 | HTTP 错误 | 商业 API |
| Wav2Lip | video + audio | video | 不输出 | 人脸 bbox 裁剪 | 弱 | 本地推理 | 本地脚本 | 开源非商用 / 商业需 Sync |
| LatentSync | video + audio | video | 不输出 | 人脸区域 256/512 | 弱 | 本地推理 | 本地脚本 | Apache 2.0 可商用 |
| MuseTalk | video + audio | video | 不输出 | 人脸区域 | 弱 | 本地推理 | 本地脚本 | 开源（需确认具体 License） |
| SadTalker | photo + audio | video | 不输出 | 不适用 | 单角色 | 本地推理 | 本地脚本 | Apache 2.0 |
| VideoReTalking | video + audio | video | 不输出 | 人脸区域 | 中 | 本地推理 | 本地脚本 | 开源（需确认具体 License） |
| Sync.so | video / photo + audio | video | 不输出 | 全画面 | 强 | 异步 polling | 结构化错误 | 商业 API |
| Hedra | image + audio | video | 不输出 | 全画面角色 | 单角色为主 | 异步 + webhook | HTTP + 业务码 | 商业 API |

## 4. 推荐架构

### 4.1 Voice Generation Adapter

扩展现有 Adapter 接口：

```text
GenerationRequest
→ VoiceGenerationAdapter
→ GenerationResult + AlignmentResult
```

`AlignmentResult` 可选字段：

- `characters`
- `character_start_times_seconds`
- `character_end_times_seconds`
- `words`
- `word_start_times_seconds`
- `word_end_times_seconds`
- `phonemes`（预留，本期不实现）
- `source`：`provider` / `forced_alignment` / `audio_duration_only`
- `confidence` / `loss`

### 4.2 DialogueClip 数据结构

必须支持：

```text
DialogueClip
├── startTime
├── endTime
├── audioAssetId
├── alignment
├── speakerId
├── voiceProfileId
├── shotId
└── version
```

必须支持一句台词跨多个 Shot：

```text
shotId: shot_01, startTime: 0.0,  endTime: 1.8
shotId: shot_02, startTime: 1.8, endTime: 3.5
```

同一 `DialogueClip` 可以拥有多个 `(shotId, startTime, endTime)` 片段，而不是一句台词只能绑定一个 Shot。

### 4.3 Timeline 来源

优先级：

1. TTS Provider timestamps：TTS 时直接返回 alignment。
2. Forced Alignment：对最终拼接后的音频执行对齐，得到字符 / 词级时间轴。
3. Audio Duration：只记录 `audioAssetId + duration`，不生成任何假字符时间戳。

Shot Timeline 必须来自真实视频：

- 每个 Shot 的 `startTime / endTime` 由成片时间轴确定。
- 不能通过台词时长反推 Shot 时长。

### 4.4 Lip Sync 独立 Job

```text
Input: Video Asset + Final Audio Asset
Job: lip_sync
Output: Synced Video Asset
```

`lip_sync` 不读取台词文本，不调用 TTS，不估算时长；它只消费：

- 视频
- 最终音频
- 可选的脸部 / 角色信息

Lip Sync 后端先做 Adapter：

```text
LipSyncAdapter
├── LatentSyncAdapter（本地，Apache 2.0）
├── SyncSoAdapter（商业 API）
└── 预留：Hedra / VideoReTalking / MuseTalk
```

### 4.5 第一阶段实现范围

- 实现 `character-level` 与 `word-level` alignment 存储。
- `phoneme-level` 只预留字段，不实现。
- 先支持“TTS Provider timestamps”与“Forced Alignment”两条路径。
- 如果 TTS 没有 timestamps，先允许 Final Audio 整体 forced alignment，再切分到 DialogueClip。
- 多角色按句生成，逐句拼接后记录每个 clip 在最终音频中的偏移。
- Lip Sync 使用 LatentSync 1.5（8GB VRAM）或 Sync.so API，根据部署环境选择。

## 5. 结论

- 成熟方案里，时间轴最可靠的是 ElevenLabs TTS timestamps + Forced Alignment。
- 本地免费 Lip Sync 首选 LatentSync（Apache 2.0）；Wav2Lip 仅限非商业。
- 商用 / 高质量首选 Sync.so 或 Hedra 这类托管 API。
- 不要把 TTS、Timeline、Lip Sync 揉进同一个 Service；三者按独立 Job 实现。

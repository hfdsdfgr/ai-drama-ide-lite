# 开发踩坑记录（Pitfalls）

> 所有开发中遇到的坑必须记录到这里，方便后续开发避免重复踩坑。
> 格式：`日期 - 现象 - 根因 - 解决/规避`。

---

## 2026-08-29 视频"只有诡异音效、没有台词"

- **现象**：用 cogvideox-3 生成的分镜视频只有环境音效，没有人声台词。
- **根因**：
  - `video_audio` 能力语义被误用：CogVideoX 只支持"AI 音效"（官方文档 `with_audio` 参数，默认 false），不支持对白/人声；但 vendor_models.json 曾把它标成 `video_audio`，前端据此默认勾选"带声音生成"，并把"对白：xxx"写进提示词，模型只能产出无对白的音效。
- **解决**：
  - 能力体系拆分：`video_audio`（仅原生音效）与 `video_dialogue`（原生对白/人声，音画同步）。只有 Sora 2 / Veo 3.1 / Seedance 2.x 这类确认支持对白的模型才标 `video_dialogue`。
  - 前端默认无声（`withAudio` 默认 false）；选择支持 `video_dialogue` 的模型时才默认开启"带台词生成"；仅音效模型显示"仅音效"开关且默认关闭。
  - 生成服务：只有支持 `video_dialogue` 的模型才把台词写入提示词。
  - 兜底：无论厂商 API 是否支持关闭音频，视频落库前若 `strip_audio=True` 一律用 FFmpeg `-an` 移除音轨，保证"无声交付"。

## 2026-08-29 百炼 ASR（qwen3-asr-flash）台词审核失败

- **现象**：台词审核一直失败"语音转写未返回文本"，或 404。
- **根因**：
  - 百炼 Qwen-ASR 的 OpenAI 兼容接口是 `/chat/completions` + `input_audio`（base64 Data URL），不是 `/audio/transcriptions`（后者 404）。
  - 转写为空（`choices[0].message.content == ""`，`completion_tokens: 0`）是**有效结果**：音频里没有可识别语音（如无声视频/只有环境音）。旧代码把空转写当任务失败，导致审核不可用。
- **解决**：ASR 走原生 `/chat/completions`；空转写视为"未检测到语音"→ 审核标记 flagged（让用户重新生成/删除/沿用），而不是失败；视频完全无音轨同理。

## 2026-08-29 百炼 cogvideox-3 被归类为 llm

- **现象**：`classify_model("bailian", "cogvideox-3")` 返回 `llm`，导致能力刷新时模型类型错误、能力被清空。
- **根因**：百炼 type_rules 缺 `("cogvideox", "video")` 规则，未匹配时默认 `llm`。
- **解决**：`vendor_presets.py` 补上规则；改 vendor_models.json / type_rules 后必须重启后端（启动时 `_backfill_model_capabilities` 会刷新 auto 来源模型）。

## 2026-08-29 智谱视频生成 HTTP 429

- **现象**：cogvideox-3（智谱）提交生成返回 429 "资源配额不足"。
- **根因**：智谱账户资源包/额度不足（历史也出现过限流 429）。是账户问题，不是代码问题。
- **规避**：验证前先确认智谱账户额度；必要时换百炼等其它 provider 的模型验证。

## 经验：能力标注必须以官方文档调研为准

- 不要凭模型名猜测能力；`video_audio` 不等于"能带台词"。模型能力目录（vendor_models.json）是唯一权威来源，未收录的模型交给保守规则推断，不确定的能力不要默认开启。

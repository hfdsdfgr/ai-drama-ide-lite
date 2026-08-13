# 调研：内置模型能力目录（vendor_models.json capabilities 依据）

> 调研时间：2026-08-13。结论已写入 `apps/backend/app/services/vendor_models.json`
> 的 `capabilities` 字段与 `capability_registry.py` 规则。规则 75（Research Before Every Step）。

## 结论摘要

能力数据以厂商公开文档为准，只声明确定支持的能力（宁缺毋滥）；
内置目录（vendor_models.json）优先于名称规则，未收录的模型回落到规则推断。

## 图片模型

| 模型 | 文生图 | 图生图 | 参考图 | 依据 |
| --- | --- | --- | --- | --- |
| gpt-image-1 / 1.5 / 2 | ✓ | ✓ | ✓ | OpenAI 图片编辑端点支持输入图（最多 16 张参考图） |
| dall-e-3 | ✓ | ✕ | ✕ | 编辑端点仅支持 GPT Image 与 dall-e-2 |
| qwen-image-plus / qwen-image-2.0-pro | ✓ | ✓ | ✓ | 百炼图像生成/编辑/多图融合（2.0 支持最多 9 张参考图） |
| wan2.7-image-pro | ✓ | ✓ | ✓ | 文生图/图生图/组图/编辑 |
| wanx2.1-t2i | ✓ | ✕ | ✕ | 万相 2.1 文生图模型（t2i） |
| cogview-4 / cogview-3 系列 | ✓ | ✕ | ✕ | 智谱文生图模型 |
| FLUX.1-schnell | ✓ | ✕ | ✕ | 硅基流动文生图（编辑能力属 FLUX.1 Kontext，另设规则） |
| stable-diffusion-3-5-large | ✓ | ✓ | ✕ | GenerationMode 支持 text-to-image / image-to-image |
| Kwai-Kolors/Kolors | ✓ | ✓ | ✓ | 硅基流动文档：文生图 + 图生图（参考图输入） |

## 视频模型

| 模型 | 文生视频 | 图生视频 | 视频生视频 | 依据 |
| --- | --- | --- | --- | --- |
| sora-2 | ✓ | ✓ | ✓ | Sora 2 支持 T2V / I2V / Remix（改已有视频） |
| wan2.1-t2v / wan2.2-t2v | ✓ | ✕ | ✕ | 百炼文生视频模型（t2v）；I2V 为独立型号未收录 |
| happyhorse-1.1-t2v | ✓ | ✕ | ✕ | 官方模型文档：文生视频 |
| cogvideox / cogvideox-flash | ✓ | ✓ | ✕ | 智谱视频生成支持图生视频 |
| kling / veo / pika（规则） | ✓ | ✓ | ✕ | OpenRouter 主流视频模型均支持图生视频 |

## 参考来源

- OpenAI 图片编辑端点（gpt-image 系列支持输入图）：https://developers.openai.com/api/reference/cli/resources/images/methods/edit
- OpenAI 图片生成指南（编辑/参考图输入 token 说明）：https://developers.openai.com/api/docs/guides/image-generation
- Sora 2（T2V + I2V + Remix）：https://learn.microsoft.com/zh-cn/azure/foundry/openai/concepts/video-generation
- 阿里云百炼 qwen-image-plus（图像生成与编辑）：https://help.aliyun.com/zh/model-studio/qwen-image-plus.md
- 阿里云百炼 CLI 页面（qwen-image-2.0 编辑/多图参考）：https://bailian.console.aliyun.com/cli
- 万相文生图 V2 API（wan2.x / wanx2.x t2i）：https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference
- 万相 wan2.7-image（文生图/图生图/组图/编辑）：https://github.com/fcb01871/aliyun-wanxiang-pricing
- 阿里云百炼 HappyHorse-1.1-T2V（文生视频）：https://help.aliyun.com/zh/model-studio/happyhorse-1-1-t2v.md
- 智谱 CogVideoX（图生视频）：https://www.npmjs.com/package/n8n-nodes-zhipu
- 硅基流动 FLUX.1-schnell（文生图）：https://www.siliconflow.com/zh/models/flux-1-schnell
- 硅基流动图像生成接口 + Kolors 图生图：https://docs.siliconflow.cn/cn/api-reference/images/images-generations
- Stable Diffusion 3.5 Large（text-to-image / image-to-image mode）：https://docs.aws.amazon.com/zh_cn/bedrock/latest/userguide/model-parameters-diffusion-3-5-large.html

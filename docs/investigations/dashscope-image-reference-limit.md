# DashScope 参考图 400：输入图数量限制

## Context

分镜图生成允许用户选择多个参考资产。最近阿里云百炼（国内站）在 `reference_image` 能力下返回 HTTP 400。

## Findings

失败 Job（例如 `job_5543ae5b8efd`）的请求中包含 4 张参考图：

- character 赵明
- character 小福子
- location 赵家村
- location 赵明家

官方文档明确：

- `qwen-image-2.0` 系列图生图/图像编辑支持 1-3 张输入图
- `qwen-image-3.0` 系列图生图/图像编辑支持 1-3 张输入图

当前 `DashScopeAdapter.generate()` 把所有 `request.images` 原样放入
`multimodal-generation/generation` 的 `content`，没有处理 DashScope 的数量上限。

Sources:

- https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference
- https://help.aliyun.com/zh/model-studio/qwen-image-edit-api

## Decision

保持用户可以选择任意数量参考资产，不通过静默丢弃图片来规避 400。

在 `DashScopeAdapter` 内部，当图片类能力收到的参考图数量超过当前模型声明的
`max_reference_images` 时，将多张本地参考图合成一张 PNG contact sheet，再作为单张输入图
传给 DashScope。这样仍是一次 Job、一个模型、一个 Provider，并且不改变前端请求结构。

最大参考图数量不再写死在 Adapter 中：

- `vendor_models.json` 为已知图片模型增加 `max_reference_images` 字段；
- `GenerationService.create_job()` 根据 `provider_preset_key` 和 `model_id`
  解析该字段，并写入 Job 的 `extra.max_reference_images`；
- `DashScopeAdapter.generate()` 仅在 `len(request.images) > max_reference_images`
  时启用 contact sheet 合并；
- 未收录模型按名称片段保守兜底（qwen-image=3、wan2.7-image=9、gpt-image=16）。

依赖使用 Pillow，仅用于读取图片、缩放并拼合成一张图片。该依赖体积可控，且后端已经在
处理媒体资产，属于合理增加。

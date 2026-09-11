# 版本依赖健康检查（2026-09-10）

用户路径：更新资产后，在剧集制作台查看待确认数量和具体版本差异；点击原因打开对应镜头的图片或视频配置；重新选择参考版本并主动生成，新结果保留历史。用户主动固定的版本显示“沿用指定版”，记录不足显示“来源待核实”。查询不创建任务。

依据：
- [Blender dependency graph](https://developer.blender.org/docs/features/core/depsgraph/) 将关系与更新传播分离；本项目复用 ProductionGraph，受影响集合不直接等同于过期。
- [React state structure](https://react.dev/learn/choosing-the-state-structure) 建议避免冗余派生状态；依赖结论在后端按版本实时计算。
- [TanStack Query](https://github.com/TanStack/query/blob/main/docs/reference/QueryClient.md) 提供查询失效机制，但无法替代生产素材版本语义；本次不引入依赖。
- UI 技能检索命中 Contextual Live Badge Updates：只让聚合摘要播报，单元格使用文字与状态色，原因按需展开。

实现顺序：生成请求/来源记录 → ProductionGraph 批量健康检查 → Episode Overview → 工作台与分镜定位 → 回归与截图 → Roadmap。

沿用现有主题 token、表格、原生 details 和分镜侧栏。待确认使用 warning，固定版本和未知来源使用次要文字；不增加面板嵌套。

明确选择意图：请求 pinned_version_ids 只允许包含实际选择的版本。历史版本不会仅因提交瞬间不再是 current 就被自动视为有意固定（避免并发切换误判）。未固定的精确版本跟随当前版本比较；UI 只有用户明确选择历史版本才固定。空参考列表与省略字段分开。

健康状态：none/current/stale/pinned/unknown/broken。按 ID 相等比较，支持当前版本回退；缺记录不按时间猜测。只检查当前结果，视频递归检查实际使用的关键帧。固定关键帧仍暴露其自身依赖问题，避免掩盖已知失效来源。不同原因可同时出现，broken > stale > unknown > pinned > current > none。

风险与验证：跨项目引用、版本删除、文件缺失、旧数据、空选择、回退、固定历史、图片到视频传播、重复边、查询数量和零付费预检；前端校验原因文字、定位和状态优先级；构建/类型/lint/测试与1440/900截图。

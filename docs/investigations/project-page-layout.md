# 调研：主页项目列表布局（ProjectPage 重排依据）

> 调研时间：2026-08-13。规则 75（Research Before Every Step）。

## 背景

上一版主页把「项目列表」和「选中项目后的编辑卡片」上下堆叠，点编辑后卡片出现在页面最底部，
用户需要滚动才能看到，不符合「选中即编辑」的直觉。

## 结论：Master-Detail（主从）双栏布局

管理类界面的标准模式，成熟产品（邮箱、文件管理器、Linear、SAP Fiori、shadcn two-pane shell）高度一致：

1. **左栏 = 固定宽度的项目列表**：点击某项即选中并高亮；列表宽度固定、不随详情滚动，位置稳定。
2. **右栏 = 详情/编辑区**：选中项目后立即显示可编辑详情，用户在同一屏内完成查看与编辑。
3. **新建与导入放在页面顶部工具栏**，不占用列表区；未选中项目时右栏显示新建表单。

## 参考来源

- Two Pane Shell（列表 + 详情）：https://www.shadcn-ui-blocks.com/blocks/application-pro/app-shells/two-pane-shell
- Lightning Design System Layout（master-detail 适用场景 ≥1024px）：https://v1.lightningdesignsystem.com/guidelines/layout/
- SAP Fiori List-Detail pattern（列表区 + 详情区）：https://raw.githubusercontent.com/SAP-docs/sapui5/main/docs/03_Get-Started/step-13-setting-the-list-detail-pattern-cb38637.md
- Wix List and Detail Dashboard Pages：https://dev.wix.com/docs/build-apps/develop-your-app/develop-an-app-with-blocks/dashboard-pages/create-list-and-detail-dashboard-pages
- Linear 风格 task detail panel（列表 + 属性侧栏）：https://github.com/iamnbutler/tasks/issues/219

## 对 ProjectPage 的影响

- 顶部工具栏：新建项目 + 导入项目按钮。
- 左栏：项目列表（名称 + 更新时间），选中高亮，点击即编辑；列表项保留两步确认删除。
- 右栏：未选中显示「新建项目」表单；选中显示「项目详情」（名称 / 描述 / 保存 / 导出 / 删除）。
- 删除「编辑」独立按钮：点击列表项本身就是进入编辑，避免重复入口。

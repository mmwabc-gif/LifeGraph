# LifeGraph v0.0.7 Stable Release

发布日期：2026-08-08

## 定位

v0.0.7 是 LifeGraph 的“统一内容整理与浏览”稳定版。在 v0.0.6 的记忆搜索和标签基础上，将事件、记忆、计划三类内容纳入同一套整理体系，并形成统一内容中心。

## 主要能力

- 事件、记忆、计划共用统一标签；
- 三类内容统一全文搜索、日期范围筛选与标签筛选；
- 三类内容统一参与日/月/年地图标签高亮；
- 内容中心集中浏览、筛选、排序和定位全部内容；
- 内容中心支持单条快速整理标签；
- 支持多选内容批量添加/移除标签；
- 批量操作使用后端整体验证，避免部分写入；
- 内容中心关闭详情后可恢复原整理状态和滚动位置；
- 首页默认视图调整为月视图。

## 数据与迁移

- 数据库 schema：v5；
- 从 schema v4 非破坏性升级；
- 新增统一 `content_tags(kind, content_id, tag_id, created_at)`；
- 旧 `memory_tags` 自动迁移为 `kind='memory'` 的统一关联；
- 原业务密文不需要重写；
- `.lifevault` 格式保持兼容，稳定版生产者版本统一为 `0.0.7`。

## 兼容接口

为避免破坏已有调用，以下记忆专用接口继续保留：

- `GET /api/v1/memories/search`；
- `GET /api/v1/memories/tag-map`；
- 记忆专用标签绑定接口。

新的统一入口包括：

- `GET /api/v1/content/browse`；
- `GET /api/v1/content/search`；
- `GET /api/v1/content/tag-map`；
- `GET|PUT /api/v1/content/{kind}/{content_id}/tags`；
- `POST /api/v1/content/bulk/tags`。

## 当前边界

- 暂不包含照片和附件；
- 暂不包含 EXIF 自动归档和文件目录扫描；
- 暂不包含跨设备实时同步和云端协作；
- 暂不包含 AI 自动整理；
- Markdown 混合编辑继续暂缓。

## 验证

```text
141 passed
JavaScript syntax check passed
Python compile check passed
```

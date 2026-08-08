# 人生图谱 LifeGraph v0.0.7

人生图谱是一个以生命时间为骨架、以本地加密仓库保存事件、记忆与计划的个人数字档案系统。v0.0.7 在 v0.0.6 的记忆搜索与标签基础上，把整理能力扩展到事件、记忆和计划三类内容，并加入统一内容中心、统一搜索、统一标签地图筛选与批量整理。

## v0.0.7 当前能力

### 统一内容中心

- 首页和全页视图提供【内容中心】入口，集中浏览事件、记忆和计划；
- 支持关键词、内容类型、日期范围、标签与排序组合整理；
- 多标签筛选采用“同时包含”的交集逻辑；
- 结果列表在独立区域内滚动，筛选区保持可见；
- 点击正文可打开对应年/月/日详情，关闭右侧抽屉后返回原内容中心，并保留筛选、排序、结果和滚动位置；
- 内容卡片直接显示类型、标题、时间、正文摘要和标签；
- 普通模式可单条【整理标签】，批量模式可多选内容后统一添加或移除标签；
- 批量操作采用后端整体验证后再提交，避免部分成功、部分失败；
- 内容中心经过紧凑布局收口，批量工具栏按需显示，默认浏览界面保持简洁。

### 统一标签

- 事件、记忆、计划共用同一套标签；
- 三类内容在新增、编辑和阅读时均可维护标签；
- 标签管理显示总使用次数，并区分事件、记忆和计划；
- 支持新建、重命名和删除标签；
- 删除标签只解除关联，不删除任何内容；
- 旧 `memory_tags` 会自动迁移到统一 `content_tags`；
- 回收站软删除期间保留标签，恢复后标签仍在；永久删除时清理关联。

### 统一搜索与地图筛选

- 【搜索】支持事件、记忆、计划三类内容；
- 支持标题/正文关键词、类型、开始/结束日期和多标签组合条件；
- 富文本记忆按可见文字检索，不把 HTML 标签当作正文；
- 年度/月度内容按与日期范围是否相交进行匹配；
- 搜索结果可直接打开对应年/月/日详情并定位目标内容；
- 地图标签筛选覆盖事件、记忆、计划；
- 日级内容命中日/月/年，月级内容命中月/年，年级内容命中年；
- 地图保持完整人生结构，只突出命中格并弱化其他格；
- 原 `/memories/search` 和 `/memories/tag-map` 接口继续保留兼容。

### 时间图谱与记录

- 综合首页支持日／月／年三级全范围图谱，v0.0.7 默认进入月视图；
- 支持定位今天、鼠标跟随日期提示、点击日期打开右侧详情抽屉；
- 事件、记忆和计划可挂在整年、整月或具体日期；
- 首页和全页视图提供【记一记】快捷入口；
- 记忆支持 TinyMCE 富文本编辑；
- 长记忆在抽屉阅读时自动折叠，可展开/收起；
- 抽屉支持全屏阅读、上一个/下一个有内容时间范围和键盘快捷切换。

### 内容生命周期

- 事件、记忆、计划支持新增、查看和原地编辑；
- 编辑保留原时间范围与创建时间，并递增 `revision`；
- 删除采用软删除，统一回收站支持恢复、彻底删除和清空；
- revision 乐观并发校验阻止旧页面覆盖新版本；
- 未保存表单关闭、切换、锁定或离开页面前提供保护提示。

### 备份、迁移与安全

- 姓名、出生日期、事件、记忆和计划正文均在本地加密保存；
- 随机 256 位仓库主密钥负责业务密文，PIN 与恢复密钥通过 Argon2id 派生包装密钥；
- 支持修改 PIN、恢复密钥轮换与恢复密钥重置 PIN；
- 支持 `.lifevault` 一致性加密备份、导入演练、正式恢复和失败自动回滚；
- 支持每天/每周自动备份、历史保留、下载、删除、健康检查和再次验证；
- 正式恢复前自动保存当前仓库，恢复成功后撤销全部会话；
- 标签属于整理索引元数据，私人正文仍保持 AEAD 字段加密。

## 数据与迁移

当前数据库 schema：**v5**。

从旧版本升级时会执行非破坏性迁移：

- schema v4 的 `tags` 和 `memory_tags` 保持可读；
- schema v5 新增统一 `content_tags`；
- 旧记忆标签关系自动迁移到 `content_tags(kind='memory', ...)`；
- 原事件、记忆、计划密文不会被重写为明文；
- `.lifevault` 备份格式继续兼容。

## 时间范围模型

```text
年：time_scope = year  / period_key = YYYY
月：time_scope = month / period_key = YYYY-MM
日：time_scope = day   / period_key = YYYY-MM-DD
```

年度内容不会误点亮每一天，月度内容也不会自动写入月内日期；月份和年份状态会按下级内容向上聚合。

## Windows 启动

首次运行双击：

```text
start.bat
```

脚本会创建 `.venv`、安装依赖、启动服务并打开：

```text
http://127.0.0.1:8765
```

环境初始化后，可直接运行：

```text
start_server_only.bat
```

PowerShell 也可以运行：

```powershell
./start.ps1
```

## 手动启动

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -e ".[dev]"
python scripts\run_dev.py
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

v0.0.7 正式收口基线：

```text
141 passed
JavaScript syntax check passed
Python compile check passed
```

## 数据目录

默认运行数据位于：

```text
data/
```

`.gitignore` 已排除数据库、`vault.json`、WAL、SHM、日志、缓存和虚拟环境。正式源码包只保留 `data/.gitkeep`。

可通过环境变量更改数据目录：

```text
LIFEGRAPH_DATA_DIR=D:\LifeGraphData
```

## 主要 API

- 页面：`http://127.0.0.1:8765`
- API 文档：`http://127.0.0.1:8765/api/docs`
- 健康检查：`GET /health`
- 系统状态：`GET /api/v1/system/status`
- 个人档案：`GET /api/v1/profile`、`PUT /api/v1/profile`
- 日期详情：`GET /api/v1/dates/{date}`
- 时间范围详情：`GET /api/v1/periods/{scope}/{period_key}`
- 统一内容浏览：`GET /api/v1/content/browse`
- 统一内容搜索：`GET /api/v1/content/search`
- 统一标签地图：`GET /api/v1/content/tag-map`
- 标签：`GET|POST /api/v1/tags`、`PUT|DELETE /api/v1/tags/{tag_id}`
- 内容标签：`GET|PUT /api/v1/content/{kind}/{content_id}/tags`
- 单标签绑定/解绑：`POST|DELETE /api/v1/content/{kind}/{content_id}/tags/{tag_id}`
- 批量标签整理：`POST /api/v1/content/bulk/tags`
- 兼容记忆搜索：`GET /api/v1/memories/search`
- 兼容记忆标签地图：`GET /api/v1/memories/tag-map`
- 新增内容：`POST /api/v1/events|memories|plans`
- 编辑内容：`PUT /api/v1/events|memories|plans/{content_id}`
- 软删除：`DELETE /api/v1/events|memories|plans/{content_id}`
- 回收站：`GET /api/v1/trash`
- 备份检查：`GET /api/v1/backup/check`
- 导出备份：`GET /api/v1/backup/export`
- 导入演练：`POST /api/v1/backup/import/check`
- 恢复备份：`POST /api/v1/backup/import`
- 自动备份状态与设置：`GET|PUT /api/v1/backup/auto`

## 版本文档

- `docs/ACCEPTANCE_v0.0.7.md`
- `docs/STABLE_RELEASE_v0.0.7.md`
- `docs/GIT_COMMIT_v0.0.7.md`
- `docs/人生图谱_v0.0.7_收口归档.md`
- `docs/NEXT_STEPS.md`
- `docs/LIFEVAULT_FORMAT.md`
- `docs/SECURITY_DESIGN.md`
- `docs/ARCHITECTURE.md`

## 当前边界

v0.0.7 暂不包含照片/附件、EXIF 自动归档、本地文件目录扫描、多设备同步、云端协作及 AI 自动整理。Markdown 混合编辑继续暂缓，后续可作为独立导入/编辑能力处理。

## 下一阶段

v0.0.8 建议进入“附件与人生资料库”：先实现内容/日期附件模型、图片与普通文件挂接、缩略图和基础预览，再逐步评估 EXIF 日期识别与指定目录自动挂接。

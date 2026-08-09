# LifeGraph 当前架构说明（v0.0.10）

```text
本机资料目录
    ↓ 自动增量扫描 / 手动导入
时间识别（EXIF / 媒体 metadata / 文件名 / 文件系统时间）
    ↓
Material / attachments
    ├─ blob-v1 普通附件
    └─ chunked-v1 大型媒体
    ↓
SQLite schema v11
    ├─ 加密业务正文与附件 metadata
    ├─ 可索引 timeline_* 时间事实
    ├─ 年/月/日/小时统计
    └─ 自动扫描源与增量状态
    ↓
FastAPI /api/v1
    ↓
浏览器
    ├─ 人生图谱
    ├─ 年/月/日详情抽屉
    ├─ 资料中心列表
    └─ 年/月/日 + 日内十字时间轴
```

## 核心安全边界

- 事件、记忆、计划正文继续使用仓库主密钥 AES-GCM 加密；
- 附件文件名、原始 EXIF/文档 metadata 等私人元数据继续加密；
- 为支持几十万资料的时间范围查询，规范化后的时间事实 `timeline_at` 等作为结构化索引字段保存；
- 本机自动扫描源绝对路径加密保存；
- 大型媒体按块独立 AES-GCM，Range 播放仅解密命中块；
- 浏览器兼容音轨属于可重建派生缓存。

## 内容模型

业务内容仍为：

```text
events
memories
plans
```

共同使用 `time_scope` 与 `period_key` 表达年/月/日范围，并通过统一标签索引组织。资料 `attachments` 可独立存在，也可以继续挂接到上述业务内容。资料自身时间与父内容时间相互独立。

## 资料时间模型（schema v9+）

`attachments` 维护可查询时间字段：

```text
timeline_at
timeline_end_at
time_precision
time_source
time_confidence
timezone_offset
```

原始识别值如 EXIF 字段仍保存在加密 metadata。旧资料通过显式后台回填任务建立结构化时间索引，启动阶段不做全库解密。

## 时间统计层（schema v10+）

轻量统计表按年/月/日/小时保存资料数量，并通过 SQLite 触发器增量维护。横向时间轴只读取少量统计数据，不加载媒体内容。

单日详情使用范围查询：

```text
timeline_at >= YYYY-MM-DD 00:00:00
timeline_at <  next-day 00:00:00
```

密集日内资料可按分钟、10 分钟或小时聚合。

## 自动扫描层（schema v11）

扫描源管理保存加密绝对路径与启用状态；增量索引保存相对路径哈希、大小、mtime、文件身份和扫描状态。

扫描原则：

1. 未变化文件跳过；
2. 新文件调用现有附件/大型媒体入库能力；
3. 大文件直接从本机路径流式读取并进入 `chunked-v1`；
4. 源文件缺失仅标记，不删除 LifeGraph 副本；
5. 文件变化时先成功导入新版本，再清理该扫描源此前版本。

## 大型媒体层

```text
attachments (SQLite)
    ├─ storage_kind = blob-v1
    │      └─ data/attachments/<shard>/<id>.lgatt
    └─ storage_kind = chunked-v1
           └─ data/media/<shard>/<media-id>/
                 ├─ manifest.lgmedia
                 └─ 00000000.lgchunk ...
```

HTTP Range 根据明文字节范围定位分块，只解密命中块。`data/previews` 保存加密封面，`data/audio_compat` 保存可重建 MP3/AAC 浏览器兼容音轨。

## 右侧详情抽屉

年/月/日抽屉不再调用全库附件解密。数据库先通过 `timeline_at` 索引筛选当前范围，只对当前页资料解密 metadata；默认 12 项/批，可继续加载。

## 备份模型

`.lifevault format v3` 继续作为核心备份：

- SQLite；
- `vault.json`；
- 普通附件；
- 可用视频封面；
- 加密大型媒体 inventory；
- schema v11 时间索引、统计和自动扫描源配置。

原始 `data/media` 继续通过大型媒体独立增量备份保存。扫描源路径在 SQLite 中为加密值，恢复到不同电脑时路径不存在不会阻断恢复。

## 当前边界

当前尚未加入：

- GPS / 地点地图的自动整理；
- 人脸识别与人物关系；
- 全库 OCR / AI 图像理解；
- R2 / NAS 远端媒体增量同步；
- 多设备冲突合并。

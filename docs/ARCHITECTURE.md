# LifeGraph 当前架构说明（v0.0.9）

```text
浏览器页面
    ↓ REST / JSON / multipart
FastAPI /api/v1
    ↓
VaultManager
    ├─ PIN / 恢复密钥解锁
    ├─ 内存主密钥与会话令牌
    ├─ 个人档案与事件 / 记忆 / 计划业务规则
    ├─ 统一内容浏览 / 搜索 / 标签 / 地图筛选
    ├─ 单条与批量标签整理
    ├─ .lifevault 导出 / 演练 / 恢复
    ├─ 自动备份策略、健康状态与历史管理
    ├─ PIN／恢复密钥槽轮换
    ├─ 密钥槽状态与本地安全审计摘要
    └─ Database
          ↓
SQLite（业务正文为 AES-GCM 密文）
```

## 内容模型

三类业务内容继续分别保存在：

```text
events
memories
plans
```

它们共用相同的时间范围语义：

```text
time_scope = year  / month / day
period_key = YYYY / YYYY-MM / YYYY-MM-DD
```

v0.0.7 将标签关联统一为：

```text
tags
  ↓
content_tags
  ├─ kind = event
  ├─ kind = memory
  └─ kind = plan
```

旧 `memory_tags` 只用于迁移兼容，初始化 schema v5 时会把已有记忆标签复制到 `content_tags`。

## 查询与整理层

统一内容能力由后端完成，不由浏览器直接拼接数据库结果：

- `/content/browse`：三类内容统一浏览与排序；
- `/content/search`：关键词、类型、时间范围和多标签组合检索；
- `/content/tag-map`：按标签计算日/月/年三级地图命中；
- `/content/{kind}/{id}/tags`：单条内容标签读取与原子替换；
- `/content/bulk/tags`：多条内容批量添加/移除标签。

记忆专用 `/memories/search`、`/memories/tag-map` 和标签接口继续保留兼容。

## 前端状态模型

内容中心维护独立的浏览状态：

- 关键词、类型、开始/结束日期、标签、排序；
- 当前结果列表；
- 单条标签整理状态；
- 批量整理模式与选择集合；
- 结果区滚动位置。

从内容中心打开右侧详情抽屉时，会暂存上述状态；关闭抽屉后恢复内容中心，而不是回到首页默认状态。

## 本地数据布局

```text
data/
├─ vault.json
├─ lifegraph.db
├─ backups/
│  └─ auto/
│     └─ lifegraph-auto-*.lifevault
└─ recovery/
   └─ lifegraph-before-restore-*.lifevault
```

- `vault.json` 保存 KDF 参数、包装后的主密钥、验证密文、密钥槽更新时间、不含秘密的安全审计摘要和自动备份策略；
- `lifegraph.db` 保存结构字段、统一标签索引与加密档案/内容；
- `backups/auto/` 保存周期自动备份；
- `recovery/` 保存正式恢复前的安全回滚包。

## 为什么所有界面都走 API

- 浏览器不直接读取 SQLite 或密钥包装文件；
- 认证、会话、并发校验、标签一致性、备份和恢复规则集中在后端；
- 数据库实现和加密结构可以升级而不直接暴露给客户端；
- 未来浏览器插件或移动端可以复用同一接口。

## 自动备份触发模型

启用后，普通 API 活动成功完成时，后端检查每天或每周周期是否到期：

1. 未到期时立即跳过；
2. 到期时生成一致性 SQLite 快照；
3. 验证全部加密记录并写入 `.lifevault`；
4. 重新读取落盘文件，验证 ZIP、SHA-256、SQLite、外键和全部密文；
5. 记录最近成功与最近完整验证摘要；
6. 按保留数量删除最旧的自动备份；
7. 失败只记录状态，不回滚已经成功的用户操作。

## 密钥槽与审计模型

PIN 与恢复密钥分别拥有独立盐、AAD 和 Argon2id 包装槽。修改其中一个槽时，只重新包装同一个仓库主密钥，不改动 SQLite 中业务密文。

## 当前边界

当前版本仍未实现：

- 图片与附件；
- EXIF 与本地目录自动挂接；
- 整库 SQLCipher；
- 操作系统安全凭据存储；
- 云端同步和多设备冲突合并；
- 插件设备配对；
- 第三方安全审计。


## v0.0.8 人生资料层

资料使用 `attachments` 作为当前持久化模型，但语义已从“必须依附内容的附件”扩展为可独立存在的 Material：`kind/content_id` 在 schema v7 中可为空。资料拥有独立加密元数据和 `timeline_date`，其内容关系与时间轴关系彼此独立。

附件密文物理保存于 `data/attachments/<UUID前2位>/<UUID>.lgatt`；旧平铺路径保持兼容迁移。`.lifevault` format v2 的包内逻辑路径不随本地物理分片变化。

资料中心采用分页/懒加载：后端分批迭代加密元数据并使用有界内存选择分页结果，前端 48 份/批追加，图片缩略图按可视区域加载。由于私人元数据保持加密，复杂筛选不会建立等价的明文明细索引。


## v0.0.9 大型媒体层

当前资料存储按大小分成两条通道：

```text
Material / attachment index (SQLite schema v8)
    ├─ storage_kind = blob-v1
    │      └─ data/attachments/<shard>/<id>.lgatt
    └─ storage_kind = chunked-v1
           └─ data/media/<shard>/<media-id>/
                 ├─ manifest.lgmedia
                 └─ 00000000.lgchunk ...
```

大型媒体每块独立 AES-GCM 认证，finalize 后用整文件 SHA-256 固定身份。HTTP Range 根据明文字节范围定位块，只解密命中分块。

派生媒体独立保存：`data/previews` 保存小型加密视频封面；`data/audio_compat` 保存浏览器兼容 MP3/AAC，可由原始媒体重建。

`.lifevault v3` 定位为核心备份，仅包含数据库、普通附件、可用封面和加密媒体 inventory；原始 `data/media` 通过独立增量备份镜像。

登录与日常资料浏览只做轻量媒体/备份状态查询，逐块完整性校验仅在用户主动执行维护操作时运行。

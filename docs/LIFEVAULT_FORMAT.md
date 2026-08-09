# LifeGraph `.lifevault` 格式 v3

`.lifevault` 是 LifeGraph 的本地加密**核心仓库备份**。文件本质为 ZIP，但使用独立扩展名，避免与源码压缩包混淆。

v0.0.9.6 起当前写出格式为 **format v3**。导入端继续兼容历史 **v1 / v2**。

## 为什么从 v2 升级到 v3

v0.0.9 引入 GB / 数十 GB 的 `chunked-v1` 大型媒体。如果把所有视频再次塞入一个 `.lifevault`，每次自动备份都会重新复制几十或几百 GB 数据，既慢，也不利于 R2、NAS、外置硬盘做增量同步。

因此 v3 明确分成两层：

- **核心 `.lifevault`**：数据库、密钥包装元数据、普通附件、小型视频封面、加密媒体清单；
- **外部大型媒体库 `data/media/`**：原始大型视频/文件的加密分块，独立镜像备份。

完整备份的语义为：

```text
1 个核心 .lifevault
+
1 份对应的 data/media 镜像
=
可完整恢复的 LifeGraph 仓库
```

`data/audio_compat/` 中的浏览器兼容 MP3/AAC 属于可重新生成派生缓存，不要求备份。

## v3 包结构

```text
manifest.json
repository/
├─ vault.json
├─ lifegraph.db
├─ media-inventory.lgindex
├─ attachments/
│  ├─ <attachment-id>.lgatt
│  └─ ...
└─ previews/
   ├─ <attachment-id>.lgpreview
   └─ ...
```

没有普通附件或视频封面时，对应目录不会产生空目录项。

- `vault.json`：Argon2id 参数、PIN/恢复密钥包装后的主密钥及验证密文；不包含 PIN 或恢复密钥明文。
- `lifegraph.db`：SQLite Backup API 生成的一致性快照；档案、标题、正文、附件元数据和大型媒体索引继续以 AEAD 密文保存。
- `attachments/*.lgatt`：`blob-v1` 普通附件的 AES-GCM 密文。
- `previews/*.lgpreview`：已存在并通过校验的小型视频封面密文。历史备份恢复后若封面文件本身不存在，核心备份仍允许导出，界面会回退到通用视频图标。
- `media-inventory.lgindex`：使用仓库主密钥再次加密的 v3 媒体清单。记录大型媒体 opaque ID、大小、SHA-256、分块规格、备份时在线状态，以及可重建兼容音轨关系；不暴露文件名、时间轴日期或正文。
- `manifest.json`：只保存格式版本、schema、聚合数量/大小、策略和包内文件 SHA-256，不保存私人标题或文件名。

## 大型媒体库

原始大型媒体仍位于：

```text
data/media/
└─ <shard>/
   └─ <media-id>/
      ├─ manifest.lgmedia
      └─ chunks/
         ├─ 00000000.lgchunk
         ├─ 00000001.lgchunk
         └─ ...
```

每个 `lgchunk` 独立 AES-GCM 认证加密。目录可以直接由文件级同步工具增量镜像到 R2、NAS 或外置磁盘，不需要重新打一个巨型压缩包。

`.lifevault v3` **不会**包含 `repository/media/` 或任何 `.lgchunk` 原始大型媒体分块。

## 媒体状态

LifeGraph 会把大型媒体分成：

- `online`：加密 manifest 可验证、与数据库索引一致，并且完整性检查时所有预期 chunk 都存在；
- `offline`：数据库索引存在，但对应 `data/media/<shard>/<media-id>/manifest.lgmedia` 尚未恢复；
- `incomplete`：manifest 存在，但缺少一个或多个分块；
- `invalid`：manifest 无法认证，或大小/SHA/分块规格与数据库索引不一致。

核心 `.lifevault` 可以在媒体离线时继续导出，因为数据库和媒体索引仍是有效的；但此时“完整媒体备份”不是 ready 状态。

## 恢复与自动重新挂接

恢复 v3 核心包时，LifeGraph 替换：

- `vault.json`
- `lifegraph.db`
- `data/attachments/`
- `data/previews/`

**不会删除或覆盖 `data/media/`。**

因此恢复有两种常见方式：

1. 先恢复 `.lifevault`：内容、普通附件、视频封面和大型媒体索引立即回来；缺少原媒体的卡片显示“媒体离线”，播放/下载暂时禁用。
2. 再把匹配的 `data/media/` 镜像复制回原位置：LifeGraph 根据 `media_id + size + SHA-256 + chunk 规格` 自动重新识别为在线，不需要改数据库或重新导入视频。

这也意味着如果目标机器已经提前放好了正确的 `data/media`，恢复核心包后可以直接重新挂接。

## 派生音轨

浏览器兼容音轨位于：

```text
data/audio_compat/
```

它们由原始视频中的 DTS / AC-3 / E-AC-3 / TrueHD 等音轨按需生成 MP3/AAC，仅用于浏览器兼容播放。v3 的策略是：

- 清单记录“曾存在兼容音轨”的关系；
- `.lifevault` 不包含兼容音轨分块；
- `data/audio_compat` 不属于完整备份必需项；
- 缺失时可由原视频 + FFmpeg 再生成。

## 一致性保证

导出 v3 时 LifeGraph 会：

1. 在仓库互斥锁内获取当前主密钥；
2. 使用 SQLite Backup API 从 WAL 仓库创建一致快照；
3. 执行 `PRAGMA quick_check` 与 `PRAGMA foreign_key_check`；
4. 逐条解密验证档案、事件、记忆、计划、附件元数据和回收站记录；
5. 对所有 `blob-v1` 普通附件实际解密，核对明文大小和 SHA-256；
6. 对存在的视频封面实际解密，核对大小和 SHA-256；
7. 验证大型媒体 manifest 与数据库索引；完整性检查模式还会确认所有预期 chunk 文件存在；
8. 生成并加密 `media-inventory.lgindex`；
9. 对包内每个文件计算 SHA-256；
10. 仅在核心仓库检查通过后原子生成 `.lifevault`。

大型媒体本体不会在每次 `.lifevault` 导出时逐 GB 解密重算完整 SHA，因为 finalize 时已经保存并校验整文件 SHA；v3 日常检查以加密 manifest 认证、索引匹配和 chunk 存在性为主。

## v1 / v2 兼容

历史格式仍可导入：

### v1

```text
manifest.json
repository/
├─ vault.json
└─ lifegraph.db
```

### v2

```text
manifest.json
repository/
├─ vault.json
├─ lifegraph.db
└─ attachments/
   └─ *.lgatt
```

v1/v2 没有 v3 媒体清单和嵌入式视频封面。恢复后如果数据库中存在后来版本产生的封面元数据而实际封面文件缺失，LifeGraph 会正常显示无封面状态，不阻止新的 v3 核心备份。

## 自动备份

自动备份仍保存到：

```text
data/backups/auto/
└─ lifegraph-auto-YYYYMMDD-HHMMSS.lifevault
```

从 v0.0.9.6 开始，自动备份同样是 **v3 核心备份**，不会重复复制 `data/media`。因此大型媒体库应使用独立的文件级备份/镜像策略。

推荐长期布局：

```text
LifeGraph 核心备份：data/backups/auto/*.lifevault
大型媒体镜像：    data/media/ -> R2 / NAS / 外置盘
可重建缓存：      data/audio_compat/ -> 不要求备份
```

## 隐私边界

`manifest.json` 不包含姓名、出生日期、事件标题、正文、附件原始文件名、媒体原始路径或 PIN。它会暴露聚合数量、总字节数、schema 版本和包内密文文件大小。

`media-inventory.lgindex` 中的媒体关系本身也是 AEAD 密文。只有持有该备份对应主密钥的人才能读取。

## 手工恢复原则

自动恢复不可用时，应在 LifeGraph **完全停止运行后**操作：

1. 先完整备份现有 `data/`；
2. 解压 `.lifevault`；
3. 恢复 `repository/vault.json` 与 `repository/lifegraph.db`；
4. 恢复 `repository/attachments/*.lgatt` 到 `data/attachments/` 对应分片结构；
5. 恢复 `repository/previews/*.lgpreview` 到 `data/previews/` 对应分片结构；
6. 如果需要完整媒体，再恢复原先备份的 `data/media/`；
7. 启动 LifeGraph 并用该备份对应的 PIN / 恢复密钥解锁；
8. 在“备份与迁移 → 大型媒体库”确认在线/离线数量。

不要在服务运行期间手工覆盖活动数据库、附件或媒体目录。

# 人生图谱 LifeGraph v0.0.9 总体设计

日期：2026-08-09  
基线：v0.0.8 正式稳定版  
阶段主题：大文件与影音资料

## 一、设计目标

v0.0.9 解决的是“单个资料很大”以及“大型媒体库长期增长”的问题，而不是简单提高 v0.0.8 的 50 MB 限制。

核心目标：

1. 支持 GB / 数十 GB 乃至更大的单文件；
2. 上传过程内存占用与文件总大小脱钩；
3. 支持分块上传、失败恢复和断点续传；
4. 每个分块独立认证加密，可单独验证与随机解密；
5. 视频可以按 HTTP Range 只解密播放需要的字节范围；
6. 视频封面、时长、尺寸等进入资料中心；
7. 核心 `.lifevault` 不因大型媒体增长到数百 GB / TB；
8. 保持 v0.0.8 普通附件通道稳定，不用大文件方案替换所有小文件。

## 二、双层资料存储模型

### 1. 普通附件层（保留 v0.0.8）

```text
data/attachments/
└─ <shard>/<attachment-id>.lgatt
```

适用：

- 小图片；
- 文档；
- 普通附件；
- 单文件不超过 50 MB。

特点：

- 单文件一次 AEAD 加密；
- 现有读写逻辑保持不变；
- 默认进入核心 `.lifevault`。

### 2. 大型媒体层（v0.0.9 新增）

```text
data/media/
├─ .incoming/
│  └─ <upload-session-id>/
│     ├─ session.lgup
│     └─ chunks/
│        ├─ 00000000.lgchunk
│        └─ ...
└─ <shard>/<media-id>/
   ├─ manifest.lgmedia
   └─ chunks/
      ├─ 00000000.lgchunk
      ├─ 00000001.lgchunk
      └─ ...
```

特点：

- 独立于 `attachments/`；
- 每块独立 AES-GCM；
- 上传中断后已完成块保留；
- finalize 前处于 `.incoming`；
- finalize 后原子移动到正式媒体库；
- 可按块随机读取，不需要完整解密。

## 三、分块策略

默认使用自适应块大小：

| 文件大小 | 默认块大小 |
|---|---:|
| ≤ 8 GB | 4 MB |
| ≤ 64 GB | 8 MB |
| ≤ 256 GB | 16 MB |
| > 256 GB | 32 MB |

约束：

- 允许块大小：1 MB—32 MB；
- 单文件安全上限：2 TB；
- 单文件最多 65,536 块。

这种设计兼顾：

- 普通视频拖动播放的随机访问粒度；
- 数十 GB 文件的块数量；
- 超大文件目录项数量。

## 四、分块加密格式

每个 `.lgchunk`：

```text
[magic]
[chunk index]
[plaintext size]
[random nonce]
[AES-GCM ciphertext + authentication tag]
```

AAD 绑定：

```text
media_id + chunk_index + plaintext_size
```

结果：

- 块不能被替换到另一个媒体；
- 块不能被调换序号；
- 被篡改后独立验证失败；
- Range 请求只需解密涉及的块。

`session.lgup` 与 `manifest.lgmedia` 本身也使用主密钥加密，不明文保存文件名等资料信息。

## 五、断点续传模型

上传流程：

```text
创建上传会话
    ↓
服务器返回 session_id / media_id / chunk_size / chunk_count
    ↓
浏览器 File.slice() 分块
    ↓
逐块上传
    ↓
每块写入临时目录并原子提交
    ↓
中断后查询 completed_ranges
    ↓
只补传缺失块
    ↓
finalize
    ↓
服务器逐块解密验证并计算整文件 SHA-256
    ↓
写入加密 manifest
    ↓
原子移动到正式 media 目录
```

同一分块重复上传：

- 内容一致：视为幂等重试，直接成功；
- 内容不同：拒绝，防止错误文件覆盖已有进度。

## 六、数据库设计（v0.0.9.2）

建议 schema v8 在附件记录增加明文结构字段：

```text
storage_kind = blob-v1 | chunked-v1
```

原则：

- 人类可读资料元数据仍在现有加密 metadata 中；
- `storage_kind` 只描述物理存储结构，不泄漏私人内容；
- `blob-v1` 使用现有 `file_nonce`；
- `chunked-v1` 的 nonce 位于各自块头中；
- attachment id 与 media id 尽量统一，减少额外映射。

资料中心统一显示两类资料，不要求用户理解底层区别。

## 七、视频元数据与封面

优先采用“浏览器本地提取 + 后端加密保存”：

1. 浏览器使用本地 `File` 创建 Object URL；
2. `<video>` 读取：
   - duration；
   - videoWidth / videoHeight；
3. 跳转到合适时间点；
4. Canvas 抓取一帧生成 JPEG/WebP 封面；
5. 元数据随上传会话提交；
6. 封面作为小型加密派生资料保存。

优点：

- 不需要服务器为了读 metadata 先完整解密几十 GB 视频；
- 不强依赖 FFmpeg；
- Windows 本地部署更简单。

后续可以增加 FFprobe 作为可选增强验证，而不是硬依赖。

## 八、HTTP Range 与视频播放

播放器请求：

```http
Range: bytes=start-end
```

后端：

1. 解析 Range；
2. 计算涉及的首块与末块；
3. 只读取这些 `.lgchunk`；
4. AES-GCM 独立解密；
5. 切出精确请求区间；
6. StreamingResponse 返回 `206 Partial Content`。

响应需要：

```text
Accept-Ranges: bytes
Content-Range: bytes start-end/total
Content-Length: range_length
Content-Type: video/mp4 ...
```

这样视频拖动进度条时不需要完整解密文件。

## 九、`.lifevault` 与大型媒体库的关系

### 核心原则

大型媒体库不应该默认进入日常核心 `.lifevault`。

建议：

```text
核心 .lifevault
├─ vault.json
├─ lifegraph.db
├─ 普通附件
├─ 大型媒体索引 / 引用信息
└─ 媒体完整性清单

大型媒体库 data/media/
├─ 视频
├─ 大型原片
└─ chunked-v1 密文块
```

### v0.0.9 建议升级 `.lifevault` format v3

v3 明确区分：

- `embedded_media`：包内实际携带；
- `external_media`：核心备份只携带索引，不携带大型块。

恢复核心备份后：

- 数据库和资料记录可恢复；
- 未恢复的大型媒体显示“媒体文件离线/待恢复”；
- 将对应 `data/media/` 从 NAS / R2 / 外置硬盘恢复后自动重新识别。

### 大型媒体备份

由于 finalize 后块基本不可变，最适合：

- 文件级增量同步；
- R2；
- NAS；
- 外置硬盘；
- 目录镜像工具。

无需每次重新打一个几百 GB 的 ZIP。

## 十、实施阶段

### v0.0.9.1：大文件基础设施

- chunked-v1 文件格式；
- 独立块认证加密；
- 自适应块大小；
- 持久化上传会话；
- 断点状态；
- 幂等块重传；
- finalize 全文件 SHA；
- 随机 Range 解密底座；
- 单元测试。

### v0.0.9.2：API 与资料库接入

- schema v8；
- 初始化上传 API；
- chunk API；
- status / resume / cancel；
- finalize 后建立 attachment/material 记录；
- 删除联动；
- 资料中心识别 `chunked-v1`。

### v0.0.9.3：前端分块上传

- File.slice()；
- 进度条；
- 暂停 / 继续；
- 网络失败自动重试；
- 页面重开后的断点恢复；
- 批量目录中的大文件分流。

### v0.0.9.4：视频资料

- 视频分类；
- duration / width / height；
- 封面；
- 视频资料卡片；
- 详情预览。

### v0.0.9.5：Range 播放

- 206；
- 单 Range；
- 随机块解密；
- 原生 `<video>` 播放；
- 拖动 / 倍速 / 全屏。

### v0.0.9.6：备份分层

- `.lifevault` v3；
- core / full 备份语义；
- external media inventory；
- 缺失 / 离线状态；
- 媒体库恢复后重新挂接。

### v0.0.9.7：性能与可靠性收口

- 数 GB / 数十 GB 实测；
- 强制中断恢复；
- 浏览器刷新恢复；
- 磁盘空间不足；
- 临时会话清理；
- 块损坏识别；
- 并发上传限制；
- 视频长时间播放稳定性。

## 十一、v0.0.9.1 当前落地状态

已建立：

- `backend/app/services/large_files.py`；
- `ChunkedMediaStore`；
- `LargeUploadManager`；
- encrypted session / manifest；
- chunked-v1 AES-GCM 独立加密；
- resume 状态范围；
- finalize + SHA-256；
- 精确字节范围随机解密；
- `VaultManager` 已预留独立 `data/media/` 大型媒体底座；
- API 暂未开放，避免在 schema / 备份规则完成前让半成品大型资料进入正式资料库。

下一步进入 v0.0.9.2。

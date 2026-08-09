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
- attachment id 继续作为资料记录主键，media id 作为随机的大媒体物理对象标识；两者一对一并通过唯一索引关联，便于以后把“资料记录”和“媒体物理对象”生命周期分开管理。

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
- 资料中心识别 `chunked-v1`；
- `.lifevault v2` 过渡兼容：只嵌入 `blob-v1`，`chunked-v1` 保留数据库索引并标记为 external media。

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


## 十二、v0.0.9.2 当前落地状态

已完成：

- schema v8：`attachments.storage_kind`、`attachments.media_id`，并允许 `chunked-v1` 不使用单文件 `file_nonce`；
- v6 → v7 → v8 与 v7 → v8 自动迁移，旧附件统一回填为 `blob-v1`；
- `POST /api/v1/materials/large/uploads` 创建持久化上传会话；
- `GET /api/v1/materials/large/uploads/{session_id}` 查询断点状态；
- `PUT /api/v1/materials/large/uploads/{session_id}/chunks/{index}` 上传单块，服务器端限制单请求最多 32 MB；
- `DELETE /api/v1/materials/large/uploads/{session_id}` 取消未完成会话；
- `POST /api/v1/materials/large/uploads/{session_id}/finalize` 完成逐块验证、整文件 SHA-256、原子提交并建立资料记录；
- 资料记录公开 `storage_kind` / `media_id` / `is_large`，资料中心后端新增 `video` 分类；
- 删除大型独立资料时同步删除 `data/media/<shard>/<media-id>/`；
- 历史附件时间元数据补齐逻辑会跳过大型媒体完整解密；
- 核心 `.lifevault v2` 在过渡期只打包 `blob-v1` 小附件，对 `chunked-v1` 只保留数据库索引，并在 manifest 中记录 `external_media_policy=chunked-v1-index-only`；
- 备份完整性检查、导出、导入预检均可识别 external media，不会因为大型媒体未嵌入包内而误报附件缺失；
- 新增大文件 API 专项测试，并完成现有测试回归。

此阶段尚未做浏览器 `File.slice()` 上传 UI；因此 v0.0.9.2 是“后端可调用”的完整闭环。下一步 v0.0.9.3 将把现有资料中心上传入口切换为自动分流：小文件继续原通道，大文件进入 resumable chunked-v1 通道。

## 十三、v0.0.9.3 当前落地状态

已完成资料中心前端大文件分流与断点上传闭环：

- `≤ 50 MB` 独立资料继续使用现有 `/materials/import` 单文件加密通道；
- `> 50 MB` 自动切换到 `chunked-v1`：创建上传会话后使用浏览器 `File.slice()` 按服务端返回的块大小逐块上传；
- 同一时间只执行一个大型资料上传任务，避免多个数 GB / 数十 GB 文件同时抢占磁盘与内存；
- 每块请求失败最多自动重试 3 次；4xx 冲突类错误不会无意义重复重试；
- 支持暂停、继续、取消；暂停会中止当前 HTTP 请求，继续前重新读取服务端会话状态，因此即使服务器已经收下刚才的块也不会重复写错；
- 浏览器使用 `localStorage` 只保存当前 profile 与上传 `session_id` 的恢复索引，不保存文件内容、文件名或目录路径；解锁后再从加密服务器会话读取显示信息；页面刷新/重新打开后可以看到可恢复任务；
- 由于浏览器不能在刷新后自动重新取得本地 `File` 权限，恢复时要求用户重新选择同一个原文件，系统按文件名、大小、最后修改时间和目录相对路径自动匹配原上传会话，再从服务器 `completed_ranges` 继续；
- 目录扫描不再排除 50 MB 以上文件；大型文件跳过浏览器 `crypto.subtle.digest()` 整文件哈希，避免几十 GB 文件被一次性读入浏览器内存，最终完整 SHA-256 仍由服务端 finalize 流式逐块完成；
- 指定目录中的大型文件会进入同一分块上传队列，并在目录扫描列表同步显示排队、上传、暂停、完成或失败状态；
- 资料中心补齐 `video` 分类入口和基础视频类别样式，为 v0.0.9.4 视频元数据/封面做准备；
- 文件大小显示扩展到 GB / TB；
- `chunked-v1` 大型资料在 v0.0.9.5 Range 读取接口完成前不会调用旧的整文件下载 API，避免出现已入库但点击“下载”必然报错的假功能。

当前刷新恢复语义明确为“服务器断点持久化 + 用户重新选择原文件后继续”，而不是把 GB 级文件复制到浏览器 IndexedDB。这样可以保持本地磁盘单份数据、不额外占用几十 GB 浏览器存储，也更符合 LifeGraph 本地资料库的长期架构。

下一步进入 v0.0.9.4：视频资料元数据、时长/尺寸、浏览器本地封面提取和视频资料卡片。

## 十四、v0.0.9.3 实测修正（v0.0.9.3.1）

针对数 GB 视频实测补齐三项可靠性与体验修正：

- 上传进度更新不再在每个 4 MB 分块完成后重建整套任务 DOM；改为节流更新现有进度条与文字，确保高速本地上传时“暂停 / 取消”按钮不会在 pointer down / click 之间被替换；
- 上传状态增加 `pausing` / `cancelling` 与独立 `cancelRequested`，后端大型上传管理器增加会话写入互斥，取消会等待正在落盘的当前分块结束后再清理整个会话，避免删除和分块写入竞争；
- 普通“导入资料”默认开启重复拒绝；大文件创建会话前计算约 3 MB 的首部 / 中部 / 尾部采样 SHA-256 快速指纹，不需要扫描整个数十 GB 文件即可预检重复；finalize 仍执行整文件 SHA-256 作为最终权威校验；对 v0.0.9.3 之前已经入库、尚无快速指纹的大文件，使用“文件名 + 大小 + 最后修改时间”做兼容预检；
- 大文件入库时间轴优先采用浏览器提供的文件最后修改时间，而不是上传会话创建时间；后续 v0.0.9.4 如能读取视频容器中的拍摄/创建时间，可再提升时间来源优先级；
- 上传完成后资料中心重新加载，并自动滚动到该资料所属的时间轴日期；若目标资料不在首批分页结果中，会将刚完成的资料临时合入当前已加载结果用于定位，不要求把整个大型资料库全部加载出来；
- 小文件独立导入完成后同样会定位到最后成功导入资料的位置。

下一步仍进入 v0.0.9.4：视频资料元数据、时长/尺寸、浏览器本地封面提取和视频资料卡片。

## 十五、v0.0.9.3 大文件上传性能实测优化（v0.0.9.3.3）

针对 6.56 GB 视频在本机约 3 分 12 秒完成分块上传的实测，继续优化传输链路：

- 发现原实现前后端实际上均为单块串行：前端每次只 `fetch` 一个分块；后端 `LargeUploadManager` 又用全局互斥锁包住整个“读取会话 → SHA → AES-GCM → fsync → 原子落盘”过程，因此无法利用浏览器、CPU 与 SSD 的并行余量；
- 前端改为**单个大型文件最多 3 个分块有限并发**，仍保持“大型文件任务之间一次只处理一个文件”，避免多个数十 GB 文件同时争用内存与磁盘；
- 后端分块接口在读取完单个请求体后，把加密和磁盘落盘移入 Starlette thread pool，不再阻塞 async event loop；
- `LargeUploadManager` 改为“不同分块可并行、同一分块序号互斥”，并保留 session 级 active writer 计数；取消和 finalize 会先阻止新 writer，再等待在途 writer 结束，因此不会重新引入 v0.0.9.3.1 已修复的取消/写入竞争；
- 默认分块策略调整为：≤1 GB 使用 4 MB；1–16 GB 使用 8 MB；16–128 GB 使用 16 MB；更大文件使用 32 MB。6.56 GB 视频的新上传会话因此从约 1680 个 4 MB 请求下降到约 840 个 8 MB 请求；旧的断点会话继续沿用创建时记录的块大小，不强制迁移；
- 上传信息行增加实时吞吐率（MB/s 或 KB/s）与预计剩余时间。速率按最近约 8 秒已确认完成的分块做滑动窗口估算，暂停/恢复后重新建立速度窗口，避免把暂停时间计入上传速率；
- finalize 阶段明确显示“上传已完成，正在校验”，避免 100% 后仍在做整文件 SHA-256 / AES-GCM 完整性校验时被误认为界面卡住；
- 完成任务后的“移除”文案改为“清理”，含义仅为清理上传任务记录，不删除已经入库的大型资料。

这一阶段的目标是降低协议往返和串行等待。实际速度仍取决于浏览器到本机服务的吞吐、CPU AES-GCM 性能、磁盘持续写入/`fsync` 性能以及杀毒软件实时扫描等环境因素，因此以用户本机再次实测为最终依据。

## 十六、v0.0.9.4 视频资料元数据与封面

本阶段把“视频”从仅有分类标识的普通文件，提升为可浏览的媒体资料，同时保持原始大视频仍走 `chunked-v1` 外部媒体库。

已实现：

- 浏览器在上传前优先使用原生 `<video>` 读取视频 `duration / videoWidth / videoHeight`；浏览器可解码时，在约 10% 时长位置截取实际视频帧并压缩为 JPEG 封面；
- 对 Chrome 等浏览器不能直接解码/识别的 `.mkv` / `.webm`，增加轻量 Matroska/EBML 头部解析，只读取文件开头最多约 16 MB，不扫描完整数 GB 文件；可提取 Duration、PixelWidth、PixelHeight 与常见 `CodecID`，其中 HEVC/AVC/AV1/VP9 等会转换为可读编码名称；
- 当浏览器无法解码实际画面时，根据已识别的时长、分辨率、编码和文件名生成信息型视频封面，因此 MKV/H.265 仍能在资料中心以视频卡片正常展示；
- 视频元数据不改变 schema：继续保存在 attachment 的 AEAD 加密 metadata 中，字段包括 `duration_seconds`、`video_width`、`video_height`、`video_codec`、`video_metadata_source`、`video_poster_source`；
- 新增独立 `data/previews/<shard>/<attachment-id>.lgpreview` 小型加密预览存储。封面最大 512 KB，支持 JPEG/WebP/PNG；封面使用独立 AEAD/AAD 加密，不写入明文数据库，也不需要为了显示封面而解密原始数 GB 视频；
- 大文件上传会话新增 `PUT /api/v1/materials/large/uploads/{session_id}/video-metadata` 与 `PUT /api/v1/materials/large/uploads/{session_id}/preview`。元数据与临时封面均先进入加密上传会话，finalize 后才绑定到正式 attachment；
- 普通 `≤50 MB` 独立视频资料和内容附件也支持同一套视频 metadata + preview，因此大小视频使用统一资料模型；
- 新增 `GET /api/v1/attachments/{attachment_id}/preview`，只解密几十 KB 的封面派生文件；原始 `chunked-v1` 视频仍不在本阶段开放整文件读取；
- 资料中心时间轴/列表卡片与日期详情资料卡片均支持视频封面，并显示 `时长 · 分辨率 · 编码`；如果封面缺失或损坏，自动回退到通用视频图标；
- 删除资料时同时删除对应加密封面；大型媒体 finalize 时即使封面损坏，也不会因此丢弃已经完整上传并通过 SHA-256 校验的数 GB 原始视频。

当前边界：

- `data/previews` 目前被视为可再生成的派生预览缓存，尚未纳入 `.lifevault v2`。v0.0.9.6 在设计 core/full 分层备份时会一并决定预览文件应进入核心备份还是随大型媒体库存放；
- 本阶段只做“封面与媒体信息浏览”，视频卡片上的播放能力仍保持关闭。真正的随机解密、HTTP Range、206 与原生 `<video>` 拖动播放进入 v0.0.9.5；
- MP4/MOV/WebM 等浏览器支持格式通常可生成真实视频帧；MKV/H.265 等不受浏览器解码器支持的组合当前使用 EBML 元数据 + 信息型封面，待 Range 播放阶段根据浏览器实际 codec 能力决定是否需要额外兼容方案。

下一步进入 v0.0.9.5：`chunked-v1` 随机范围读取、HTTP Range/206 与在线视频播放。

## 十七、v0.0.9.5 HTTP Range 与在线视频播放

本阶段把 v0.0.9.1 已具备的 `chunked-v1` 随机字节解密能力正式接到 HTTP 与浏览器播放器，原始大型视频继续保持“分块密文落盘”，不生成临时完整明文文件。

已实现：

- 新增附件级临时媒体票据。前端仍使用 Bearer 会话调用受保护的 `POST /api/v1/attachments/{attachment_id}/playback-ticket`，随后原生 `<video>` 只携带这一份 attachment 绑定的随机 ticket 访问流接口；不会把主登录 Bearer Token 直接写进媒体 URL；
- 播放 ticket 使用最长至少 4 小时的滑动有效期，适合长视频播放/暂停；仓库执行 lock 时与普通会话一起全部撤销；ticket 不能拿去访问另一份 attachment；
- 新增 `GET /api/v1/attachments/{attachment_id}/stream?ticket=...` 与对应 HEAD；支持 RFC 7233 常用单 Range 形式：`bytes=start-end`、`bytes=start-`、`bytes=-suffix`；多 Range 暂不支持并返回 416；
- Range 请求返回 `206 Partial Content`、`Accept-Ranges: bytes`、精确 `Content-Range` 与 `Content-Length`；无 Range 时以 `200` 流式返回完整对象；无效/越界 Range 返回 `416` 和 `Content-Range: bytes */<total>`；
- `chunked-v1` Range 读取只定位并 AES-GCM 解密命中的密文块，再从首尾块切出精确字节范围；不会拼接数 GB 临时明文，也不会把整个文件读入内存；跨块 Range 已有专项测试；
- `blob-v1` 小视频也复用同一 stream API，因此普通小视频与大型分块视频的前端播放入口统一；小文件仍受 50 MB 上限约束，Range 时最多只在内存中验证这一份小附件；
- 大型资料正式开放流式下载：下载使用同一 ticket + stream 接口，并通过 `Content-Disposition: attachment` 交给浏览器直接接收，不使用 `fetch(...).blob()` 缓冲数 GB 内容；
- 资料中心、日期详情与内容附件中的视频均增加“播放”入口；有封面的视频可直接点击封面中央播放图标；播放器使用原生 `<video controls playsinline preload="metadata">`，支持浏览器自身提供的暂停、拖动、倍速、音量和全屏；
- 播放过程中 `waiting / seeking` 会提示“按需解密/定位目标分块”，便于区分网络/解密缓冲与浏览器解码问题；
- 对浏览器无法解码的容器/编码组合会明确提示兼容性问题，并保留“下载原视频”。HTTP Range 与加密随机读取可以正常工作，并不等价于浏览器一定拥有相应 codec；例如 MKV / H.265 是否能原生播放仍取决于当前浏览器和系统解码能力；
- 视频 stream 请求明确排除自动 `.lifevault` 调度触发，避免播放器连续 Range 请求给自动备份检查造成额外负担；
- 视频播放器关闭、离开主页或锁定仓库时立即停止媒体请求并清空 `src`，不在前端保留可继续复用的播放 URL。

安全与性能边界：

- 每个 `lgchunk` 仍执行独立 AES-GCM 完整性认证；Range 只减少“需要解密多少块”，不会绕过块认证；
- 当前不缓存解密后的大型视频块到磁盘，也不建立长期明文缓存。浏览器若对同一 8 MB 块发出多个很小的 Range 请求，后端可能重复解密该块；先以实际长视频播放数据观察，再决定 v0.0.9.7 是否需要受限的内存块缓存；
- 当前只实现单 Range。原生 HTML5 视频的主流播放/seek 场景不依赖 multipart/byteranges；若后续发现特定浏览器确有多 Range 请求，再扩展而不是提前增加协议复杂度。

下一步进入 v0.0.9.6：核心 `.lifevault` 与大型媒体库的正式分层备份、媒体 inventory、缺失/离线状态和恢复后重新挂接。

## 十八、v0.0.9.5.1 浏览器音频兼容层

针对 MKV/H.265 视频可以正常 Range 播放、拖动，但 DTS 音轨在 Chrome/Edge 中无声的实测问题，本阶段在不改动原始视频的前提下增加独立兼容音轨层。

已实现：

- 自动检测 FFmpeg/FFprobe，优先级为 `LIFEGRAPH_FFMPEG_PATH` → `C:\ffmpeg\bin\ffmpeg.exe` / `C:\ffmpeg\ffmpeg.exe` → 系统 `PATH`；缺少 FFmpeg 时 LifeGraph 仍可正常启动和播放原视频，只显示音轨兼容提示；
- Matroska/EBML 浏览器侧元数据继续扩展到音轨，能识别 DTS、AC-3、E-AC-3、TrueHD、AAC、Opus、Vorbis、FLAC、MP3 等 CodecID，并保存 `audio_codec / audio_codec_id / channels / sample_rate`；
- 对 v0.0.9.4 已经入库、尚无音频元数据的旧视频，播放器打开时后端只随机解密文件开头最多 16 MB 并交给 FFprobe 探测，不需要重新上传，也不扫描完整数 GB 视频才能判断音轨类型；
- DTS / AC-3 / E-AC-3 / TrueHD / MLP 被明确视为浏览器兼容风险音轨。检测到这些音轨且 FFmpeg 可用时，播放器自动启动一次性兼容音轨生成；
- 转码输入不生成完整明文视频副本：后端按原 `chunked-v1` 顺序逐块 AES-GCM 解密，并通过 stdin 直接喂给 FFmpeg；FFmpeg 只映射第一主音轨，原视频轨完全不参与重编码；
- 兼容音轨采用 AAC-LC 立体声派生轨，优先保证 Chrome/Edge 的普遍可解码能力；原始 DTS/AC-3/TrueHD 5.1/7.1 音轨保持原样、继续保存在原视频中；
- FFmpeg 输出 fragmented MP4/AAC 到 stdout，LifeGraph 不落完整明文兼容音频文件，而是边接收边使用 `ChunkedMediaStore.write_stream()` 分成 4 MB `lgchunk` 并 AES-GCM 加密保存到 `data/audio_compat/`；
- 新增 `GET/POST /api/v1/attachments/{id}/audio-compat`：查询探测/生成状态或启动兼容音轨任务；生成进度按原视频已送入 FFmpeg 的字节数显示；
- 新增 `/api/v1/attachments/{id}/audio-compat/stream` GET/HEAD，复用视频 attachment-scoped playback ticket，同样支持 HTTP Range / 206；
- 播放器内部增加隐藏 `<audio>` 元素。原 `<video>` 继续负责画面、原生进度条与控制栏；兼容 AAC 音轨跟随 video 的 play/pause、seek、volume、muted、playbackRate，并在时间漂移超过阈值时重新同步；
- 第一次兼容音轨后台生成完成时，如果原视频正在无声播放，会暂停一次并提示用户再次点击播放，以满足浏览器音频 autoplay 限制；后续再次打开同一视频时直接挂接已加密保存的 AAC 兼容轨，不再重复转换；
- 兼容音轨属于可再生成的派生媒体：删除原资料时同步删除；仓库 lock 会请求取消仍在运行的 FFmpeg 任务；异常中断留下的无 manifest 派生目录会在下次启动时自动清理；
- 音频兼容状态轮询与 Range stream 均排除自动 `.lifevault` 调度触发，避免播放/转码状态查询造成备份噪声；
- 当前只取第一主音轨生成兼容 AAC。多国语言/多音轨选择属于后续媒体播放器增强，不在 v0.0.9.5.1 扩展范围内。

实测验证：

- 使用本地生成的 MKV + DTS 测试文件，FFprobe 能识别 DTS；
- 后台 DTS → AAC 转换成功，输出再次经 FFprobe 验证为 AAC；
- 兼容音轨密文落盘，明文片段不出现在 `.lgchunk` 中；
- 兼容音轨 Range 请求返回 `206 Partial Content` 和 `audio/mp4`，并通过专项 API 测试验证随机范围内容一致。

下一步恢复原计划进入 v0.0.9.6：核心 `.lifevault` 与大型媒体库正式分层备份，并将 `previews` 与 `audio_compat` 一并纳入“核心索引 / 可重建派生文件 / 原始大型媒体”的备份策略。


### v0.0.9.5.2 音频兼容生成加速

- 大型加密媒体为 FFmpeg 顺序读取时，采用 4 worker / 6 chunk 的有界并行预取解密；输出顺序保持不变，内存占用仍受控。
- 浏览器兼容 AAC 派生轨改为 256 kbps 立体声，并启用 FFmpeg 原生 AAC 的 `aac_coder=fast`，原始 DTS / AC-3 / E-AC-3 / TrueHD 音轨不做任何修改。
- 播放器在兼容音轨生成期间显示实时处理速率和预计剩余时间。
- 该优化仍需顺序读取原视频，因为容器中的音频数据分布在整部视频时间线上；不会生成完整明文临时视频。

### v0.0.9.5.3 音频兼容顺序流水线优化

v0.0.9.5.2 在 Windows 本机实测中出现反效果：6.56 GB 视频的兼容音轨生成仅约 14 MB/s，说明“多个线程同时打开/读取不同 `.lgchunk` 文件”的方式不适合当前本地文件系统与实时扫描环境。因此 v0.0.9.5.2 的多 worker 预解密被视为性能实验，不再用于音频兼容主链路。

v0.0.9.5.3 调整为更保守的顺序流水线：

- 原视频始终只使用一个后台 reader，按 `0 → 1 → 2 → ...` 顺序打开、读取并 AES-GCM 解密分块，不再并行访问多个 chunk 文件；
- reader 与 FFmpeg stdin 之间加入最多 3 个明文块的小型内存缓冲，使“下一块读取/解密”可与“当前块写入 FFmpeg/转码”重叠；以 8 MB 原视频块计算，额外明文缓冲约不超过 24 MB；
- 若 FFmpeg 消费速度变慢，producer 会被有界队列自动背压，不会无限预读整部视频；任务取消/异常时会停止 producer；
- `iter_plain_chunks_prefetched()` 暂时保留供专项测试/未来其他场景评估，但音频兼容生成不再使用它；
- AAC 派生轨属于可重新生成缓存，输出 `.lgchunk` 不再逐块强制 `fsync`；最终加密 manifest 仍使用原有原子写入 + `fsync` 提交。原始视频、普通附件和正式大型媒体的 durable 写入策略完全不变；
- 继续保留 v0.0.9.5.2 已启用的 AAC-LC 256 kbps、`aac_coder=fast` 以及处理速率/预计剩余时间显示。

这一版的目标不是用更多线程追求峰值，而是让 Windows/SSD 的读盘方式保持连续、可预测，同时用很小的缓冲隐藏 FFmpeg stdin 的短暂等待。最终吞吐仍以用户同一 6.56 GB 视频在实际机器上的复测为准。

### v0.0.9.5.4 快速浏览器兼容音轨

v0.0.9.5.2 / v0.0.9.5.3 在用户 Windows 实机对同一 6.56 GB 视频复测时，兼容 AAC 生成仍只有约 13–14 MB/s，预计耗时接近 8 分钟。由此确认继续微调分块预取、并发或 `fsync` 已无法解决主要耗时，本阶段改为优化“浏览器兼容派生音轨”的编码目标本身。

设计与实现：

- 原始 DTS / AC-3 / E-AC-3 / TrueHD 音轨继续完整保留在原视频中，不修改、不覆盖；本地播放器仍可使用原始高质量/多声道音轨；
- 浏览器兼容派生轨不再固定为 AAC。LifeGraph 启动兼容任务时先查询当前 FFmpeg 编码器列表；若存在 `libmp3lame`，优先生成 **224 kbps CBR、双声道 MP3**；若当前 FFmpeg 构建不含 LAME，则自动回退原来的 **256 kbps AAC-LC**；
- MP3 派生轨使用 `audio/mpeg` + `.mp3`，AAC 回退轨继续使用 `audio/mp4` + `.m4a`。两者都继续经过 `ChunkedMediaStore.write_stream()` 边输出边 AES-GCM 分块加密，不生成完整明文临时音频；
- `audio_compat` metadata、状态 API、Range/HEAD/GET stream 均改为动态返回兼容轨的实际 `codec / media_type / filename`，不再硬编码 AAC；已有已完成 AAC 兼容轨保持可读、无需强制重建；
- 前端播放器兼容状态文案也改为动态显示，例如 `AC-3 → MP3` 或 `DTS → AAC`，生成期间会直接显示当前实际目标编码器；
- MP3 与 AAC 共用原有 attachment-scoped playback ticket、HTTP Range / 206 与 `<audio>` 同步逻辑，暂停、seek、音量、静音和倍速联动机制不变；
- 当前仍只转换第一主音轨，多语言音轨切换继续留给后续播放器增强。

这一调整的目标不是替换原始音频质量，而是把派生轨明确定位为“浏览器出声缓存”。最终性能仍以用户 Windows 机器上的同一 6.56 GB 视频实测为准。


## 十九、v0.0.9.6 核心 `.lifevault` 与大型媒体库分层备份

本阶段正式结束 v0.0.9.2 起的“chunked-v1 只留索引”过渡规则，把大型媒体备份模型固定为 **核心备份 + 外部媒体镜像**。

### 1. `.lifevault v3` 定位为核心备份

当前写出格式升级为 `lifegraph-lifevault format_version=3`。v3 包含：

- SQLite 一致性快照 `lifegraph.db`；
- 密钥包装元数据 `vault.json`；
- `blob-v1` 普通附件密文；
- 已存在并通过校验的小型视频封面 `previews/*.lgpreview`；
- 新增加密 `media-inventory.lgindex`，记录大型媒体 opaque ID、大小、整文件 SHA-256、分块规格、备份时在线状态以及可重建兼容音轨关系。

`manifest.json` 只保存聚合数量/字节数和策略，不写文件名、时间轴日期、标题或媒体路径。媒体 inventory 本身再次使用仓库主密钥 AEAD 加密。

### 2. 原始大型媒体不再进入单文件备份

`data/media/` 被正式定义为外部原始媒体层：

- `.lifevault` 不打包任何 `.lgchunk`；
- 原始媒体继续保持 `chunked-v1` AES-GCM 密文；
- 适合由 R2、NAS、外置盘或其他文件级同步工具直接做增量镜像；
- 完整备份语义为 `core .lifevault + data/media mirror`，而不是一个数百 GB 的 ZIP。

### 3. 派生媒体边界

- `data/previews/`：小而高价值，v3 中已存在且可验证的封面随核心备份保存；
- `data/audio_compat/`：浏览器兼容 MP3/AAC 可由原视频重新生成，不进入核心备份，也不属于完整恢复必需项；
- 媒体 inventory 会记录兼容音轨关系与备份时状态，但不保存派生音轨分块。

### 4. 媒体在线状态与自动重新挂接

新增媒体结构状态：

- `online`：加密 manifest 可认证，且与数据库大小/SHA/分块规格一致；完整性检查时所有预期 chunk 均存在；
- `offline`：数据库索引存在，但对应媒体目录尚未恢复；
- `incomplete`：manifest 存在但分块缺失；
- `invalid`：manifest 无法认证或与数据库索引不一致。

公开 attachment 数据增加 `media_state / media_available`。恢复核心备份但尚未复制媒体库时，视频卡仍可借助 v3 内嵌封面和元数据显示，但播放/下载按钮禁用并标记“媒体离线”。把原 `data/media/<shard>/<media-id>` 放回后，LifeGraph 会自动根据加密 manifest 与索引重新识别为 online，不修改数据库、不重新导入。

### 5. 恢复行为

v3 自动恢复会原子替换：

- `vault.json`；
- `lifegraph.db`；
- `data/attachments/`；
- `data/previews/`。

恢复不会删除或覆盖 `data/media/` 和 `data/audio_compat/`。这样既允许先放媒体再恢复核心，也允许先恢复核心、稍后再拷贝媒体。匹配的媒体自动挂接；无关媒体目录不会进入数据库。

恢复前安全备份、手动导出和本地自动备份均统一升级为 v3。导入端继续兼容历史 v1/v2。

### 6. 设置界面

“备份与迁移”新增“大型媒体库”状态卡，可查看：

- 原始大型媒体数量和总容量；
- online / offline / incomplete / invalid 状态；
- `data/media` 为完整备份必需的外部目录；
- 浏览器兼容音轨数量及“可重建、不要求备份”策略。

核心完整性检查仍可在媒体离线时通过，但会明确区分“核心备份可生成”和“完整媒体备份尚未 ready”。

### 7. 兼容与容错

- v1/v2 继续可验证、导入和恢复；
- 历史备份可能有视频封面 metadata 但没有实际 `data/previews` 文件。v3 对“缺失的旧封面”采用可降级策略：不阻止核心备份，只嵌入当前实际存在且验证通过的封面；
- 已存在但无法解密或 SHA 不一致的封面仍视为完整性错误；
- v3 媒体 inventory 在恢复演练中会与加密数据库大型媒体记录逐项核对，防止索引被替换或错配。

至此，v0.0.9 的大文件上传、视频媒体、Range 播放、浏览器音频兼容与核心/大型媒体分层备份形成完整闭环。

## v0.0.9.6.1 — Windows 实机备份修复

- 核心 `.lifevault v3` 不再因缺失或损坏的视频封面预览而整体失败。视频封面属于可重建派生资源：存在且校验通过时纳入核心备份；缺失或损坏时记录为跳过/警告，数据库、普通附件和大型媒体索引仍可正常导出与自动备份。
- `.lifevault v3` 自验证同步允许数据库中保留历史封面元数据但备份包未嵌入该封面的情况，并返回 `preview_files_missing` 统计；多余的无数据库对应封面文件仍被视为包结构错误。
- 备份完整性检查将封面缺失/损坏降级为 `preview_files_missing` / `preview_files_invalid`，不再阻断核心备份。
- 媒体清单扫描增强 Windows 文件系统容错：单个媒体目录或分块暂时不可访问时记录为 invalid/incomplete，而不是让核心备份抛异常。
- 磁盘型 `.lifevault` 在最终 `fsync` 前以可写句柄重新打开临时文件，避免 Windows 对只读句柄刷新行为差异。
- 前端备份错误优先显示服务端具体原因，后续排错不再只看到笼统的“备份导出失败”。

## v0.0.9.6.2 — 大型媒体独立增量备份

在 `.lifevault v3` 与 `data/media` 分层规则稳定后，本阶段补齐大型媒体库自身的本地/外置盘备份闭环。

### 1. 独立备份目录

“设置 → 备份与迁移 → 大型媒体库”新增独立备份目录输入框。目录由用户明确指定，例如外置硬盘上的 `E:\LifeGraph-Media-Backup`。LifeGraph 在该目录中维护：

- `media/`：`data/media` 中当前数据库仍引用的原始 `chunked-v1` 加密媒体；
- `lifegraph-media-backup.json`：仅含 opaque media path、加密文件大小/SHA-256、源文件 mtime 与当前媒体 inventory 指纹的备份清单。

备份目录路径本身不会明文写入 `vault.json` 或 `.lifevault`，而是保存在本机 `data/.media-backup-target.lgcfg` 的 AEAD 加密配置中；它是机器相关设置，不随核心备份迁移。

### 2. 安全增量复制

第一次执行会复制当前在线大型媒体的 `manifest.lgmedia + *.lgchunk`。再次执行时优先根据上次清单中的源大小、mtime 与目标文件大小判定未变化文件并直接跳过，只复制新增或变化的加密分块。

为了避免误删历史备份，本阶段采用“安全增量”而不是破坏性双向镜像：当前数据库已不再引用的旧媒体块不会由备份任务自动删除。后续如需回收备份盘空间，将另做显式清理/审计流程。

单文件复制使用同目录 `.part` 临时文件，完成后原子替换；任务中断时已完成的分块保留，下次执行继续增量补齐。

### 3. 独立完整校验

新增“校验媒体备份”操作。校验会读取备份目标清单中当前媒体库所需的全部文件，并逐文件计算 SHA-256，与首次/最近一次增量复制时记录的密文摘要比较。

完整校验是可选的重 I/O 操作，不在每次增量备份后强制执行。校验完成后清单记录 `verified_at`，设置页会显示“独立备份已同步 / 已完整校验”。

### 4. 后台任务与状态

大型媒体增量备份和校验均作为后台任务执行，可在设置页关闭后继续运行；重新打开设置页会恢复任务状态。任务支持取消，并显示：

- 已处理字节 / 总字节；
- 已处理文件 / 总文件；
- 本次实际复制文件数；
- 因未变化而跳过的文件数；
- 校验通过文件数。

锁定仓库会请求取消正在运行的大型媒体备份任务。

### 5. 完整备份语义最终定型

至此 LifeGraph 的完整备份由两部分组成：

1. 核心 `.lifevault v3`：数据库、普通附件、封面和加密媒体索引；
2. 大型媒体独立备份目录：原始 `data/media` 加密分块及其独立校验清单。

`data/audio_compat` 仍是可重建派生缓存，不进入任何必需备份集合。后续接入 R2 / NAS 时可直接复用本阶段的 inventory fingerprint、增量文件判断和校验模型。

## v0.0.9.7 — 性能与可靠性收口

在 6.56 GB MKV 的 Windows 实机验证基础上，本阶段不再增加新的资料业务功能，集中补齐大文件链路的容量保护、故障清理、完整性校验与长时间 Range 播放稳定性，为 v0.0.9 正式收口做准备。

### 1. 已完成的实机大文件链路验证

本轮之前已经完成并实际验证：

- 6.56 GB 单文件分块上传、暂停、继续与取消；
- 8 MB 分块 + 单文件最多 3 路前端有限并发，实测上传吞吐约 82 MB/s；
- 刷新后重新选择同一原文件，从服务端 `completed_ranges` 继续；
- HTTP Range / 206 随机解密播放与拖动定位；
- 浏览器不兼容 DTS / AC-3 音轨派生 MP3 兼容轨，实测生成吞吐约 71 MB/s；
- `.lifevault v3` 与 `data/media` 分层，以及大型媒体独立增量备份。

因此 v0.0.9.7 的重点是保护这些已经跑通的链路，而不是重新改变存储格式。

### 2. 上传与媒体备份磁盘空间预检

创建大型上传会话前，服务端会检查 `data/media` 所在文件系统的剩余空间。除原文件大小外还保留安全余量：默认按原文件大小的 1% 计算，最少 256 MB、最多 2 GB。每个分块实际写入前再次保留 64 MB 安全余量，避免长时间上传过程中磁盘被其他程序占满后继续盲目落盘。

大型媒体独立增量备份同样增加目标磁盘预检，但只按“本次真正需要复制的新增/变化文件”计算所需空间，不会因为源媒体库总容量很大而错误要求整个媒体库大小的额外空闲空间。

磁盘空间不足时在开始或分块写入阶段明确失败，不创建看似可继续但实际无法完成的半成品任务。

### 3. 服务端分块写入并发上限

浏览器端仍保持“同一个大文件最多 3 个分块并发、不同大型文件任务依次处理”的策略。服务端额外增加全局并发保护：同一 LifeGraph 实例最多同时处理 6 个大型分块写入。

这个限制用于防止多个浏览器标签页或未来多个客户端同时上传时无限创建加密/磁盘写入任务；超过容量的请求短暂等待，持续繁忙时明确返回“上传并发繁忙”，而不是拖垮整个 FastAPI 进程。

### 4. 过期断点上传任务清理

资料中心的大文件上传区域新增“清理过期任务”。服务端会统计尚未 finalize 的上传会话及其占用空间，并把默认超过 30 天无活动的会话标记为 stale。

清理操作只删除这些长期无活动的 `.incoming` 未完成会话，不会删除已经完成并进入资料中心的 `data/media` 原始媒体。清理前仍使用现有 active-writer / cancel 互斥，避免恰好正在写入的会话被直接移除。

本阶段坚持“显式清理”而不是后台静默自动删除，避免用户有意保留较长时间的断点任务被系统擅自丢弃。

### 5. 原始媒体深度完整性校验

“设置 → 备份与迁移 → 大型媒体库”新增“校验原始媒体”。它与已有的“校验媒体备份”含义不同：

- 校验原始媒体：检查当前 `data/media` 本体；
- 校验媒体备份：检查外置盘 / 独立备份目录中的密文副本。

原始媒体校验会逐个读取所有 `.lgchunk`，执行 AES-GCM 认证解密，核对分块明文长度，并重新计算整份原始文件 SHA-256。任何单块被篡改、截断或错配都会使任务失败，因此它可以真实发现块损坏，而不是只检查“841 个文件是否存在”。

该操作是重 I/O 的按需维护任务，不会在每次启动、播放或日常备份时自动执行。

### 6. Range 播放的有限内存解密缓存

浏览器在播放、seek 或探测媒体时，可能连续请求落在同一个 8 MB 加密块内的多个 Range。为避免同一块被反复 AES-GCM 解密，Vault 增加最多 64 MB 的进程内 LRU 明文块缓存。

缓存只存在内存：

- 不生成磁盘明文缓存；
- 只缓存已经通过认证解密的原始媒体块；
- 达到 64 MB 后按 LRU 淘汰旧块；
- 锁定仓库或执行恢复后立即清空。

因此可以减少长时间播放和频繁拖动时的重复 CPU / 文件读取开销，同时不改变 `chunked-v1` 的磁盘安全边界。

### 7. v0.0.9 收口判断

完成本阶段后，v0.0.9 的核心目标已经形成闭环：

1. GB / 数十 GB 文件无需整文件进内存；
2. 分块加密、暂停续传、重复检测与断点恢复；
3. 视频元数据、加密封面、Range 在线播放；
4. 浏览器不兼容音轨的可重建兼容层；
5. `.lifevault v3` 核心备份与大型媒体库分层；
6. 大型媒体独立增量备份和双向完整性校验；
7. 磁盘容量、并发、过期会话和长时间播放的可靠性保护。

后续若实机校验无异常，v0.0.9 不再继续扩展新功能，应进入正式版本号、CHANGELOG、README、完整回归、Git commit / tag / push 的发布收口流程。R2 / NAS 远端媒体增量同步可以在后续阶段复用本版本的 inventory、块级增量和校验模型实现，不作为 v0.0.9 的发布阻塞项。

## v0.0.9.7.1 登录 / 资料中心性能热修

实机在存在较大的 `data/attachments` 与多个 `.lifevault` 自动备份后发现，登录和资料中心浏览会随备份文件总容量明显变慢。根因不是大型媒体的 8 MB 分块，而是自动备份 middleware 在几乎每个普通 API 请求后调用 `maybe_create_automatic_backup()`；旧实现即使备份未到期，也会构造完整自动备份状态，从而重新读取并 SHA-256 校验所有历史 `.lifevault`。登录阶段的 `unlock/profile/progress/content-status` 与资料中心的 `materials/browse` 因此会重复触发大文件扫描。

修正策略：

- 自动备份普通活动钩子的“未到期”路径改为只读取 `vault.json` 中的备份策略时间戳，不再扫描历史备份文件。
- 新增 `/api/v1/backup/auto/reminder` 轻量状态接口；首页备份提醒只读取文件 stat 与已保存的最近验证状态，不打开或哈希 `.lifevault` 内容。
- `/api/v1/backup/auto`、手动验证、导入预检等备份管理路径仍保留完整结构/校验和/解密验证，不降低备份安全性。
- 轻量状态中的备份完整性若未主动验证，状态为“待验证”而不是误报“损坏”。

目标是让登录、资料中心浏览等热路径耗时与当前请求本身相关，而不再与历史 `.lifevault` 总容量相关。

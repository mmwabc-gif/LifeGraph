# 人生图谱 LifeGraph v0.0.9

人生图谱是一个以生命时间为骨架、以本地加密仓库保存事件、记忆、计划与人生资料的个人数字档案系统。

> v0.0.9 是“大文件与影音资料”稳定版：在 v0.0.8 人生资料系统基础上，新增 GB / 数十 GB 文件的分块加密、断点续传、视频元数据与封面、HTTP Range 随机解密播放、浏览器音频兼容层，以及 `.lifevault v3` 与大型媒体库的分层备份。

## v0.0.9 核心能力

### 大文件分块加密与断点续传

- 普通资料 ≤ 50 MB 继续使用成熟的 `blob-v1` 通道；
- 大型资料自动进入 `chunked-v1`，单文件安全上限 2 TB；
- 自适应分块：≤1 GB 为 4 MB，1–16 GB 为 8 MB，16–128 GB 为 16 MB，更大文件为 32 MB；
- 每个块使用独立随机 nonce 与 AES-GCM 认证加密；
- 浏览器通过 `File.slice()` 分块上传，内存中只保留少量块；
- 支持暂停、继续、取消、失败重试和刷新后重新选择原文件续传；
- 大文件重复检测使用轻量快速指纹，最终入库仍以完整 SHA-256 为准；
- 单个文件最多 3 路前端有限并发，服务端全局最多 6 个分块同时写入；
- 上传前和分块写入前进行磁盘剩余空间检查。

### 视频资料与媒体元数据

- 自动识别视频资料并提取时长、分辨率和编码信息；
- 浏览器可解码格式直接截取真实视频画面作为封面；
- MKV / Matroska 等格式可从头部读取时长、宽高与常见编码；
- 无法直接截图时生成信息型视频封面；
- 封面作为独立小型加密预览保存于 `data/previews`；
- 资料中心时间轴和日期详情均显示视频卡片、封面、时长、分辨率、编码与文件大小。

### HTTP Range 与在线视频播放

- 大视频无需生成完整临时明文；
- 支持标准 HTTP Range / `206 Partial Content`；
- seek 时只定位并解密涉及的加密块；
- 支持播放、暂停、进度拖动、音量、倍速和全屏；
- 大文件下载同样使用流式随机解密；
- Range 播放增加最多 64 MB 的进程内 LRU 明文块缓存，锁仓后立即清空。

### 浏览器音频兼容

Windows 本地播放器可使用系统/第三方解码器，但浏览器不一定支持 MKV 中的 DTS、AC-3、E-AC-3、TrueHD 等音轨。v0.0.9 增加可重建兼容层：

- 自动探测视频主音轨；
- 检测到浏览器常见不兼容音轨时，优先使用 FFmpeg `libmp3lame` 生成 224 kbps 立体声 MP3；
- 无 MP3 编码器时自动回退 AAC；
- 原始 DTS / AC-3 等音轨不修改、不删除；
- 兼容音轨边生成边分块加密保存于 `data/audio_compat`；
- 播放时原视频画面与兼容音轨同步，支持 seek、暂停、倍速、音量联动；
- `data/audio_compat` 属于可重建派生缓存，不要求备份。

FFmpeg 自动检测顺序包括：

```text
C:\ffmpeg\bin\ffmpeg.exe
C:\ffmpeg\ffmpeg.exe
系统 PATH
```

### `.lifevault v3` 与大型媒体分层备份

v0.0.9 将完整备份正式拆为两层：

```text
核心 .lifevault v3
├─ lifegraph.db
├─ vault.json
├─ 普通附件 data/attachments
├─ 视频封面 data/previews
└─ 加密大型媒体 inventory

大型媒体独立备份
└─ data/media 的 chunked-v1 加密分块镜像
```

- 大型原始媒体不进入单个 `.lifevault`，避免数百 GB / TB 媒体反复重打 ZIP；
- 恢复核心 `.lifevault` 后，即使媒体尚未复制回来，资料索引和封面仍可显示，并标记“媒体离线”；
- 将匹配的 `data/media` 放回后会自动重新挂接，无需重新上传或修改数据库；
- 支持将大型媒体增量镜像到本地/外置盘目录；
- 再次备份时未变化的加密分块直接跳过；
- 支持独立备份 SHA-256 完整校验；
- 原始媒体还支持逐块 AES-GCM 解密 + 整文件 SHA-256 深度校验。

### 大型媒体可靠性维护

- 资料中心支持清理 30 天以上无活动的未完成大文件上传会话；
- 不会自动删除已入库的大型媒体；
- 媒体状态区分 `online / offline / incomplete / invalid`；
- 媒体备份目录采用 `.part` 临时文件后原子替换；
- 登录和资料中心热路径只读取轻量备份策略元数据，不再反复扫描历史 `.lifevault`；
- 完整备份校验仅在备份管理、验证或恢复预检时执行。

## v0.0.8 既有能力

v0.0.9 完整保留 v0.0.8 的人生资料系统：

- 加密附件与独立资料；
- EXIF / 文档内部时间 / 文件时间识别；
- 资料自身时间与父内容时间解耦；
- 资料中心时间轴与列表；
- 指定目录扫描与批量导入；
- 48 份/批分页与图片懒加载；
- 首页快捷月历、农历、二十四节气和重要传统节日；
- 事件、记忆、计划、统一标签、搜索、内容中心和人生图谱。

## 数据与格式

```text
应用版本：0.0.9
数据库：schema v8
.lifevault：format v3
大型媒体：chunked-v1
普通附件：blob-v1
```

主要数据目录：

```text
data/
├─ vault.json
├─ lifegraph.db
├─ attachments/        # 普通附件密文
├─ media/              # 大型原始媒体分块密文
├─ previews/           # 小型加密视频封面
├─ audio_compat/       # 可重建浏览器兼容音轨
├─ backups/auto/       # 自动核心备份
└─ recovery/           # 恢复前救援备份
```

schema v8 在附件索引中增加大型媒体存储类型与 `media_id`，旧 v7 数据库可自动非破坏性迁移。

`.lifevault v3` 继续兼容导入历史 format v1 / v2。

## Windows 启动

首次运行：

```text
start.bat
```

脚本会创建 `.venv`、安装依赖、启动服务并打开：

```text
http://127.0.0.1:8765
```

环境初始化后也可使用：

```text
start_server_only.bat
```

PowerShell：

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

v0.0.9 正式收口基线：

```text
234 passed
JavaScript syntax check passed
Python compile check passed
```

## 主要 API

- 页面：`http://127.0.0.1:8765`
- API 文档：`http://127.0.0.1:8765/api/docs`
- 健康检查：`GET /health`
- 资料中心：`GET /api/v1/materials`
- 大型上传：`/api/v1/materials/large/uploads/...`
- 视频流：资料专属播放 ticket + HTTP Range stream
- `.lifevault`：核心备份导出、检查、恢复与自动备份
- 大型媒体：独立增量备份、原始媒体校验、备份校验

## 稳定版文档

- `docs/ACCEPTANCE_v0.0.9.md`
- `docs/STABLE_RELEASE_v0.0.9.md`
- `docs/GIT_COMMIT_v0.0.9.md`
- `docs/人生图谱_v0.0.9_收口归档.md`
- `docs/DESIGN_v0.0.9.md`
- `docs/LIFEVAULT_FORMAT.md`
- `docs/SECURITY_DESIGN.md`
- `docs/ARCHITECTURE.md`
- `docs/NEXT_STEPS.md`

## 下一阶段

v0.0.9 已完成本地大型媒体闭环。后续版本可优先考虑将当前媒体 inventory、块级增量与校验模型复用到 R2 / NAS 远端同步，并进一步完善媒体库批量管理、目录监控和多音轨选择。

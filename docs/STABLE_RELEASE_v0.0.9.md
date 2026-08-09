# LifeGraph v0.0.9 Stable Release

发布日期：2026-08-09

## 定位

v0.0.9 是 LifeGraph 的“大文件与影音资料”稳定版。它在 v0.0.8 人生资料系统之上，解决单个资料从几十 MB 扩展到 GB / 数十 GB 乃至更大时的上传、加密、播放和备份问题。

## 主要能力

- `blob-v1` 普通资料与 `chunked-v1` 大型媒体双通道；
- GB / 数十 GB 文件分块加密与断点续传；
- 4 / 8 / 16 / 32 MB 自适应块大小，单文件安全上限 2 TB；
- 视频元数据、加密封面与资料卡；
- HTTP Range / 206 随机分块解密在线播放和流式下载；
- 浏览器不兼容 DTS / AC-3 等音轨的 MP3/AAC 派生兼容层；
- `.lifevault v3` 核心备份与 `data/media` 大型媒体库分层；
- 大型媒体本地/外置盘增量备份、校验与离线重新挂接；
- 原始媒体逐块 AES-GCM 深度校验；
- 磁盘空间、并发、过期任务、Range 缓存和热路径性能保护。

## 数据与格式

- 正式应用版本：**0.0.9**；
- 数据库 schema：**v8**；
- `.lifevault`：**format v3**；
- 大型媒体格式：**chunked-v1**；
- 普通附件：**blob-v1**。

## 升级兼容

- v0.0.8 / schema v7 可非破坏性升级到 schema v8；
- 普通附件和独立资料保持原存储与元数据；
- `.lifevault v3` 继续兼容历史 format v1 / v2 导入；
- 大型媒体不进入核心 `.lifevault`，完整恢复需要同时保留核心备份与大型媒体镜像；
- 浏览器兼容 MP3/AAC 可从原媒体重建，不属于恢复必需项。

## 实机验证

Windows 本地环境已使用约 6.56 GB MKV 进行实际验证：

- 8 MB 分块上传约 82 MB/s；
- 暂停、继续、重复检测与入库正常；
- 视频 Range 播放、拖动定位正常；
- AC-3 / DTS 类音轨通过 MP3 兼容层正常出声；
- MP3 派生链路约 71 MB/s；
- 大型媒体分块约 841 个，可独立增量备份。

上述速度仅为一次实机观测，不作为不同硬件的性能承诺。

## 验证

```text
234 passed
JavaScript syntax check passed
Python compile check passed
```

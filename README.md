# 人生图谱 LifeGraph v0.0.2

人生图谱是一个以生命时间为骨架、以本地加密仓库保存事件、记忆与计划的个人数字档案系统。

v0.0.2 已完成“日期详情 + 事件 / 记忆 / 计划最小闭环”，并扩展到整年、整月和具体日期三个时间范围。

## 当前能力

- FastAPI 本地后端与 `/api/v1` 版本化接口；
- 原生 HTML、CSS、JavaScript 前端；
- SQLite 结构索引；
- AES-GCM 加密事件、记忆、计划及档案正文；
- Argon2id 从 PIN 或恢复凭据派生包装密钥；
- 随机 256 位仓库主密钥与内存会话令牌；
- 初始化、解锁、锁定；
- 人生、年度、本月进度；
- 人生／月／年三级全范围图谱；
- 完整人生日期格 Canvas 总览；
- 全部年份与全部月份的紧密小格视图，包含未来范围；
- 年、月、日范围右侧详情抽屉；
- 年度抽屉可继续选择月份；
- 月度抽屉按周一至周日显示完整月历；
- 日期抽屉只显示当前周七天；
- 事件、记忆、计划可分别挂在整年、整月或具体日期；
- 事件圆点、记忆边框、计划空心环状态标记；
- 年月状态向上聚合，日期状态保持独立；
- schema v1 / v2 自动非破坏性升级到 schema v3；
- Windows 一键启动与自动停止旧服务后重启脚本；
- 35 项自动化测试。

## 时间范围模型

```text
人生视图：目标人生范围内的全部日期格
月视图：目标人生范围内的全部月份格
年视图：目标人生范围内的全部年份格

年格 → 年度详情 → 月份 → 月度详情 → 日期 → 日期详情
```

事件、记忆和计划均支持：

```text
time_scope = year  / period_key = YYYY
time_scope = month / period_key = YYYY-MM
time_scope = day   / period_key = YYYY-MM-DD
```

年度内容不会误点亮每一天，月度内容也不会自动写入月内日期。

## 加密说明

项目采用“SQLite 结构索引 + AES-GCM 加密业务正文”：

- `vault.json` 只保存加密参数和被包装的主密钥；
- PIN 不直接作为数据库密钥；
- 恢复凭据可独立解锁同一随机主密钥；
- 标题、正文与敏感档案在写入 SQLite 前加密；
- 查询所需的时间范围、范围键、关联 ID、版本号和时间戳保留为结构字段；
- 前端不直接访问 SQLite；
- 前端不把事件、记忆或计划正文写入 `localStorage`。

普通 SQLite 工具只能看到表结构、查询索引和密文，不能直接读取正文。

## Windows 启动

首次运行双击：

```text
start.bat
```

脚本会创建 `.venv`、安装依赖、启动服务并打开：

```text
http://127.0.0.1:8765
```

已经完成环境初始化后，可运行：

```text
start_server_only.bat
```

重复运行该文件时，会先停止 `8765` 端口上的旧服务，再重新启动。

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

v0.0.2 稳定版基线：

```text
35 passed
```

测试覆盖：

- 初始化、锁定、PIN / 恢复凭据解锁；
- 主密钥包装与错误凭据拒绝；
- 时区与进度时间精度；
- schema v1 / v2 → v3 数据库迁移；
- 年、月、日范围事件、记忆与计划新增和读取；
- 内容状态聚合；
- 标题与正文不以明文进入 SQLite、WAL 或 SHM；
- 过去日期、已结束月份和年份的计划限制；
- 前端三级图谱与抽屉层级结构。

## 数据目录

默认运行数据保存在：

```text
data/
```

`.gitignore` 已排除运行数据库、`vault.json`、WAL、SHM 和日志。源码包只保留：

```text
data/.gitkeep
```

也可以通过环境变量更改数据目录：

```text
LIFEGRAPH_DATA_DIR=D:\LifeGraphData
```

首次使用 v0.0.2 打开旧仓库时，数据库自动升级到 schema v3，已有加密档案和按日内容不会被重写为明文。

## API

- 页面：`http://127.0.0.1:8765`
- API 文档：`http://127.0.0.1:8765/api/docs`
- 健康检查：`GET /health`
- 系统状态：`GET /api/v1/system/status`
- 日期详情：`GET /api/v1/dates/{date}`
- 时间范围详情：`GET /api/v1/periods/{scope}/{period_key}`
- 内容状态：`GET /api/v1/dates/content-status`
- 新增事件：`POST /api/v1/events`
- 新增记忆：`POST /api/v1/memories`
- 新增计划：`POST /api/v1/plans`

## 版本文档

- `docs/ACCEPTANCE_v0.0.2.md`
- `docs/STABLE_RELEASE_v0.0.2.md`
- `docs/GIT_COMMIT_v0.0.2.md`
- `docs/NEXT_STEPS.md`
- `docs/SECURITY_DESIGN.md`
- `docs/ARCHITECTURE.md`

## 当前边界

v0.0.2 暂不包含：

- 内容编辑、删除和恢复；
- 照片与附件；
- 文件扫描；
- 农历；
- 浏览器插件；
- 多设备同步。

下一阶段规划见 `docs/NEXT_STEPS.md`。

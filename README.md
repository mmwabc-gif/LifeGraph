# 人生图谱 LifeGraph v0.0.2

人生图谱是一个以生命时间为骨架，逐步连接事件、记忆、照片、文件和未来计划的本地优先个人数字档案系统。

当前开发步为 **v0.0.2.4：未来计划最小闭环**：

```text
点击生命日期格
  ↓
打开当天详情抽屉
  ↓
添加正式事件、个人记忆或未来计划
  ↓
AES-GCM 加密写入 SQLite
  ↓
重新读取当天内容
  ↓
生命日期格显示事件圆点、记忆边框与计划空心环
```

## 当前包含

- FastAPI 本地后端；
- `/api/v1` 版本化接口；
- 原生 HTML/CSS/JavaScript 前端；
- SQLite 索引数据库；
- AES-GCM 敏感字段加密；
- Argon2id 从 PIN / 恢复凭据派生包装密钥；
- 随机 256 位仓库主密钥；
- 内存会话令牌；
- 初始化、解锁、锁定；
- 人生、年度和月度进度；
- Canvas 100 年生命日期格；
- Canvas 日期命中与右侧日期详情抽屉；
- 正式事件新增、按日期读取与内容状态查询；
- 个人记忆新增、按日期读取与独立内容状态；
- 未来计划新增、按日期读取与独立内容状态；
- 日期格使用事件圆点、柔和记忆边框和计划空心环区分三类内容；
- 悬停放大镜同步显示事件、记忆与计划状态；
- schema v1 → v2 非破坏性自动迁移；
- 事件、记忆、计划三张加密内容表；
- 基础自动化测试；
- Windows 一键启动脚本。

## 当前加密说明

项目使用“SQLite 结构索引 + AES-GCM 加密业务正文”的跨平台方案：

- `vault.json` 只保存加密参数和被包装的主密钥；
- 个人档案正文在写入 SQLite 前加密；
- 事件标题和正文整体加密后写入 `events` 表；
- 记忆标题和正文使用独立 AAD 加密后写入 `memories` 表；
- 计划标题和正文使用独立 AAD 加密后写入 `plans` 表；
- 日期、关联 ID、版本号和时间戳作为查询与同步所需结构字段保留；
- PIN 不直接作为数据库密钥；
- 恢复凭据可以独立解锁同一随机主密钥；
- 普通 SQLite 工具只能看到表结构、日期索引和密文，不能读取事件、记忆或计划的标题与正文。

前端不会直接访问 SQLite，也不会将事件、记忆或计划正文保存到 `localStorage`。

## Windows 启动

安装 Python 3.10 或更高版本后，双击：

```text
start.bat
```

脚本会自动：

1. 创建 `.venv`；
2. 安装依赖；
3. 启动本地服务；
4. 打开 `http://127.0.0.1:8765`。

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

当前测试覆盖：

- 仓库初始化、锁定与重新解锁；
- 主密钥包装与错误凭据拒绝；
- 时区和时间精度；
- v1 数据库升级到 schema v2；
- 事件、记忆与计划新增、日期详情和日期内容状态；
- 事件、记忆与计划标题、正文不以明文写入 SQLite/WAL/SHM；
- 同一日期可同时保存事件、记忆和计划；
- 过去日期不能新增未来计划；
- 锁定后内容接口不可访问。

## 数据目录

默认运行数据保存在：

```text
data/
```

该目录已经被 `.gitignore` 排除，不能提交到 GitHub。

可以通过环境变量更改：

```text
LIFEGRAPH_DATA_DIR=D:\LifeGraphData
```

首次使用 v0.0.2 启动旧的 v0.0.1 仓库时，数据库会自动增加内容表并将 `schema_version` 升级为 `2`。已有加密档案行不会被改写。

## API

- 页面：`http://127.0.0.1:8765`
- API 文档：`http://127.0.0.1:8765/api/docs`
- 健康检查：`http://127.0.0.1:8765/health`
- 状态接口：`GET /api/v1/system/status`
- 日期详情：`GET /api/v1/dates/{date}`
- 日期内容状态：`GET /api/v1/dates/content-status?start=YYYY-MM-DD&end=YYYY-MM-DD`
- 添加事件：`POST /api/v1/events`
- 添加记忆：`POST /api/v1/memories`
- 添加未来计划：`POST /api/v1/plans`

## GitHub

首次发布流程见：

```text
docs/GITHUB_FIRST_PUBLISH.md
```

v0.0.1 已作为稳定基线提交并打 tag。v0.0.2 建议在独立开发分支完成并通过验收后再合并、打 tag。

## v0.0.2 后续步骤

- 增加内容编辑、软删除和恢复；
- 补齐 v0.0.2 验收文档并稳定收口。

当前阶段明确不做照片、文件扫描、农历、浏览器插件和同步。

## 设计参考文档

仓库内保留：

- `docs/reference/人生图谱系统初版设计草案_v0.3_20260805.md`
- `docs/reference/人生图谱_Stage0_原型与技术验证实施计划_v0.1_20260805.md`
- `docs/ACCEPTANCE_v0.0.1.md`

## 时区说明

Windows 下使用 `Asia/Tokyo`、`Asia/Shanghai` 等 IANA 时区名时，项目依赖 `tzdata` 包提供时区数据库。若环境依赖不完整，请重新运行：

```bat
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe scripts\run_dev.py
```

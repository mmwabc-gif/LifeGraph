# 人生图谱 Stage 0 v0.0.1

人生图谱是一个以生命时间为骨架，逐步连接事件、记忆、照片、文件和未来计划的本地优先个人数字档案系统。

v0.0.1 是第一个可运行骨架，完成以下最小闭环：

```text
初始化个人档案
  ↓
生成随机主密钥
  ↓
设置 PIN / 恢复凭据
  ↓
加密写入个人信息
  ↓
查看 100 年生命格与当前进度
  ↓
锁定并重新解锁
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
- 基础自动化测试；
- Windows 一键启动脚本。

## 当前加密说明

v0.0.1 使用“SQLite 结构 + AES-GCM 加密业务正文”的跨平台原型：

- `vault.json` 只保存加密参数和被包装的主密钥；
- 个人档案正文在写入 SQLite 前已经加密；
- PIN 不直接作为数据库密钥；
- 恢复凭据可以独立解锁同一随机主密钥；
- 普通 SQLite 工具只能看到表结构和密文，不能读取姓名、出生日期等正文。

这是 Stage 0 的可移植安全底座。后续会继续评估 SQLCipher 等整库页级加密方案，但前端和 API 无需因此改变。

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

## API

- 页面：`http://127.0.0.1:8765`
- API 文档：`http://127.0.0.1:8765/api/docs`
- 健康检查：`http://127.0.0.1:8765/health`
- 状态接口：`GET /api/v1/system/status`

## GitHub

首次发布流程见：

```text
docs/GITHUB_FIRST_PUBLISH.md
```

建议在 v0.0.1 本机验收通过后提交首个 GitHub 版本。

## 下一步

v0.0.2 建议完成：

- 事件、记忆和未来计划最小数据模型；
- 日期详情抽屉；
- 过去/今天/未来日期操作；
- 修改 PIN；
- 自动锁定倒计时；
- `.lifevault` 导出与恢复设计原型。

## 设计参考文档

仓库内保留：

- `docs/reference/人生图谱系统初版设计草案_v0.3_20260805.md`
- `docs/reference/人生图谱_Stage0_原型与技术验证实施计划_v0.1_20260805.md`
- `docs/ACCEPTANCE_v0.0.1.md`


## 时区说明

Windows 下使用 `Asia/Tokyo`、`Asia/Shanghai` 等 IANA 时区名时，项目依赖 `tzdata` 包提供时区数据库。若曾经遇到：

```text
ZoneInfoNotFoundError: No time zone found with key timezone.utc
```

请覆盖最新修复文件后重新运行：

```bat
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe scripts\run_dev.py
```

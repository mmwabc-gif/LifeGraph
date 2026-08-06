# 人生图谱 LifeGraph v0.0.3

人生图谱是一个以生命时间为骨架、以本地加密仓库保存事件、记忆与计划的个人数字档案系统。v0.0.3 完成内容管理、回收站、全页日图和个人安全设置闭环。

## v0.0.3 核心能力

### 时间图谱

- 解锁后默认进入连续日期格全页日图；
- 完整人生日期连续铺满页面，不按年龄分行，不显示年序号；
- 支持定位今天、鼠标跟随日期提示、点击日期打开右侧详情抽屉；
- 综合首页保留日／月／年三级全范围图谱；
- 年度抽屉可继续选择月份，月度抽屉按周一至周日显示完整月历，日期抽屉显示当前周七天；
- 事件、记忆和计划可分别挂在整年、整月或具体日期；
- 事件圆点、记忆边框、计划空心环实时显示内容状态。

### 内容管理

- 事件、记忆、计划支持新增、查看和原地编辑；
- 编辑保留原时间范围与创建时间，并递增 `revision`；
- 内容卡片使用“…”菜单承载编辑与删除；
- 删除采用软删除，原密文保持不变；
- 统一回收站支持恢复、单项彻底删除和清空回收站；
- revision 乐观并发校验阻止旧页面覆盖或误删新版本内容；
- 未保存表单关闭、切换、锁定或离开页面前提供保护提示。

### 个人档案与安全

- 姓名、出生日期、事件、记忆和计划正文均在本地加密保存；
- 支持修改姓名和出生日期，保存前验证当前 PIN；
- 修改出生日期后重新计算人生进度与图谱范围，原内容的公历时间不移动；
- 支持修改 PIN，只重新包装同一随机主密钥，不重写业务密文；
- 忘记 PIN 时可使用恢复凭据重置；
- 修改 PIN 后撤销当前会话并要求重新解锁；
- 锁定仓库后无法读取或修改私人内容。

## 加密模型

项目采用“SQLite 结构索引 + AES-GCM 加密业务正文”：

- 随机 256 位仓库主密钥负责加密档案和内容正文；
- PIN 与恢复凭据通过 Argon2id 派生包装密钥，用于包装同一主密钥；
- `vault.json` 只保存 KDF 参数和被包装的主密钥；
- PIN、恢复凭据、姓名、出生日期、标题和正文不会以明文写入 SQLite；
- 查询所需的时间范围、范围键、ID、版本号和时间戳保留为结构字段；
- 前端不直接访问 SQLite，也不把正文写入 `localStorage`。

## 时间范围模型

```text
年：time_scope = year  / period_key = YYYY
月：time_scope = month / period_key = YYYY-MM
日：time_scope = day   / period_key = YYYY-MM-DD
```

年度内容不会误点亮每一天，月度内容也不会自动写入月内日期；月份和年份状态会按下级内容向上聚合。

## Windows 启动

首次运行双击：

```text
start.bat
```

脚本会创建 `.venv`、安装依赖、启动服务并打开：

```text
http://127.0.0.1:8765
```

环境初始化后，可直接运行：

```text
start_server_only.bat
```

重复运行时会先停止 `8765` 端口上的旧服务，再重新启动。

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

v0.0.3 稳定基线：

```text
62 passed
```

测试覆盖初始化与解锁、加密与密钥包装、时区与进度、schema 迁移、年／月／日内容新增编辑删除、回收站、个人档案修改、PIN 修改与恢复凭据重置，以及关键前端结构与交互保护。

## 数据目录

默认运行数据位于：

```text
data/
```

`.gitignore` 已排除数据库、`vault.json`、WAL、SHM、日志、缓存和虚拟环境。源码包只保留：

```text
data/.gitkeep
```

可通过环境变量更改数据目录：

```text
LIFEGRAPH_DATA_DIR=D:\LifeGraphData
```

从 v0.0.1 或 v0.0.2 升级时，数据库会非破坏性迁移到 schema v3，已有加密档案和内容不会被重写为明文。

## 主要 API

- 页面：`http://127.0.0.1:8765`
- API 文档：`http://127.0.0.1:8765/api/docs`
- 健康检查：`GET /health`
- 系统状态：`GET /api/v1/system/status`
- 个人档案：`GET /api/v1/profile`、`PUT /api/v1/profile`
- 出生日期影响预览：`POST /api/v1/profile/change-impact`
- 修改 PIN：`POST /api/v1/auth/change-pin`
- 恢复凭据重置 PIN：`POST /api/v1/auth/reset-pin`
- 日期详情：`GET /api/v1/dates/{date}`
- 时间范围详情：`GET /api/v1/periods/{scope}/{period_key}`
- 新增内容：`POST /api/v1/events|memories|plans`
- 编辑内容：`PUT /api/v1/events|memories|plans/{content_id}`
- 软删除：`DELETE /api/v1/events|memories|plans/{content_id}`
- 回收站：`GET /api/v1/trash`
- 恢复内容：`POST /api/v1/trash/{kind}/{content_id}/restore`
- 彻底删除：`DELETE /api/v1/trash/{kind}/{content_id}`
- 清空回收站：`DELETE /api/v1/trash`

## 版本文档

- `docs/ACCEPTANCE_v0.0.3.md`
- `docs/STABLE_RELEASE_v0.0.3.md`
- `docs/GIT_COMMIT_v0.0.3.md`
- `docs/NEXT_STEPS.md`
- `docs/SECURITY_DESIGN.md`
- `docs/ARCHITECTURE.md`

## 当前边界

v0.0.3 暂不包含照片和附件、文件扫描、农历、浏览器插件、多设备同步及云端协作。

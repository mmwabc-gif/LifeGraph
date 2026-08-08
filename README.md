# 人生图谱 LifeGraph v0.0.6

人生图谱是一个以生命时间为骨架、以本地加密仓库保存事件、记忆与计划的个人数字档案系统。v0.0.6 在 v0.0.5 的记录与阅读闭环上加入记忆搜索、时间范围筛选、标签系统、地图标签高亮和标签管理，让已经记录的人生内容开始具备“查找、分类、筛选、回看”的整理能力。

## v0.0.6 当前能力

### 搜索、筛选与标签

- 记忆支持多个标签，可在「记一记」和日期详情中的新增/编辑记忆时直接选择、取消或新建标签；
- 记忆卡片正文下方展示标签，旧记忆保持兼容；
- 首页和全页视图提供【搜索】，支持标题/正文关键词、开始/结束日期和多个标签组合条件；
- 多标签搜索和地图筛选采用“同时包含”的交集逻辑；
- 搜索结果可直接打开对应年/月/日详情并定位到目标记忆；
- 首页和全页视图提供【标签筛选】，筛选后日/月/年三级图谱保持完整人生结构，只突出命中格并弱化其他格；
- 个人设置提供【标签管理】，可查看标签使用次数、新建、重命名和删除；
- 删除标签只解除标签关联，不删除任何记忆；
- `Ctrl + K` 可快速打开记忆搜索。

### 快捷导航与详情阅读

- 右侧日期详情抽屉支持全屏展开与收回；
- 抽屉底部固定悬浮【上一个 / 下一个】按钮，可跳转到相邻有事件、记忆或计划的日期 / 月份 / 年份；
- 抽屉打开时支持键盘 `←` / `→` 切换上下有内容日期；
- 首页与全页视图支持 `Alt + Enter` 打开当前日期、月份或年份详情；
- `Esc` 支持按层级关闭弹窗、收起全屏抽屉或关闭抽屉。

### 记一记快捷记录

- 首页日／月／年视图上方提供【记一记】入口；
- 全页日图顶部提供【记一记】入口；
- 点击后在页面中央打开今日记忆二级窗口；
- 默认绑定当前日期，保存为当天的个人记忆；
- 标题可选，未填写时自动从正文生成；
- 保存后即时刷新日期格中的“有记忆”状态。

### 记忆阅读

- 抽屉页和全屏详情页支持展示 TinyMCE 富文本记忆；
- 记忆正文较长时自动折叠显示；
- 右上角“...”更多菜单左侧会出现【展开 / 折叠】按钮；
- 短记忆不显示折叠按钮，保持阅读界面简洁。


### 个人设置窗口

- 设置窗口按“个人档案／安全设置／备份与迁移”分成三个通栏分组；
- 每个分组使用独立图标、浅色标题条、边框和留白，长窗口中也能快速定位；
- 修改恢复密钥归入安全设置，不再与备份功能混在一起；
- “恢复凭据”用户界面文案统一为“恢复密钥”，明确它是应急钥匙而不是第二个日常 PIN；
- 打开个人设置时，姓名与出生日期默认以只读摘要显示；
- 点击“编辑个人档案”后才显示输入框、PIN 确认和保存按钮；
- 取消编辑会直接回到只读摘要，不关闭整个设置窗口。

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


### 备份、迁移与恢复

- 个人设置弹窗始终限制在浏览器可视高度内；
- 弹窗标题和关闭按钮固定，档案、安全及备份内容在独立区域内滚动；
- 滚动条轨道保持隐藏，鼠标滚轮、触控板和触摸滚动仍可使用；
- 个人设置提供“备份与迁移”区域；
- 支持启用每天或每周本地自动备份，并设置保留 3—50 个历史版本；
- 启用时立即生成首个已验证备份，后续在仓库正常使用且周期到期时自动生成；
- 自动备份写入 `data/backups/auto/`，与 `data/recovery/` 中的恢复前安全备份分离；
- 支持查看备份历史、下载单个备份、删除单项和清空自动备份历史；
- 自动备份区域显示健康、待验证、已超期、失败、异常、未启用或尚无备份等状态；
- 新生成的自动备份会重新读取落盘文件，并完成结构、SHA-256、SQLite、外键与全部密文恢复验证；
- 支持一键再次验证最近备份，验证结果和时间写入不含秘密的备份策略摘要；
- 自动备份超期、失败或文件异常时，首页与全页视图的“个人设置”按钮显示非打扰式提醒点；
- 自动清理只作用于超出保留数量的自动备份，不影响当前仓库、手动导出文件和恢复前安全备份；
- 自动备份失败会记录错误并延迟重试，不会把已成功的普通内容操作变成失败；
- 可执行当前仓库完整性检查，验证 SQLite、外键和全部加密记录；
- 可导出 `.lifevault` 一致性加密备份；
- 导出时使用 SQLite Backup API 获取一个已提交状态的独立快照，兼容 WAL 模式；
- 可上传 `.lifevault` 并使用该备份对应的 PIN 或恢复密钥执行完整恢复演练；
- 演练会验证 ZIP 结构、格式版本、文件大小、SHA-256、SQLite、外键和每条加密记录；
- 正式恢复前必须再次确认，系统会先把当前仓库自动保存到 `data/recovery/`；
- 恢复采用候选文件验证、替换后复验和失败自动回滚；
- 恢复成功后撤销全部会话，必须使用导入备份对应的凭据重新解锁；
- 清单不包含姓名、出生日期、标题、正文、PIN 或恢复密钥明文。

### 个人档案与安全

- 姓名、出生日期、事件、记忆和计划正文均在本地加密保存；
- 支持修改姓名和出生日期，保存前验证当前 PIN；
- 修改出生日期后重新计算人生进度与图谱范围，原内容的公历时间不移动；
- 支持修改 PIN，只重新包装同一随机主密钥，不重写业务密文；
- 忘记 PIN 时可使用恢复密钥重置；
- 支持使用当前 PIN 更换恢复密钥，可自动生成高强度凭据或填写自定义凭据；
- 更换后原恢复密钥立即失效，当前 PIN 和业务密文保持不变；
- 已导出的旧 `.lifevault` 仍使用导出当时的 PIN 与恢复密钥；
- 个人设置可查看 PIN／恢复密钥槽的 Argon2id 状态和最近更新时间；
- 本地安全审计摘要只记录初始化、PIN 变更、恢复密钥轮换和仓库恢复等操作类型与时间，不记录秘密或私人正文；
- 修改 PIN 后撤销当前会话并要求重新解锁；
- 锁定仓库后无法读取或修改私人内容。

## 加密模型

项目采用“SQLite 结构索引 + AES-GCM 加密业务正文”：

- 随机 256 位仓库主密钥负责加密档案和内容正文；
- PIN 与恢复密钥通过 Argon2id 派生包装密钥，用于包装同一主密钥；
- `vault.json` 只保存 KDF 参数和被包装的主密钥；
- PIN、恢复密钥、姓名、出生日期、标题和正文不会以明文写入 SQLite；
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

v0.0.6 当前基线：

```text
112 passed
```

测试覆盖初始化与解锁、加密与密钥包装、时区与进度、schema 迁移、年／月／日内容新增编辑删除、回收站、个人档案修改、PIN 修改与恢复密钥重置、一致性快照、`.lifevault` 清单校验、恢复演练、自动导入、恢复前安全备份、本地自动备份周期、历史保留、下载删除、备份健康状态、超期判定、落盘文件快速验证、损坏识别、恢复密钥轮换、密钥槽摘要、安全审计兼容和异目录恢复。

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

从 v0.0.1—v0.0.5 升级时，数据库会非破坏性迁移到 schema v4；v4 新增标签与记忆标签关联表，已有加密档案和内容不会被重写为明文。

## 主要 API

- 页面：`http://127.0.0.1:8765`
- API 文档：`http://127.0.0.1:8765/api/docs`
- 健康检查：`GET /health`
- 系统状态：`GET /api/v1/system/status`
- 个人档案：`GET /api/v1/profile`、`PUT /api/v1/profile`
- 出生日期影响预览：`POST /api/v1/profile/change-impact`
- 修改 PIN：`POST /api/v1/auth/change-pin`
- 恢复密钥重置 PIN：`POST /api/v1/auth/reset-pin`
- 更换恢复密钥：`POST /api/v1/auth/change-recovery`
- 密钥槽与安全审计摘要：`GET /api/v1/security/summary`
- 日期详情：`GET /api/v1/dates/{date}`
- 标签：`GET|POST /api/v1/tags`、`PUT|DELETE /api/v1/tags/{tag_id}`
- 记忆标签：`GET /api/v1/memories/{memory_id}/tags`、`POST|DELETE /api/v1/memories/{memory_id}/tags/{tag_id}`
- 记忆搜索：`GET /api/v1/memories/search`
- 地图标签命中：`GET /api/v1/memories/tag-map`
- 时间范围详情：`GET /api/v1/periods/{scope}/{period_key}`
- 新增内容：`POST /api/v1/events|memories|plans`
- 编辑内容：`PUT /api/v1/events|memories|plans/{content_id}`
- 软删除：`DELETE /api/v1/events|memories|plans/{content_id}`
- 回收站：`GET /api/v1/trash`
- 恢复内容：`POST /api/v1/trash/{kind}/{content_id}/restore`
- 彻底删除：`DELETE /api/v1/trash/{kind}/{content_id}`
- 清空回收站：`DELETE /api/v1/trash`
- 备份检查：`GET /api/v1/backup/check`
- 导出备份：`GET /api/v1/backup/export`
- 导入演练：`POST /api/v1/backup/import/check`
- 恢复备份：`POST /api/v1/backup/import`
- 自动备份状态与设置：`GET|PUT /api/v1/backup/auto`
- 立即自动备份：`POST /api/v1/backup/auto/run`
- 验证最近自动备份：`POST /api/v1/backup/auto/verify-latest`
- 自动备份历史：`GET /api/v1/backup/auto/history`
- 下载／删除历史备份：`GET|DELETE /api/v1/backup/auto/history/{filename}`
- 清空自动备份历史：`POST /api/v1/backup/auto/history/clear`

## 版本文档

- `docs/ACCEPTANCE_v0.0.6.md`
- `docs/STABLE_RELEASE_v0.0.6.md`
- `docs/GIT_COMMIT_v0.0.6.md`
- `docs/人生图谱_v0.0.6_收口归档.md`
- `docs/ACCEPTANCE_v0.0.4.md`
- `docs/STABLE_RELEASE_v0.0.4.md`
- `docs/GIT_COMMIT_v0.0.4.md`
- `docs/ACCEPTANCE_v0.0.4.7.md`
- `docs/ACCEPTANCE_v0.0.4.5.md`
- `docs/ACCEPTANCE_v0.0.4.4.md`
- `docs/ACCEPTANCE_v0.0.4.3.md`
- `docs/ACCEPTANCE_v0.0.4.2.md`
- `docs/ACCEPTANCE_v0.0.4.1.md`
- `docs/LIFEVAULT_FORMAT.md`
- `docs/ACCEPTANCE_v0.0.3.md`
- `docs/STABLE_RELEASE_v0.0.3.md`
- `docs/GIT_COMMIT_v0.0.3.md`
- `docs/NEXT_STEPS.md`
- `docs/SECURITY_DESIGN.md`
- `docs/ARCHITECTURE.md`

## 当前边界

v0.0.6 暂不包含照片和附件、文件扫描、农历、浏览器插件、多设备同步及云端协作；标签和全文搜索当前以记忆为第一类内容，事件与计划的统一整理留待后续阶段；Markdown 已暂缓，后续可改为独立导入流程。


## v0.0.5.1 富文本记忆

记忆入口支持本地 TinyMCE 富文本编辑器，资源路径为 `/static/tinymce/tinymce.min.js`。当前仅启用文字、列表、链接、引用、代码和清除格式；图片、附件和表格留待后续多媒体阶段。

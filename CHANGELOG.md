# CHANGELOG

## v0.0.5 - 2026-08-08

### Added

- 抽屉页记忆卡片支持长内容自动折叠；
- 当记忆正文超过阈值时，在右上角“...”更多菜单左侧显示【展开】按钮；
- 展开后按钮切换为【折叠】，可在不进入编辑状态的情况下快速收起长记忆；
- 普通右侧抽屉和全屏详情页共用同一套折叠逻辑。

### Changed

- 长记忆默认折叠展示，减少抽屉阅读时被单条内容占满的问题；
- 记忆卡片操作区调整为“折叠/展开 + 更多操作”的并列布局；
- 短记忆不显示折叠按钮，保持卡片简洁。

### Verification

```text
98 passed
JavaScript syntax check passed
Python compile check passed
```

## v0.0.5.1 - 2026-08-07

### Added

- 首页日／月／年视图上方新增「记一记」快捷入口；
- 全页日图顶部新增「记一记」快捷入口；
- 新增居中的今日记忆二级窗口，可直接记录当前日期的个人记忆；
- 标题可选，未填写标题时会自动从正文前 28 个字符生成标题；
- 保存后立即刷新日、月、年内容状态和全页日期格标记。

### Changed

- 前端、后端、API、备份清单生产者和 Python 包版本升级为 `0.0.5.1`；
- 记录流程不再必须先打开右侧日期详情抽屉，适合随手留下当天小记；
- 数据库 schema 继续保持 v3，无需迁移。

### Verification

```text
92 passed
JavaScript syntax check passed
Python compile check passed
Quick memory modal and today-memory save flow passed
```

## v0.0.4 - 2026-08-07

### Added

- 完成 `.lifevault` 一致性加密备份导出、导入演练、正式恢复与失败自动回滚；
- 完成每天／每周本地自动备份、保留数量、历史下载、删除和清空；
- 完成备份健康、超期、失败、损坏与待验证状态，以及最近备份一键完整验证；
- 完成恢复密钥轮换、密钥槽状态和不含敏感内容的安全审计摘要；
- 完成个人设置的个人档案／安全设置／备份与迁移三组结构与默认只读档案。

### Changed

- 用户界面统一使用“恢复密钥”，并将其明确归入安全设置；
- 个人设置弹窗限制在浏览器可视高度内，标题固定、内容可滚动且隐藏滚动条轨道；
- 前端、后端、API、备份清单生产者和 Python 包版本统一为 `0.0.4`；
- 数据库 schema 保持 v3，无需新增迁移。

### Security

- 备份导出前验证 SQLite、外键和全部加密记录，落盘后再次验证包结构、SHA-256 和可恢复性；
- 正式恢复前自动保存当前仓库，替换失败时回滚原文件；
- 修改 PIN 或恢复密钥只重新包装同一主密钥，不重写业务密文；
- 发布包排除数据库、`vault.json`、自动备份、恢复包、日志、缓存、虚拟环境和个人数据。

### Verification

```text
91 passed
JavaScript syntax check passed
Python compile check passed
.lifevault export/import/rollback passed
Automatic backup, health and verification passed
Recovery-key rotation and settings structure passed
```

## v0.0.4.7 - 2026-08-06

### Changed

- 个人设置窗口重构为“个人档案／安全设置／备份与迁移”三个清晰分组；
- 三个分组新增通栏标题、线性图标、独立边框与留白，提升长设置页的扫描效率；
- “修改恢复凭据”归入安全设置，用户界面统一改称“修改恢复密钥”；
- 姓名和出生日期默认以只读摘要展示，只有点击“编辑个人档案”后才进入表单状态；
- 取消档案编辑只退出编辑态，不再关闭整个个人设置窗口。

### Safety

- 档案只读态不会要求或缓存 PIN；
- 进入编辑态时重新以当前档案填充表单，取消编辑会清除输入的确认 PIN；
- 关闭设置时，仅在实际存在未保存输入的区域触发放弃确认；
- 本次不改变密钥槽、主密钥、业务密文、备份格式或数据库 schema。

### Verification

```text
91 passed
JavaScript syntax check passed
Python compile check passed
Settings grouping and read-only profile flow passed
Recovery-key terminology and security placement passed
```

## v0.0.4.6 - 2026-08-06

### Added

- 自动备份区域新增健康状态卡，区分健康、待验证、已超期、失败、异常、未启用和无备份；
- 新增 `POST /api/v1/backup/auto/verify-latest`，对最近自动备份的落盘文件执行完整恢复验证；
- 首页和全页视图的“个人设置”按钮新增备份警示点，提示超期、失败、异常或待验证状态；
- 备份策略新增最近验证时间、验证文件名和非敏感错误摘要，旧版 `vault.json` 自动使用安全默认值。

### Safety

- 新生成的自动备份在记录成功前，会重新读取实际落盘字节并验证 ZIP、SHA-256、SQLite、外键和全部加密记录；
- 最近备份快速验证只读取自动备份目录中的最新 `.lifevault`，不会替换或改写当前仓库；
- ZIP 压缩数据损坏、CRC 或解压异常会转换为可控的备份校验错误，不再导致未处理异常；
- 健康摘要不包含姓名、出生日期、标题、正文、PIN、恢复凭据或主密钥。

### Verification

```text
90 passed
JavaScript syntax check passed
Python compile check passed
Healthy/missing/overdue backup states passed
Exact disk backup recovery verification passed
Tampered ZIP detection and controlled failure passed
Backup reminder UI hooks passed
```

## v0.0.4.5 - 2026-08-06

### Added

- 个人设置新增“修改恢复凭据”，支持自动生成高强度凭据或填写自定义凭据；
- 新增 `POST /api/v1/auth/change-recovery`，使用当前 PIN 验证后重新包装同一主密钥的恢复密钥槽；
- 新增 `GET /api/v1/security/summary`，展示 PIN／恢复密钥槽算法与最近更新时间；
- 新增本地安全审计摘要，记录仓库初始化、PIN 修改、恢复凭据重置 PIN、恢复凭据轮换和仓库恢复等操作类型与时间；
- 自动生成的新恢复凭据沿用一次性展示窗口，关闭后不再从系统中读取明文。

### Security

- 恢复凭据轮换不重写 SQLite 中的档案、事件、记忆和计划密文；
- 新恢复凭据与当前 PIN 均不写入 `vault.json`、SQLite、审计记录或浏览器存储；
- 原恢复凭据在轮换完成后立即失效，PIN 密钥槽保持不变；
- 审计摘要最多保留 50 条，只包含动作代码、结果和 UTC 时间戳；
- 对旧版 `vault.json` 自动合成只读初始化／旧安全更新时间摘要，不要求迁移数据库。

### Verification

```text
84 passed
JavaScript syntax check passed
Python compile check passed
Generated and custom recovery rotation passed
Old recovery invalidation and PIN continuity passed
Legacy security metadata compatibility passed
```

## v0.0.4.4 - 2026-08-06

### Added

- 个人设置新增“本地自动备份”，支持每天或每周周期；
- 支持设置保留 3—50 个自动备份，生成成功后自动清理超额旧版本；
- 启用策略时可立即创建首个一致性 `.lifevault`；
- 新增自动备份历史列表、单项下载、单项删除和清空历史；
- 新增 `GET|PUT /api/v1/backup/auto`、`POST /api/v1/backup/auto/run` 及历史管理接口；
- 普通 API 活动完成后检查备份周期，到期时以尽力而为方式生成本地备份。

### Safety

- 自动备份继续使用 SQLite Backup API、SHA-256 清单和逐条密文验证；
- 自动备份只写入 `data/backups/auto/`，不会覆盖当前仓库；
- 保留清理只删除自动备份目录中的旧 `.lifevault`，不触碰 `data/recovery/`；
- 自动备份失败会记录状态并至少等待一小时后重试，不影响已成功的业务请求；
- 文件下载和删除均要求有效解锁会话，并限制为自动备份目录内的 `.lifevault` 文件。

### Verification

```text
78 passed
JavaScript syntax check passed
Python compile check passed
Automatic due backup and retention cleanup passed
Backup history download/delete/clear passed
```

## v0.0.4.3 - 2026-08-06

### Fixed

- 修复新增备份恢复功能后个人设置弹窗超出浏览器底部、无法访问下方内容的问题；
- 个人设置卡片限制在当前可视高度内，标题与关闭按钮保持固定；
- 档案、安全和备份内容改为独立内部滚动区；
- 首页与全页视图共用同一修复；
- 隐藏滚动条轨道，同时保留滚轮、触控板和触摸滚动。

### Verification

```text
70 passed
JavaScript syntax check passed
Python compile check passed
Viewport-constrained settings modal check passed
```

## v0.0.4.2 - 2026-08-06

### Added

- 个人设置新增 `.lifevault` 文件选择、备份凭据验证、恢复演练与正式恢复入口；
- 新增 `POST /api/v1/backup/import/check`，在临时目录完整验证备份而不改动当前仓库；
- 新增 `POST /api/v1/backup/import`，自动导入并替换当前加密仓库；
- 正式恢复前自动生成 `data/recovery/lifegraph-before-restore-*.lifevault` 安全备份；
- 恢复成功后强制锁定，要求使用导入备份对应的 PIN 或恢复凭据重新解锁；
- 新增恢复失败自动回滚机制和恢复前安全备份可恢复测试。

### Security

- 导入检查验证固定 ZIP 结构、格式版本、schema 上限、文件大小和 SHA-256；
- 使用备份自身 PIN 或恢复凭据解开主密钥，并逐条验证全部加密档案和内容；
- 正式替换前再次验证候选数据库，替换后再次执行 SQLite、外键和密文验证；
- 备份凭据仅随本次 multipart 请求传输，不写入数据库、清单或浏览器存储；
- 恢复成功后撤销所有旧会话，防止旧令牌继续访问已替换仓库。

### Verification

```text
69 passed
JavaScript syntax check passed
Python compile check passed
.lifevault import rehearsal passed
Automatic rescue backup restore passed
```

## v0.0.4.1 - 2026-08-06

### Added

- 个人设置新增“备份与迁移”区域；
- 新增仓库完整性检查，验证 SQLite `quick_check`、外键和全部加密记录；
- 新增 `.lifevault` 一致性加密备份导出；
- 备份包包含 `manifest.json`、`repository/vault.json` 和一致性 `repository/lifegraph.db` 快照；
- 清单记录文件大小与 SHA-256，且不写入个人档案或业务正文；
- 新增 `.lifevault` 格式说明和验收测试。

### Security

- 备份导出需要有效解锁会话；
- 导出包不包含 PIN、恢复凭据或任何解密后的姓名、日期、标题和正文；
- 导出前逐条验证档案、事件、记忆、计划及回收站密文可被当前主密钥解密。

### Verification

```text
65 passed
JavaScript syntax check passed
Python compile check passed
.lifevault restore simulation passed
```

## v0.0.3 - 2026-08-06

### Added

- 连续日期格全页日图，并作为解锁后的默认入口；
- 事件、记忆和计划在年、月、日范围内的编辑闭环；
- revision 乐观并发保护；
- 三类内容软删除；
- 统一回收站、恢复、单项彻底删除和清空回收站；
- 应用内确认弹窗、未保存表单保护、处理中状态和友好错误反馈；
- 个人档案设置，支持修改姓名和出生日期；
- PIN 修改与恢复凭据重置 PIN；
- 全页日图和个人设置的响应式布局优化。

### Changed

- 内容卡片操作统一收进“…”更多菜单；
- 日期详情空状态改为紧凑的事件／记忆／计划快捷操作栏；
- 综合首页与全页日图的文字、进度卡和响应式布局完成收口；
- 前端、后端、API 和 Python 包正式版本统一为 `0.0.3`；
- 数据库 schema 保持 v3，无需新增迁移。

### Security

- 编辑后正文重新使用 AES-GCM 加密；
- 软删除不改写原 nonce 和 ciphertext；
- PIN 修改只重新包装主密钥，不重写档案和内容密文；
- 恢复凭据重置 PIN 后，原加密数据继续可读；
- 姓名、出生日期、PIN、标题和正文不会以明文进入 SQLite、WAL 或 SHM。

### Verification

```text
62 passed
JavaScript syntax check passed
Python compile check passed
```

> 以下保留 v0.0.3.1—v0.0.3.17 的开发过程记录。

## v0.0.3.17 - 2026-08-06

- 个人设置弹窗在常规桌面窗口中按内容自然撑高，不再出现内部滚动条。
- 小屏或窗口高度不足时改由弹窗遮罩层滚动，并隐藏滚动条轨道；鼠标滚轮与触控板仍可使用。
- 首页与全页日图共用同一套个人设置弹窗行为。
- 前后端开发版本更新为 `0.0.3.17`，数据库 schema 保持 v3。

## v0.0.3.16 - 2026-08-06

- 放大首页标题下方“你已经走过 X 天。”说明文字，使其与主标题和进度卡视觉层级更协调。
- 宽屏使用响应式字号，窄屏同步适度放大。
- 前后端开发版本更新为 `0.0.3.16`，数据库 schema 保持 v3。

## v0.0.3.15 - 2026-08-06

### 个人档案与安全设置

- 综合首页与全页日图新增“个人设置”入口。
- 支持修改加密个人档案中的姓名和出生日期。
- 保存个人档案前要求输入当前 PIN，并使用 `revision` 防止过期页面覆盖较新档案。
- 修改出生日期前计算影响范围；超出新图谱范围的内容不会删除，只会暂时隐藏。
- 修改出生日期后重新计算人生进度、年龄、目标日期、年/月/日图谱与今天的位置。
- 支持修改本机 PIN，只重新包装同一个主密钥，不重写 SQLite 中的档案、事件、记忆或计划密文。
- PIN 修改成功后撤销全部会话并立即锁定，要求使用新 PIN 重新解锁。
- 锁定页新增“使用恢复凭据重置 PIN”，忘记当前 PIN 时仍可恢复访问。
- PIN 与恢复凭据不会以明文写入 `vault.json`、SQLite、WAL 或 SHM。
- 前后端开发版本更新为 `0.0.3.15`，数据库 schema 保持 v3。

## v0.0.3.14 - 2026-08-06

- 移除首页生命进度圆环中的“生命进度”说明文字。
- 圆环内仅保留百分比，并保持水平、垂直居中。
- 前后端开发版本更新为 `0.0.3.14`。

## v0.0.3.13 - 2026-08-06

- 首页“你已经走过 X 天。”说明文字改为与进度卡寄语相同的字号、字重、颜色与行高。
- 生命进度圆环中的百分比与“生命进度”文字改为紧凑组合，并在圆环内整体垂直居中。
- 前后端开发版本更新为 `0.0.3.13`。

## v0.0.3.12 - 2026-08-06

- 首页顶部说明精简为“你已经走过 X 天。”，移除“人生第几天”和目标年龄说明。
- 首页首张进度卡改为显示已完整走过的天数，与顶部说明统一使用 `life.elapsed_days`，消除相差 1 天的统计口径差异。
- 综合首页日视图标题由“天天”改为“太阳每天都是新的”。
- 前后端开发版本更新为 `0.0.3.12`。

## v0.0.3.11 - 2026-08-06

- 全页日图顶部固定区改为内容驱动的自适应高度，窄窗口换行后会自动向下撑开。
- 窄屏下标题、说明、状态图例和操作按钮分层排列，不再覆盖日期格。
- 日期格滚动区域始终从顶部实际高度之后开始，浏览器宽度变化时保持正确布局。
- 前后端开发版本更新为 `0.0.3.11`.

## v0.0.3.9 - 2026-08-06

- 全页视图开启时同时锁定 `html` 与 `body`，移除原主页外层滚动条。
- 全页日期格区域仍可通过鼠标滚轮、触控板和键盘滚动，但滚动条轨道不再显示。
- 修复全页视图同时出现页面滚动条和日期区域滚动条的问题。
- 前后端开发版本更新为 `0.0.3.9`。

## v0.0.3.8 - 2026-08-06

### 连续日期格全页视图

- 在日／月／年视图切换旁新增“全页视图”入口。
- 全页视图隐藏首页其他模块，完整人生日期按连续顺序铺满浏览器页面。
- 不再按“一行一岁”分组，也不显示年龄或年份序号，日期格显著放大。
- 鼠标悬停时显示跟随浮层，包含完整日期、人生第几天、过去／今天／未来及内容状态。
- 点击日期格继续打开现有右侧详情抽屉，编辑、删除、回收站等能力保持不变。
- 新增“定位今天”和“退出全页”操作；按 Esc 可先关闭抽屉，再退出全页视图。
- 窗口缩放后保持当前浏览位置附近的日期，内容状态变化后全页格子同步重绘。
- 前后端开发版本更新为 `0.0.3.8`。

## v0.0.3.7 - 2026-08-06

### 视图命名调整

- 人生日期总览标题由“人生总览”改为“天天”。
- 右侧视图切换标签由“人生 / 月 / 年”改为“日 / 月 / 年”。
- 仅调整显示文案，人生日期格、月视图、年视图及其交互逻辑保持不变。
- 前后端开发版本更新为 `0.0.3.7`。

## v0.0.3.6 - 2026-08-06

### 内容卡片更多菜单

- 事件、记忆和计划卡片右上角默认只显示“…”更多按钮。
- 将“编辑”“删除”操作收进浮动菜单，减少卡片头部占用。
- 同一时间只允许打开一个更多菜单。
- 点击卡片外部、按 `Esc`、执行编辑或完成删除确认后自动关闭菜单。
- 补充菜单的 `aria-haspopup`、`aria-expanded`、`role="menu"` 与 `role="menuitem"` 语义。
- 移动端保持紧凑按钮，并放大菜单项点击区域。
- 前后端开发版本更新为 `0.0.3.6`。

## v0.0.3.5 - 2026-08-06

### 日期详情快捷操作栏

- 将右侧日期详情中三个大面积信息区收为日期选择区下方的“添加事件 / 添加记忆 / 添加计划”并排按钮。
- 没有内容且未打开表单时不再显示空状态大卡片。
- 已有内容或正在新增、编辑时，按类型显示紧凑内容区。
- 过去时间范围的计划按钮保持禁用，并使用紧凑提示说明原因。
- 前后端开发版本更新为 `0.0.3.5`。

## v0.0.3.4 - 2026-08-06

### Added

- 应用内统一确认弹窗，替代浏览器原生确认框；
- 未保存表单检测与放弃更改确认；
- 关闭抽屉、切换时间范围、打开回收站和锁定仓库时的草稿保护；
- 页面离开前的未保存内容提醒；
- 保存、删除、恢复、彻底删除和清空回收站的处理中状态；
- 空内容区域的直接添加入口；
- 操作成功、失败两种 Toast 反馈样式；
- 抽屉和确认弹窗的焦点返回；
- 移动端操作按钮和确认弹窗的紧凑布局；
- 交互收口专项测试。

### Changed

- 删除、永久删除和清空回收站不再调用 `window.confirm`；
- revision 冲突、会话过期和内容不存在等错误改为更易理解的中文提示；
- 三类内容表单在切换或关闭前会判断是否真的发生了修改；
- 空状态不再只有说明文字，可直接进入对应新增表单；
- 前后端开发版本更新为 `0.0.3.4`。

### Security

- 未保存标题和正文仅保留在当前页面内存中，不写入浏览器持久化存储；
- 应用内确认弹窗不会改变软删除、恢复或永久删除的后端安全规则；
- 所有写操作继续使用有效解锁会话和 revision 校验。

### Verification

```text
51 passed
JavaScript syntax check passed
Python compile check passed
```

## v0.0.3.3 - 2026-08-06

### Added

- 顶部统一回收站入口；
- 三类已删除内容的集中列表与数量统计；
- 回收站内容恢复；
- 单项彻底删除；
- 清空回收站；
- `GET /api/v1/trash`；
- `POST /api/v1/trash/{kind}/{content_id}/restore`；
- `DELETE /api/v1/trash/{kind}/{content_id}`；
- `DELETE /api/v1/trash`；
- 回收站恢复、永久删除、清空和会话保护测试。

### Changed

- 恢复内容后自动回到原年份、月份或日期范围；
- 恢复后图谱事件、记忆与计划状态立即重新聚合；
- 回收站卡片显示内容类型、原时间范围、删除时间和版本号；
- 前后端开发版本更新为 `0.0.3.3`。

### Security

- 回收站读取仍要求有效解锁会话；
- 恢复和单项彻底删除要求当前 revision，防止旧页面误操作；
- 彻底删除才会物理移除对应密文记录；
- 清空回收站只删除当前加密档案中已软删除的内容。

### Verification

```text
46 passed
```

## v0.0.3.2 - 2026-08-06

### Added

- 事件、记忆和计划卡片中的删除入口；
- 删除前确认提示；
- `DELETE /api/v1/events/{event_id}`；
- `DELETE /api/v1/memories/{memory_id}`；
- `DELETE /api/v1/plans/{plan_id}`；
- 三类内容软删除、重复删除和 revision 冲突测试。

### Changed

- 删除后写入 `deleted_at`、刷新 `updated_at` 并递增 `revision`；
- 已删除内容立即从年、月、日详情以及图谱状态标记中移除；
- 正在编辑的内容被删除后自动退出编辑状态；
- 前后端开发版本更新为 `0.0.3.2`。

### Security

- 软删除不改写 nonce 与 ciphertext，保留原始加密正文供后续恢复；
- 删除接口要求当前 revision，避免旧页面删除已经更新的内容；
- 内容 ID 仍限定在当前加密档案内。

### Verification

```text
41 passed
```

## v0.0.3.1 - 2026-08-06

### Added

- 事件、记忆和计划列表中的编辑入口；
- 编辑表单标题与正文回填；
- 编辑取消与新增模式恢复；
- `PUT /api/v1/events/{event_id}`；
- `PUT /api/v1/memories/{memory_id}`；
- `PUT /api/v1/plans/{plan_id}`；
- revision 乐观并发校验；
- 编辑接口加密与冲突测试。

### Changed

- 编辑后保留内容原创建时间和时间范围；
- 编辑后 `updated_at` 刷新且 `revision` 自动递增；
- 已编辑内容显示更新时间与版本号；
- 前后端开发版本更新为 `0.0.3.1`。

### Security

- 编辑后的标题与正文继续使用原内容 ID 对应的 AES-GCM AAD 重新加密；
- 请求中的内容 ID 必须属于当前加密档案；
- 过期 revision 返回 `409 REVISION_CONFLICT`，防止静默覆盖。

### Verification

```text
38 passed
```

## v0.0.2 - 2026-08-06

### Added

- 日期详情右侧抽屉；
- 正式事件、个人记忆和未来计划的最小闭环；
- 年、月、日三个时间范围的数据模型；
- 人生／月／年三级全范围图谱；
- 年度抽屉中的 12 个月选择；
- 月度抽屉中的周一至周日完整月历；
- 日期抽屉中的当前周七天选择；
- 日期格事件圆点、记忆边框和计划空心环；
- 年月内容状态聚合；
- Canvas 日期格悬停放大说明；
- 年月格跟随鼠标说明卡片；
- 首页人生、年度、本月进度条指标；
- `start_server_only.bat` 自动停止旧服务并重新启动；
- v0.0.2 验收、稳定发布和 Git 提交文档。

### Changed

- 数据库 schema 从 v1 / v2 非破坏性升级到 v3；
- 事件、记忆和计划标题正文统一使用 AES-GCM 加密保存；
- 月、年视图覆盖完整目标人生范围，包括未来月份和年份；
- 抽屉日期取消前导零；
- 人生 Canvas 改为按容器宽度自适应，移除横向滚动条；
- 前后端正式版本统一为 `0.0.2`。

### Security

- 验证事件、记忆和计划正文不会以明文写入 SQLite、WAL 或 SHM；
- 保持 PIN / 恢复凭据包装随机主密钥的现有机制；
- 运行数据库、密钥文件与日志继续由 `.gitignore` 排除。

### Verification

```text
35 passed
```

## v0.0.1 - 2026-08-05

- 完成 Stage 0 项目骨架；
- 完成加密仓库初始化、解锁、锁定；
- 完成人生进度与完整人生日期格原型；
- 建立 FastAPI、SQLite、AES-GCM 与自动化测试底座；
- Git 提交：`d8968bf 初始化人生图谱 Stage 0 v0.0.1`。

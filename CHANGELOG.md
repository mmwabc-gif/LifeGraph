# Changelog

## v0.0.9 - 2026-08-09

### Stable

- 完成 GB / 数十 GB 大型资料的 `chunked-v1` 分块 AES-GCM 存储、暂停/继续、断点恢复、重复检测与磁盘容量保护；
- schema 从 v7 升级到 v8，引入 `storage_kind` 与 `media_id`，普通 `blob-v1` 与大型 `chunked-v1` 两条存储通道并存；
- 视频资料支持时长、分辨率、编码、加密封面与资料卡片；
- 支持 HTTP Range / 206 随机解密在线播放、拖动定位和流式下载；
- 对 DTS / AC-3 / E-AC-3 / TrueHD 等浏览器不兼容音轨提供可重建 MP3/AAC 兼容层，原始音轨保持不变；
- `.lifevault` 升级到 format v3，核心备份与 `data/media` 大型媒体库正式分层，并继续兼容 v1/v2 导入；
- 新增大型媒体本地/外置盘独立增量备份、备份校验和原始媒体逐块深度完整性校验；
- 增加服务端分块并发上限、过期上传任务清理、Range 64 MB LRU 解密块缓存与登录/资料中心热路径性能修复；
- Windows 6.56 GB MKV 实机验证：8 MB 分块上传约 82 MB/s，浏览器兼容 MP3 派生约 71 MB/s，Range 播放与拖动正常；
- 正式稳定版统一前端、FastAPI、Python 包和 `.lifevault` producer 版本为 `0.0.9`；
- 正式收口回归基线：234 项测试通过，JavaScript 语法检查与 Python 编译检查通过。

## v0.0.8 - 2026-08-09

### Stable

- 正式完成“人生资料系统”阶段：加密附件、独立资料、资料双重时间关系、资料中心时间轴与目录批量导入形成完整闭环；
- 首页快捷月历加入年月切换、农历、二十四节气与重要传统节日；右侧月/周视图同步复用；
- 附件本地物理存储升级为 UUID 前两位 256 分片目录，并兼容旧平铺附件自动迁移；
- `.lifevault` 导出、自动备份、导入检查与恢复全面改为磁盘流式路径，保持 format v2；
- 资料中心采用 48 份/批分页追加，图片缩略图按可视区域懒加载；
- 正式稳定版统一前端、FastAPI、Python 包和 `.lifevault` 生产者版本为 `0.0.8`；
- 数据库稳定在 schema v7，`.lifevault` 稳定在 format v2；
- 正式收口回归基线：192 项测试通过，JavaScript 语法检查与 Python 编译检查通过。

## v0.0.8.9 - 大型资料库性能加固

- `.lifevault` 手动导出改为磁盘流式组包，SQLite 快照和加密附件直接写入 ZIP，不再把整个仓库备份构造在内存中。
- 自动备份同步使用磁盘流式组包，并对落盘后的备份执行磁盘读取校验。
- `.lifevault` 导入检查与正式恢复改为流式上传到临时文件，再逐项校验/恢复；不再把整个备份上传内容读入内存，安全上限提升为 2 TB。
- 自动备份历史读取改为磁盘包轻量检查，避免为了列出历史记录读取整个备份文件。
- 附件元数据新增批量迭代接口；资料中心分页时不再一次性保存全部解密元数据。
- 资料中心 API 新增 `offset`，默认每页 48 份，返回 `next_offset` / `has_more`。
- 资料中心前端滚动接近底部自动加载下一页；时间轴和列表模式均复用已加载分页数据。
- 资料中心图片缩略图使用 `IntersectionObserver` 懒加载，仅在进入可视区域附近时解密读取图片。
- 保持附件元数据加密模型、schema v7 和 `.lifevault` format v2 不变。

## v0.0.8.8 - 附件存储扩展性加固

- 附件物理存储从单目录平铺升级为按附件 UUID 前两位分片，例如 `data/attachments/a7/<UUID>.lgatt`；目录按需创建，最多自然分散到 256 个分片。
- 启动时自动检查旧版 `data/attachments/<UUID>.lgatt` 平铺文件，并尽力迁移到新分片目录；若迁移因权限或占用失败，读取链路仍兼容旧路径。
- 新上传、独立资料导入、目录批量导入和备份恢复产生的附件均直接写入分片目录。
- 删除附件时同时清理新版分片路径与旧版兼容路径，并自动移除已空的分片目录。
- `.lifevault` 继续保持 format v2，包内附件逻辑路径仍为 `repository/attachments/<UUID>.lgatt`，不因本地物理分片改变备份格式。
- 数据库 schema 保持 v7，无需数据库迁移。
- 应用、前端及备份 producer 版本统一升级为 `0.0.8.8`。

## v0.0.8.7 - 指定目录扫描与批量导入

- 资料中心新增“扫描目录”，支持浏览器主动选择目录及子目录并生成导入预览。
- 自动排除常见系统/隐藏文件、空文件及超过 50 MB 的文件。
- 浏览器端计算 SHA-256，标记目录内重复；后端批量检查仓库已有相同内容，重复资料默认不选中。
- 目录导入时后端再次校验重复，避免扫描后状态变化造成重复入库。
- 导入资料保留目录内相对路径和根目录名称作为加密元数据；不读取或保存本机绝对路径。
- 单次目录扫描上限暂定 1000 个文件，导入继续沿用现有 50 MB 单文件限制。
- 前端、FastAPI、Python 包及备份生产者版本统一升级为 `0.0.8.7`。

### Verification

```text
177 tests passed (split verification)
JavaScript syntax check passed
Python compile check passed
```

## v0.0.8.6 - 独立人生资料导入

- 资料中心新增【导入资料】，照片、文档和其他文件无需先挂到事件/记忆/计划即可直接进入人生资料库。
- 数据库 schema 从 v6 升级到 v7，`attachments.kind/content_id` 改为可选，使“资料本身”和“内容附件关系”正式解耦。
- 原有内容附件关系完整保留；独立资料以 `kind/content_id = NULL` 表示，不创建伪内容。
- 独立资料继续使用仓库主密钥加密存储，并自动参与资料中心、人生日期资料区、完整性检查和 `.lifevault` format v2 备份恢复。
- 独立资料优先使用文件自身时间进入时间轴，没有可用文件时间时回退到资料导入时间。
- 资料中心明确显示“独立资料 · 直接导入人生资料库”，并提供下载和永久删除操作。
- 前端、FastAPI、Python 包及备份生产者版本统一升级为 `0.0.8.6`。

### Verification

```text
174 tests passed (split verification)
JavaScript syntax check passed
Python compile check passed
```

## v0.0.8.5 - 资料中心时间轴视图

- 资料中心默认升级为纵向主时间轴，按资料真实归属日期聚合展示照片、文档和其他文件。
- 同一天资料归为一个日期节点，并按年份、月份组织，避免传统列表重复显示时间。
- 日期节点展示“照片数 / 文件数”摘要，可直接打开对应人生日期详情。
- 图片继续复用加密缩略图与沉浸式预览；文档和其他资料使用紧凑卡片展示。
- 新增【时间轴 / 列表】显示方式切换，列表模式继续服务检索、最近添加排序和文件管理。
- 无日期资料统一进入“时间未识别”区。
- 资料中心单次展示上限由 100 份提高到 200 份；数据库 schema 仍为 v6，`.lifevault` format 仍为 v2。
- 前端、FastAPI、Python 包及备份生产者版本统一升级为 `0.0.8.5`。

### Verification

```text
165 tests passed
JavaScript syntax check passed
Python compile check passed
```

## v0.0.8.3.1 - 资料双重时间关系

- 附件关系与资料自身时间正式分离：附件不会再因 EXIF/文件日期移动父事件、记忆或计划。
- 图片优先使用 EXIF 拍摄时间；Office/PDF 优先使用文档内部创建/保存时间；普通文件回退到浏览器提供的文件修改时间。
- 附件加密元数据新增独立的 `timeline_at / timeline_date / timeline_time_source`，不升级数据库 schema。
- 日期/月/年详情新增“资料”区域，按资料自身时间展示附件，并保留“来自哪条事件/记忆/计划”的反向引用。
- 人生图谱状态增加“有资料”标记，资料日期参与有内容日期导航。
- 移除 v0.0.8.3 中“采用 EXIF 日期后移动整条内容”的交互。

## v0.0.8.3 - 2026-08-08

### Added

- 图片附件上传时读取 EXIF 拍摄日期，优先使用 `DateTimeOriginal`，缺失时回退到 `DateTimeDigitized` / `DateTime`；
- 支持 JPEG、TIFF、PNG eXIf 与 WebP EXIF 容器的拍摄时间解析，不新增 Pillow 等图片依赖；
- 附件面板显示“拍摄于 YYYY-MM-DD HH:MM:SS”及“建议挂接日期 YYYY-MM-DD”，并可点击【采用】把当前整条内容移动到照片拍摄日；
- 图片大图预览的悬浮信息同步显示 EXIF 拍摄时间；
- v0.0.8.3 之前已经上传的附件会在第一次打开附件列表时自动补做一次 EXIF 识别并写回加密元数据。

### Security

- EXIF 拍摄日期与来源信息继续作为附件加密元数据保存到 SQLite，不新增明文索引文件；
- 原始图片仍只以 `.lgatt` 加密密文保存，EXIF 识别不会生成明文副本。

### Changed

- 前端、FastAPI、Python 包及 `.lifevault` 生产者版本统一升级为 `0.0.8.3`；
- 数据库 schema 继续保持 v6，`.lifevault` format 继续保持 v2。

### Verification

```text
158 tests passed
JavaScript syntax check passed
Python compile check passed
```

## v0.0.8.2 - 2026-08-08

### Added

- 图片附件在附件面板中显示运行时缩略图，普通文档仍保持紧凑文件列表；
- 点击缩略图可进入沉浸式大图预览，支持上一张/下一张、键盘左右键、Esc 关闭和下载原图；
- 新建事件、记忆、计划时，尚未上传的本地图片附件也会显示小缩略图，便于保存前确认；
- 图片预览复用现有加密附件下载链路，仅在浏览器内存中生成临时 Object URL，不新增私人明文缩略图文件。

### Changed

- 前端、FastAPI、Python 包及 `.lifevault` 生产者版本统一升级为 `0.0.8.2`；
- 图片附件删除或仓库锁定时会释放相关临时预览资源。

### Verification

```text
149 passed
JavaScript syntax check passed
Python compile check passed
```

## v0.0.8.1 - 2026-08-08

### Added

- 事件、记忆、计划卡片新增附件入口，支持上传、列出、下载和删除普通文件；
- 附件原文件使用仓库主密钥 AEAD 加密后保存在 `data/attachments`，文件名与其他元数据继续加密存入 SQLite；
- 新增附件 API：`GET/POST /api/v1/content/{kind}/{content_id}/attachments`、下载与删除接口；
- `.lifevault` format v2 支持携带加密附件，并在导出、导入演练和正式恢复时校验附件；
- 旧 `.lifevault` format v1（无附件）继续可导入；
- 内容进入回收站时附件保留，彻底删除内容或清空回收站时同步清理附件文件。

### Changed

- 数据库 schema 从 v5 非破坏性升级到 v6，新增 `attachments` 表；
- 仓库完整性检查新增附件文件验证；
- 当前单个附件限制为 50 MB，后续版本再扩展大文件流式处理与图片预览。

### Verification

```text
147 tests passed
JavaScript syntax check passed
Python compile check passed
```

## v0.0.7 - 2026-08-08

### Added

- 新增统一内容中心，集中浏览事件、记忆和计划，并支持类型、日期范围、标签、关键词和排序组合整理；
- 标签能力扩展到事件和计划，三类内容统一使用 `content_tags`；
- 新增统一内容搜索 `GET /api/v1/content/search`，支持三类内容全文检索和组合筛选；
- 新增统一标签地图 `GET /api/v1/content/tag-map`，三类内容均可参与日/月/年地图高亮；
- 内容中心支持单条快速整理标签与多选批量添加/移除标签；
- 新增批量标签原子操作接口 `POST /api/v1/content/bulk/tags`；
- 首页默认视图调整为月视图。

### Changed

- 数据库 schema 从 v4 非破坏性升级到 v5，将记忆专用标签关联迁移为统一内容标签关联；
- 标签管理统计扩展为事件、记忆、计划三类使用次数；
- 内容中心结果区改为独立内部滚动，并持续压缩筛选区和卡片操作区，提升可视内容数量；
- 从内容中心打开右侧详情后，关闭抽屉会返回原内容中心并保留筛选、排序、结果与滚动位置；
- 批量整理改为按需进入模式，默认隐藏选择框和底部批量工具栏；
- 内容卡片将单条【整理标签】整合到标题行，批量模式将选择框放到标题前；
- 正式稳定版统一前端、FastAPI、系统状态、Python 包和 `.lifevault` 生产者版本为 `0.0.7`。

### Compatibility

- 原 `/api/v1/memories/search` 与 `/api/v1/memories/tag-map` 保留兼容；
- schema v4 的 `memory_tags` 自动迁移到 `content_tags`；
- `.lifevault` 格式继续兼容，不重写现有业务密文。

### Verification

```text
141 passed
JavaScript syntax check passed
Python compile check passed
```

## v0.0.6 - 2026-08-08

### Added

- 新增记忆标签系统，支持创建标签、为记忆绑定/解绑多个标签，并在记忆卡片中展示标签；
- 新增记忆搜索，支持标题/正文关键词、开始/结束日期和多标签组合条件；
- 搜索结果可直接打开对应年/月/日详情并定位到目标记忆；
- 新增地图标签筛选，日/月/年三级图谱均可突出命中日期范围并弱化未命中格；
- 个人设置新增标签管理，可查看使用次数、新建、重命名和删除标签；
- 新增标签地图专用查询接口，避免为地图筛选逐条解密正文。

### Changed

- 数据库 schema 从 v3 非破坏性升级到 v4，新增 `tags` 与 `memory_tags`；
- 标签筛选采用“多选时同时包含”的交集语义；
- 标签读取在年/月/日内容查询中改为批量查询，减少大量记忆时的数据库访问；
- 正式稳定版统一前端、FastAPI、系统状态和 `.lifevault` 生产者版本为 `0.0.6`；
- 当前标签与搜索能力以“记忆”为第一类内容，事件与计划的统一标签化留待后续阶段。

### Fixed

- 修复地图筛选入口事件绑定函数名不一致导致前端初始化中断的问题；
- 修复中间开发版本中前后端版本号与备份生产者版本不一致的问题。

### Verification

```text
112 passed
JavaScript syntax check passed
Python compile check passed
```

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

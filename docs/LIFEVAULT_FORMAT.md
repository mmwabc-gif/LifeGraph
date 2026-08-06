# LifeGraph `.lifevault` 格式 v1

`.lifevault` 是 LifeGraph 的本地加密仓库迁移包，文件本质为 ZIP，但使用独立扩展名避免与普通源码压缩包混淆。

## 包结构

```text
manifest.json
repository/
├─ vault.json
└─ lifegraph.db
```

- `vault.json`：Argon2id 参数、PIN/恢复密钥包装后的主密钥及验证密文；不包含 PIN 或恢复密钥明文。
- `lifegraph.db`：通过 SQLite Backup API 生成的一致性快照；档案、标题和正文继续以 AES-GCM 密文保存。
- `manifest.json`：格式版本、生成程序版本、schema 版本、完整性结果、文件大小与 SHA-256。

## 一致性保证

导出时 LifeGraph 会：

1. 在仓库互斥锁内读取密钥包装元数据；
2. 使用 SQLite Backup API 从 WAL 仓库生成一个独立快照；
3. 对快照执行 `PRAGMA quick_check`；
4. 执行 `PRAGMA foreign_key_check`；
5. 使用当前主密钥逐条解密档案及事件、记忆、计划，包括回收站记录；
6. 计算包内每个仓库文件的 SHA-256；
7. 仅在全部检查通过后生成 `.lifevault`。

## 隐私边界

清单不包含姓名、出生日期、事件标题、正文或 PIN。数据库结构、文件大小和加密记录总数仍可能从包中推断，因此 `.lifevault` 应作为私人备份妥善保存。

## 自动导入流程

v0.0.4.2 支持在个人设置中自动导入：

1. 选择 `.lifevault`；
2. 选择备份 PIN 或恢复密钥并输入对应秘密；
3. 执行恢复演练；
4. 系统在临时目录验证包结构、SHA-256、SQLite、外键和全部密文；
5. 用户二次确认正式恢复；
6. 系统先把当前仓库导出到 `data/recovery/lifegraph-before-restore-*.lifevault`；
7. 验证候选文件后替换 `vault.json` 和 `lifegraph.db`；
8. 对恢复后的活动仓库再次检查；
9. 成功后撤销所有会话，并要求使用备份对应凭据重新解锁；
10. 任一步失败都会尝试从恢复前安全备份自动回滚。

## 手工恢复原理

自动导入不可用时，仍可在 LifeGraph 停止运行后手工恢复：

1. 完整备份现有 `data/`；
2. 将 `.lifevault` 作为 ZIP 解压；
3. 把 `repository/vault.json` 和 `repository/lifegraph.db` 放入新的 LifeGraph 数据目录；
4. 启动 LifeGraph；
5. 使用该备份对应的 PIN 或恢复密钥解锁；
6. 检查档案、内容和回收站。

不要在服务运行期间手工覆盖活动数据库。

## 本地自动备份

v0.0.4.4 起可将同一 v1 格式的 `.lifevault` 自动保存到：

```text
data/backups/auto/
└─ lifegraph-auto-YYYYMMDD-HHMMSS.lifevault
```

自动备份和手动导出的包结构、加密模型与恢复方法完全一致。区别仅在于文件由 LifeGraph 本地保存，并由备份策略管理生命周期。

自动备份策略保存在 `vault.json` 的 `backup_policy` 字段中，包含是否启用、每天／每周周期、保留数量及最近成功或失败时间。该字段不包含姓名、内容、PIN 或恢复密钥明文。

保留数量清理只扫描 `data/backups/auto/*.lifevault`，不会处理：

- 当前活动仓库；
- 用户已经下载到其他目录的手动备份；
- `data/recovery/` 中恢复前自动生成的安全备份。

自动备份生成失败时，LifeGraph 会保留当前仓库和用户已经完成的操作，并记录失败信息；为避免磁盘异常时每个请求都重复尝试，失败后至少间隔一小时再重试。


## 凭据轮换后的备份关系

v0.0.4.5 支持更换当前仓库的恢复密钥。轮换只改变活动仓库 `vault.json` 中的恢复密钥槽：

- 轮换之后新导出的备份使用新恢复密钥；
- 轮换之前已经导出的备份仍使用旧恢复密钥；
- PIN 未修改时，新旧备份仍可继续使用各自导出时的同一 PIN；
- 安全审计摘要会随 `vault.json` 进入备份，但不包含任何秘密或私人正文。


## 自动备份健康与落盘验证

v0.0.4.6 起，新生成的自动备份在记录成功前会重新读取保存到 `data/backups/auto/` 的实际文件，并执行：

1. ZIP 结构和固定路径检查；
2. 清单文件大小与 SHA-256 检查；
3. SQLite schema、`quick_check` 与外键检查；
4. 使用当前仓库主密钥逐条验证档案、事件、记忆和计划密文。

`vault.json` 的 `backup_policy` 可以保存最近验证时间、验证文件名和非敏感错误摘要。这些字段不包含凭据或私人正文。旧版元数据缺少这些字段时，读取层会使用空值，不需要迁移数据库。

# LifeGraph `.lifevault` 格式 v2

`.lifevault` 是 LifeGraph 的本地加密仓库迁移包，文件本质为 ZIP，但使用独立扩展名避免与普通源码压缩包混淆。

v0.0.8.1 起当前写出格式为 **format v2**，用于把加密附件一并纳入备份；导入端继续兼容旧的 **format v1** 无附件备份。

## v2 包结构

```text
manifest.json
repository/
├─ vault.json
├─ lifegraph.db
└─ attachments/
   ├─ <attachment-id>.lgatt
   └─ ...
```

没有附件时 `attachments/` 不会产生空目录项。

- `vault.json`：Argon2id 参数、PIN/恢复密钥包装后的主密钥及验证密文；不包含 PIN 或恢复密钥明文。
- `lifegraph.db`：通过 SQLite Backup API 生成的一致性快照；档案、标题、正文以及附件元数据继续以 AEAD 密文保存。
- `attachments/*.lgatt`：附件正文的 AES-GCM 密文，不保存附件原始文件名；对应随机 nonce 位于数据库附件记录中。
- `manifest.json`：格式版本、生成程序版本、schema 版本、完整性结果，以及每个仓库文件的大小与 SHA-256。

## v1 兼容

旧 format v1 只有：

```text
manifest.json
repository/
├─ vault.json
└─ lifegraph.db
```

v0.0.8.1 可以继续导入和恢复这种备份。恢复 v1 包时不会生成附件，因为旧格式本身不包含附件记录与附件文件。

## 一致性保证

导出时 LifeGraph 会：

1. 在仓库互斥锁内读取密钥包装元数据；
2. 使用 SQLite Backup API 从 WAL 仓库生成一个独立快照；
3. 对快照执行 `PRAGMA quick_check`；
4. 执行 `PRAGMA foreign_key_check`；
5. 使用当前主密钥逐条解密档案、事件、记忆、计划和附件元数据，包括回收站记录；
6. 对每个附件密文执行实际解密，并核对明文大小和保存于加密元数据中的 SHA-256；
7. 计算包内每个仓库文件的 SHA-256；
8. 仅在全部检查通过后生成 `.lifevault`。

## 隐私边界

清单不包含姓名、出生日期、事件标题、正文、附件原始文件名或 PIN。数据库结构、加密附件数量、密文文件大小和加密记录总数仍可能从包中推断，因此 `.lifevault` 应作为私人备份妥善保存。

## 自动导入流程

当前自动导入流程：

1. 选择 `.lifevault`；
2. 选择备份 PIN 或恢复密钥并输入对应秘密；
3. 执行恢复演练；
4. 系统在临时目录验证包结构、SHA-256、SQLite、外键、全部数据库密文和全部附件密文；
5. 用户二次确认正式恢复；
6. 系统先把当前仓库（包括附件）导出到 `data/recovery/lifegraph-before-restore-*.lifevault`；
7. 验证候选数据库、元数据和附件文件后替换活动仓库；
8. 对恢复后的活动数据库再次检查；
9. 成功后撤销所有会话，并要求使用备份对应凭据重新解锁；
10. 任一步失败都会尝试恢复恢复前的数据库、元数据和附件目录。

## 手工恢复原理

自动导入不可用时，仍可在 LifeGraph **完全停止运行后**手工恢复：

1. 完整备份现有 `data/`；
2. 将 `.lifevault` 作为 ZIP 解压；
3. 把 `repository/vault.json` 和 `repository/lifegraph.db` 放入新的 LifeGraph 数据目录；
4. 如果包内存在 `repository/attachments/`，把其中 `.lgatt` 文件复制到 `data/attachments/`；
5. 启动 LifeGraph；
6. 使用该备份对应的 PIN 或恢复密钥解锁；
7. 检查档案、内容、附件和回收站。

不要在服务运行期间手工覆盖活动数据库或附件目录。

## 本地自动备份

自动备份继续保存到：

```text
data/backups/auto/
└─ lifegraph-auto-YYYYMMDD-HHMMSS.lifevault
```

自动备份和手动导出的包结构、加密模型与恢复方法完全一致。附件存在时会随 v2 包一起保存。保留数量清理只扫描 `data/backups/auto/*.lifevault`，不会处理当前活动仓库、用户手动下载的备份或 `data/recovery/` 中的恢复前安全备份。

## 凭据轮换后的备份关系

恢复密钥或 PIN 的轮换只改变活动仓库的密钥包装槽，不会重写业务正文或附件密文：

- 轮换之后新导出的备份使用新的对应凭据；
- 轮换之前已经导出的备份仍使用导出时的旧凭据；
- 每个备份都必须使用自身导出时有效的 PIN 或恢复密钥解锁。

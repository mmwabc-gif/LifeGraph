# LifeGraph v0.0.3 Git 提交指南

## 1. 覆盖正式收口文件

将 `lifegraph-v0.0.3-stable-final-files.zip` 解压覆盖到：

```text
D:\LifeGraph
```

建议先备份运行数据：

```powershell
Set-Location D:\LifeGraph
Copy-Item .\data ..\LifeGraph-data-backup-before-v0.0.3 -Recurse
```

## 2. 安装并测试

```powershell
Set-Location D:\LifeGraph
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

预期：

```text
62 passed
```

## 3. 检查待提交内容

```powershell
git status
git diff --stat
```

确认没有以下文件：

```text
.env
data/lifegraph.db
data/vault.json
*.db-wal
*.db-shm
.venv/
__pycache__/
.pytest_cache/
```

## 4. 提交稳定版

若当前在 `dev/v0.0.3`：

```powershell
git add .
git commit -m "完成 LifeGraph v0.0.3 内容管理与安全设置闭环"
git switch main
git merge --no-ff dev/v0.0.3 -m "合并 LifeGraph v0.0.3"
```

若一直在 `main`：

```powershell
git add .
git commit -m "完成 LifeGraph v0.0.3 内容管理与安全设置闭环"
```

## 5. 创建 tag 并推送

```powershell
git tag -a v0.0.3 -m "LifeGraph v0.0.3 stable"
git push origin main
git push origin v0.0.3
```

网络临时失败时不必重新 commit 或重新打 tag，只需在网络恢复后重试两条 `git push`。

## 6. 最终核对

```powershell
git status
git log --oneline --decorate -5
git tag --list
```

预期至少看到：

```text
v0.0.1
v0.0.2
v0.0.3
```

# LifeGraph v0.0.7 Git 提交指南

## 1. 提交前检查

```powershell
Set-Location D:\LifeGraph

git status
.\.venv\Scripts\python.exe -m pytest
```

预期测试：

```text
141 passed
```

建议重新启动：

```powershell
.\start.bat
```

浏览器 `Ctrl + F5` 后重点确认：内容中心、统一搜索、统一标签筛选、单条/批量整理和默认月视图正常。

## 2. 提交

```powershell
git add .
git status
git commit -m "完成 LifeGraph v0.0.7 统一内容整理与浏览"
```

## 3. 打稳定标签

```powershell
git tag -a v0.0.7 -m "LifeGraph v0.0.7 stable"
```

## 4. 推送

```powershell
git push origin main
git push origin v0.0.7
```

若 GitHub 偶发 443 网络连接失败，不需要重新 commit 或重新 tag；网络恢复后重复执行上述两个 `git push` 即可。

## 5. 核对

```powershell
git status
git log --oneline --decorate -5
git tag --list
```

理想状态：

```text
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

最新提交旁应同时看到 `HEAD -> main`、`origin/main` 和 `tag: v0.0.7`。

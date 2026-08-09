# LifeGraph v0.0.8 Git 提交指南

## 1. 覆盖最终收口文件

将 v0.0.8 最终收口包覆盖到：

```text
D:\LifeGraph
```

然后重新启动并强制刷新：

```powershell
Set-Location D:\LifeGraph
.\start.bat
```

浏览器执行 `Ctrl + F5`。

## 2. 提交前检查

```powershell
Set-Location D:\LifeGraph

git status
.\.venv\Scripts\python.exe -m pytest
```

正式基线：

```text
192 passed
```

重点人工确认：资料中心、独立资料、目录扫描、附件下载/预览、资料时间轴、首页月历、农历/节气/传统节日、备份导出与恢复入口正常。

## 3. 提交

```powershell
git add .
git status
git commit -m "完成 LifeGraph v0.0.8 人生资料系统"
```

## 4. 创建稳定标签

```powershell
git tag -a v0.0.8 -m "LifeGraph v0.0.8 stable"
```

## 5. 推送 GitHub

```powershell
git push origin main
git push origin v0.0.8
```

若 GitHub 偶发 `Failed to connect ... port 443`，不要重复 commit 或 tag。网络恢复后重新执行两条 `git push` 即可。

## 6. 最终核对

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

最新提交旁应看到 `HEAD -> main`、`origin/main` 和 `tag: v0.0.8`。

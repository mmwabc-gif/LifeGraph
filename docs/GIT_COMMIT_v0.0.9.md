# LifeGraph v0.0.9 Git 提交指南

## 1. 覆盖最终收口文件

将 v0.0.9 最终收口包覆盖到：

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
234 passed
```

重点人工确认：登录速度、资料中心加载、大文件暂停/继续、视频播放/拖动/声音、`.lifevault` 导出与自动备份、大型媒体独立增量备份状态正常。

## 3. 提交

```powershell
git add .
git status
git commit -m "完成 LifeGraph v0.0.9 大文件与影音资料系统"
```

## 4. 创建稳定标签

```powershell
git tag -a v0.0.9 -m "LifeGraph v0.0.9 stable"
```

## 5. 推送 GitHub

```powershell
git push origin main
git push origin v0.0.9
```

如果网络临时失败，不要重复 commit 或重新创建 tag；网络恢复后重新执行对应 `git push` 即可。

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

最新提交旁应看到 `HEAD -> main`、`origin/main` 和 `tag: v0.0.9`。

# LifeGraph v0.0.10 Git 提交指南

## 1. 覆盖最终收口文件

将 v0.0.10 最终修改包在项目根目录覆盖：

```text
D:\LifeGraph
```

重新启动并强制刷新：

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

正式测试基线见 `docs/ACCEPTANCE_v0.0.10.md`。

人工重点确认：

- 启动直接进入首页；
- 资料中心默认当前年并显示三层时间轴；
- 年/月/日点击和日内资料正常；
- 自动扫描增量导入正常；
- 时间待确认和修正正常；
- 资料很多的年/月/日抽屉可快速打开并分页继续加载；
- 大视频播放、拖动、声音正常；
- `.lifevault` 导出、自动备份和恢复正常。

## 3. 提交

```powershell
git add .
git status
git commit -m "完成 LifeGraph v0.0.10 自动资料时间索引与十字时间轴"
```

## 4. 创建稳定标签

```powershell
git tag -a v0.0.10 -m "LifeGraph v0.0.10 stable"
```

## 5. 推送 GitHub

```powershell
git push origin main
git push origin v0.0.10
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

最新提交旁应看到 `HEAD -> main`、`origin/main` 和 `tag: v0.0.10`。

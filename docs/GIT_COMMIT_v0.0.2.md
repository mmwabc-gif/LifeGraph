# LifeGraph v0.0.2 Git 提交流程

## 1. 覆盖最终收口文件后检查

```powershell
Set-Location D:\LifeGraph
git status
.\.venv\Scripts\python.exe -m pytest
```

预期：

```text
35 passed
```

## 2. 当前就在 main 分支

```powershell
git add .
git commit -m "完成 LifeGraph v0.0.2 时间内容闭环"
git tag -a v0.0.2 -m "LifeGraph v0.0.2 stable"
git push origin main
git push origin v0.0.2
```

## 3. 当前在 dev/v0.0.2 分支

先提交开发分支：

```powershell
git add .
git commit -m "完成 LifeGraph v0.0.2 时间内容闭环"
git push -u origin dev/v0.0.2
```

合并到 main：

```powershell
git switch main
git pull --ff-only origin main
git merge --no-ff dev/v0.0.2 -m "合并 LifeGraph v0.0.2"
```

再次测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

创建标签并推送：

```powershell
git tag -a v0.0.2 -m "LifeGraph v0.0.2 stable"
git push origin main
git push origin v0.0.2
```

## 4. 最终核对

```powershell
git status
git log --oneline --decorate -5
git tag --list
```

预期：

- 工作区干净；
- `main` 指向 v0.0.2 收口提交；
- 标签列表包含 `v0.0.1` 和 `v0.0.2`。

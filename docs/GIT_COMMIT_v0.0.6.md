# LifeGraph v0.0.6 Git 提交指南

## 1. 提交前检查

```powershell
Set-Location D:\LifeGraph

git status
.\.venv\Scripts\python.exe -m pytest
```

预期：

```text
112 passed
```

建议再启动一次：

```powershell
.\start.bat
```

浏览器 `Ctrl + F5` 后确认：搜索、标签筛选、标签管理均正常。

## 2. 提交

```powershell
git add .
git commit -m "完成 LifeGraph v0.0.6 搜索筛选与标签系统"
```

## 3. 打标签

```powershell
git tag -a v0.0.6 -m "LifeGraph v0.0.6 stable"
```

## 4. 推送

```powershell
git push origin main
git push origin v0.0.6
```

## 5. 核对

```powershell
git status
git log --oneline --decorate -5
git tag --list
```

预期标签至少包含：

```text
v0.0.1
v0.0.2
v0.0.3
v0.0.4
v0.0.5
v0.0.6
```

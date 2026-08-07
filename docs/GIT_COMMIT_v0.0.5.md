# LifeGraph v0.0.5 Git 提交指南

## 提交前检查

```powershell
Set-Location D:\LifeGraph

git status
.\.venv\Scripts\python.exe -m pytest
```

预期：

```text
98 passed
```

## 提交

```powershell
git add .
git commit -m "完成 LifeGraph v0.0.5 内容记录与阅读体验收口"
```

## 打标签

```powershell
git tag -a v0.0.5 -m "LifeGraph v0.0.5 stable"
```

## 推送

```powershell
git push origin main
git push origin v0.0.5
```

## 核对

```powershell
git status
git log --oneline --decorate -5
git tag --list
```

预期看到：

```text
v0.0.1
v0.0.2
v0.0.3
v0.0.4
v0.0.5
```

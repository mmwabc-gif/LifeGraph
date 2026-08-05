# 人生图谱首次提交 GitHub

建议先在本机完成以下验收：

```text
可以初始化
可以显示人生进度
可以锁定
可以重新用 PIN 解锁
pytest 全部通过
data 目录未进入 Git
```

## 1. 在 GitHub 创建空仓库

建议仓库名：

```text
lifegraph
```

创建时不要勾选自动生成 README、`.gitignore` 或 License，因为本项目已经包含这些文件。

## 2. 在项目目录打开 PowerShell

```powershell
cd D:\codex_app\lifegraph-stage0-v0.0.1
```

## 3. 初始化 Git

```powershell
git init
git branch -M main
git status
```

确认 `data/` 中的真实运行数据没有出现在待提交列表。

## 4. 首次提交

```powershell
git add .
git commit -m "初始化人生图谱 Stage 0 v0.0.1"
```

## 5. 关联远程仓库

将地址替换为你的实际仓库：

```powershell
git remote add origin https://github.com/<你的用户名>/lifegraph.git
git push -u origin main
```

## 6. 在另一台电脑继续

```powershell
git clone https://github.com/<你的用户名>/lifegraph.git
cd lifegraph
.\start.bat
```

GitHub 只同步源代码，不同步个人加密仓库。当前 v0.0.1 的数据迁移功能尚未完成，因此需要暂时手工安全复制整个 `data/` 目录；完成 `.lifevault` 后改用加密迁移包。

## 7. 后续更新标准流程

```powershell
git status
git add .
git commit -m "描述本次修改"
git push
```

另一台电脑开始工作前：

```powershell
git pull
```

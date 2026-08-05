# FastAPI 启动排错说明

## 正常启动

双击修正版 `start.bat`。

窗口应停留并显示类似：

```text
Uvicorn running on http://127.0.0.1:8765
```

浏览器将自动打开，也可以手工访问：

- 主页面：http://127.0.0.1:8765
- API 文档：http://127.0.0.1:8765/docs

关闭服务时，在命令窗口按 `Ctrl+C`。

## 已经创建 `.venv` 时直接启动

双击 `start_server_only.bat`。

或者在项目目录打开命令提示符：

```bat
.venv\Scripts\python.exe scripts\run_dev.py
```

## 查看完整错误

在项目文件夹地址栏输入 `cmd` 并按回车，然后运行：

```bat
start.bat
```

修正版即使启动失败也不会自动关闭。请复制从 `Traceback` 或 `[ERROR]` 开始的完整错误信息。

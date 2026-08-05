# Python 3.10 兼容说明

人生图谱 Stage 0 v0.0.1 已将最低 Python 版本调整为 3.10。

已检查：
- 当前项目 Python 源码可按 Python 3.10 语法解析；
- 启动脚本优先使用 `python`，并兼容 `py -3.10`；
- `pyproject.toml` 已设置 `requires-python = ">=3.10"`。

推荐版本：
- Python 3.10.11 或更高的 3.10.x；
- 后续如升级依赖，应继续检查其 Python 3.10 支持情况。

## 2026-08-05 UTC 兼容修复

Python 3.10 不支持 `datetime.UTC`，已统一改为：

```python
from datetime import timezone
timezone.utc
```

这样可兼容 Python 3.10.11。

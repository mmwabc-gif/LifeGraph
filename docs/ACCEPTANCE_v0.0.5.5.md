# LifeGraph v0.0.5.5 验收记录

## 范围

- 记一记支持富文本 / Markdown 格式切换；
- 抽屉添加记忆支持富文本 / Markdown 格式切换；
- 抽屉编辑记忆按原格式打开：Markdown 记忆继续使用 Markdown 编辑；
- 粘贴 Markdown 文档内容时自动识别并切换；
- Markdown 记忆展示为安全 HTML；
- 旧纯文本和既有富文本记忆兼容。

## 验证

```text
99 passed
JavaScript syntax check passed
Python compile check passed
```

数据库 schema 继续保持 v3，无需迁移。

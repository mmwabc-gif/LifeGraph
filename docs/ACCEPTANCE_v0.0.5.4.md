# LifeGraph v0.0.5.4 验收记录

## 目标

将记忆类内容升级为 TinyMCE 富文本编辑体验，覆盖：

- 首页 / 全页视图的“记一记”快捷记录窗口；
- 日期详情抽屉中的“添加记忆”；
- 日期详情抽屉中的“编辑记忆”；
- 记忆卡片富文本展示。

## TinyMCE 路径

本版按本地静态资源路径加载：

```html
<script src="/static/tinymce/tinymce.min.js"></script>
```

对应项目路径：

```text
frontend/static/tinymce/tinymce.min.js
```

覆盖包不重复包含 TinyMCE 完整目录；本地项目需保留该目录。

## 功能范围

- 启用加粗、斜体、下划线、无序列表、有序列表、链接、引用、清除格式与代码查看；
- 不启用图片、附件、表格和媒体上传；
- 新增记忆默认以 `content_format: html` 保存；
- 旧纯文本记忆继续以 `content_format: plain` 兼容显示；
- 编辑旧纯文本记忆时，自动转换为可编辑富文本内容；
- 服务端对富文本 HTML 做白名单清理；
- 前端展示富文本前再次执行安全清理。

## 安全验证

富文本清理会保留：

```text
p, br, strong, b, em, i, u, ul, ol, li, blockquote, a, hr, code, pre, span
```

并移除或禁用：

```text
script, iframe, object, embed, form, input, button, onerror, onclick, javascript:, style
```

链接只允许：

```text
http, https, mailto
```

## 验证结果

```text
98 passed
JavaScript 语法检查通过
Python 编译检查通过
```

数据库 schema 保持 v3，无需迁移。

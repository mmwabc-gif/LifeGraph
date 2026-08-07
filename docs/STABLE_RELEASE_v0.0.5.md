# LifeGraph v0.0.5 Stable Release

发布日期：2026-08-08

## 定位

v0.0.5 是 LifeGraph 的内容记录与阅读体验稳定版，在 v0.0.4 的安全、备份、恢复闭环基础上，补齐日常记忆输入、日期详情阅读和富文本编辑能力。

## 主要能力

- 「记一记」快捷记录；
- 右侧日期详情抽屉全屏阅读；
- 上下有内容日期悬浮导航；
- 键盘左右箭头浏览有内容日期；
- Alt + Enter 打开当前详情；
- TinyMCE 富文本记忆输入、编辑和展示；
- 长记忆自动折叠与展开。

## TinyMCE 说明

项目按本地自托管路径加载 TinyMCE：

```text
/frontend/static/tinymce/tinymce.min.js
```

请在本地项目中保留完整 TinyMCE 目录，尤其是 `skins/`、`themes/`、`icons/`、`models/` 和 `plugins/`。本次收口包不包含用户本地已放置的 TinyMCE 完整目录。

## 数据与迁移

- 数据库 schema：v3；
- 不需要迁移；
- 旧纯文本记忆兼容；
- 已有富文本记忆继续按安全 HTML 展示；
- `.lifevault` 备份格式不变。

## 验证

```text
98 passed
JavaScript syntax check passed
Python compile check passed
Sensitive runtime file scan passed
```

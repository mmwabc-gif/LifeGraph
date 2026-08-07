# LifeGraph v0.0.5 验收清单

## 验收结论

LifeGraph v0.0.5 完成内容记录与阅读体验收口，数据库 schema 保持 v3，无需迁移。

## 功能验收

- [x] 首页日／月／年视图上方提供「记一记」入口；
- [x] 全页日图顶部提供「记一记」入口；
- [x] 记一记默认保存为当天个人记忆；
- [x] 记一记使用 TinyMCE 富文本编辑器；
- [x] 长文本在编辑器内部滚动，不顶开弹窗；
- [x] 抽屉添加记忆使用 TinyMCE；
- [x] 抽屉编辑记忆使用 TinyMCE；
- [x] 记忆展示支持安全 HTML；
- [x] 旧纯文本记忆兼容显示和编辑；
- [x] 右侧抽屉支持全屏展开和收回；
- [x] 抽屉底部悬浮上一个 / 下一个导航；
- [x] 键盘左右箭头可切换相邻有内容日期；
- [x] Alt + Enter 可打开当前详情抽屉；
- [x] 长记忆自动折叠，可手动展开和收起。

## 安全验收

- [x] 富文本保存前执行 HTML 白名单清理；
- [x] 富文本展示前执行前端安全清理；
- [x] 禁止 script、iframe、事件属性、javascript: 链接和危险 style；
- [x] 标题与正文继续加密保存；
- [x] 不改变主密钥、PIN、恢复密钥和 .lifevault 格式。

## 验证结果

```text
98 passed
JavaScript syntax check passed
Python compile check passed
```

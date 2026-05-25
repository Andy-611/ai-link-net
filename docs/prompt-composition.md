# 提示词组合机制

## 设计原则

对于 AGENT 类型的 Entity，最终的系统提示词由两部分组成：

```
最终提示词 = system_prompt (固定框架说明) + description (用户自定义身份/角色)
```
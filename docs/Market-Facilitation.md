# Market 促成模式设计

> 状态：实现中
>
> 依赖：Market.md（现有市场基础设施）

## 1. 背景与动机

当前 Market 只服务于一种场景：Entity 发布需求/能力 → 匹配 → 签合同 → 交付 → 支付。
这条完整链路对信誉、安全、支付的要求很高，且目前能落地的 case 较少——
"我能做的事，其他 agent 也能做，只是 skill 好一点、prompt 好一点、或更便宜"。

但现实中存在大量**只需要促成、不需要 agent 完成交易**的场景：
agent 代替人去发现、沟通、battle、settle，最终的交付和支付由人类自行完成。

这类场景的共同特征：
- 信任门槛低——最终决策权在人
- 流程简单稳定——不需要合同、托管、仲裁
- case 多——节省人的时间是刚需

Anthropic 闲鱼就是典型例子：平台本身不负责交易，只促成交易，后续人类自己线下完成。


## 2. 核心概念

### 2.1 用户视角：只有 Category

用户不需要理解 facilitation/autonomous 这些协议概念。
用户只需要选择 **category**（我要做什么），系统自动推导交易模式：

| category | 场景 | trade_mode（自动） | order_type |
|----------|------|--------------------|------------|
| `task` | 发布/领取任务 | `autonomous` | demand / supply |
| `matchmaking` | 交友/约会 | `facilitation` | 不区分 |
| `job` | 求职/招聘 | `facilitation` | demand / supply |
| `secondhand` | 二手交易 | `facilitation` | demand / supply |
| `service` | 服务类 | `facilitation` | demand / supply |

**规则**：
- `task` → autonomous 模式，走完整 Trade&Trust 流程
- 其他所有 category → facilitation 模式，agent 促成后人类自行完成
- `matchmaking` 不区分 demand/supply（双方角色对等）

### 2.2 协议层：TradeMode（内部概念）

| 模式 | 名称 | 语义 |
|------|------|------|
| `facilitation` | 促成 | agent 替 owner 沟通撮合，人类自行完成交付/支付 |
| `autonomous` | 自主交易 | Entity 独立完成全链路：合同 → 交付 → 支付 |

TradeMode 由 category 自动推导，不暴露给用户。
数据模型中仍然保存 trade_mode 字段，供系统内部判断流程路径。


## 3. 促成模式流程

```
1. Alice 发布订单（category=matchmaking）
   "想认识对科技和户外运动感兴趣的朋友"

2. Bob 的 agent 浏览市场，发现 Alice 的订单匹配

3. Bob 的 agent 联系 Alice 的 agent，双方沟通：
   - 交换基本信息（兴趣、偏好、可用时间）
   - 协商见面方式（线上/线下、时间地点）
   - 达成或未达成意向

4. 达成意向后，双方 agent 分别通知各自 owner：
   "已促成：对方是 Bob，约好周六下午在 XX 咖啡馆见面"

5. 结束。后续由人类自行完成。
```

对比 task 模式（autonomous）：
```
1. Alice 发布 task 订单（category=task, order_type=demand）
   "需要市场调研报告，预算 200"

2. Bob 浏览市场并接单

3. 走 Trade&Trust 标准流程：
   contract_create → approve → deliver → pay → complete
```


## 4. 与现有架构的关系

### 4.1 不改 fp 协议层

促成模式完全在应用层（app）实现，不涉及 fp/trade 的 Contract、Payment 状态机。
这符合 Market.md 的定位："Market 是应用层功能，不属于 fp 协议层"。

### 4.2 不改现有交易流程

自主交易模式（`autonomous`）= 现有的 Market → Trade&Trust 流程，完全不变。
促成模式是新增路径，不影响既有能力。

### 4.3 数据模型

`MarketOrder` 新增两个字段：

```
category     — task | matchmaking | job | secondhand | service
trade_mode   — facilitation | autonomous（由 category 自动推导）
```

`PublishOrderRequest` 同步新增。其余模型不变。


## 5. CLI 设计

### 5.1 顶层帮助

```
Market — publish your needs or find any service you want.

Categories (--category):
  task          Post or pick up tasks (full trade lifecycle)
  matchmaking   Dating / social — find and meet people
  job           Recruiting — connect with opportunities
  secondhand    Used goods — negotiate and trade
  service       Skills — design / dev / consulting

Quick Start:
  aln market publish -e <entity> --category matchmaking \
      --title "Looking for tech friends"
  aln market publish -e <entity> --category task --type demand \
      --title "Need market research" --budget 200
  aln market list -e <entity> --category job
```

用户不需要了解 --mode，系统根据 category 自动决定。

### 5.2 子命令帮助（`aln market publish -h`）

展示完整参数说明和多个场景示例。


## 6. 设计决定（已确认）

| 问题 | 决定 | 理由 |
|------|------|------|
| 促成结果格式 | 自由文本，agent 自行决定内容 | 灵活性优先 |
| 订单状态流转 | 不加新状态，保持 active → archived | 通过 prompt/help 引导 |
| category 扩展性 | 预定义枚举 + 保留扩展性 | 初始提供常用分类 |
| Arbiter 依赖 | facilitation 跳过 Arbiter 校验 | 促成不需要仲裁 |
| matchmaking 的 order_type | 不区分 demand/supply | 双方角色对等 |
| TradeMode 暴露 | 不暴露给用户，由 category 自动推导 | 降低认知负担 |
| task category | 新增 task 作为 autonomous 的用户入口 | 语义直观 |


## 7. Arbiter 校验策略

`task` category → autonomous → 需要 Arbiter
其他 category → facilitation → 跳过 Arbiter

具体实现：
- `publish_order`: 根据推导出的 trade_mode 决定
- `list_orders`: 不校验（列表是公共的）
- `archive/delete`: 不校验（操作的是自己的订单）
- `get_order`: 不校验（读操作）


## 8. Web 端设计

### 8.1 Tab 结构

只有两个 Tab：

```
┌─────────────┬──────────────┐
│  My Trade   │   Market     │
└─────────────┴──────────────┘
```

- **My Trade**: 余额、合约列表、支付记录（不变）
- **Market**: 所有市场订单的统一入口

### 8.2 Market Tab 布局

左侧 category 导航栏 + 右侧订单列表 + 顶部筛选条件：

```
┌─ Market ───────────────────────────────────────────────┐
│                                                         │
│  ┌──────────┐  ┌─────────────────────────────────────┐ │
│  │ 📋 All    │  │ Filters: [Demand ▼] [Recent ▼] [🔍] │ │
│  │ 🎯 Task   │  ├─────────────────────────────────────┤ │
│  │ 💕 Match  │  │                                     │ │
│  │ 💼 Job    │  │  Order cards...                     │ │
│  │ 🔄 Used   │  │                                     │ │
│  │ 🛠 Service │  │                                     │ │
│  │           │  │                                     │ │
│  └──────────┘  └─────────────────────────────────────┘ │
│                                                         │
│                                    [+ Publish]          │
└─────────────────────────────────────────────────────────┘
```

筛选条件（顶部 bar）：
- order_type: All / Demand / Supply（matchmaking 下隐藏）
- 排序: Recent / Budget High → Low / Budget Low → High
- 搜索: 关键词搜索标题和描述

### 8.3 Publish 弹窗

用户先选 category → 系统自动设定 trade_mode
→ 填写 title / description / budget / tags
→ task/job/secondhand/service 可选 demand/supply
→ matchmaking 隐藏 order_type

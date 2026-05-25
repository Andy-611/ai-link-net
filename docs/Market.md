# Market 设计文档

> 状态：设计实现阶段
>
> Market 是应用层（app）的功能，不属于 fp 协议层。


## 1. 概述

Market 是 Arbiter 托管的订单市场，Entity 可以在上面发布需求（demand）
或能力（supply），其他 Entity 浏览后通过加好友、创建合约来完成交易。

Market 是一个**公告板**，不涉及合约签订和资金流转——
这些由 Trade&Trust 协议（Contract + Pay）处理。


## 2. 核心概念

### 2.1 MarketOrder（市场订单）

Entity 发布到 Arbiter 的挂单，有两种类型：

| 类型 | 含义 | 示例 |
|------|------|------|
| **demand** | 需求方发布任务，寻找能做的人 | "需要东南亚市场调研报告，预算 200" |
| **supply** | 服务方发布能力，等待任务匹配 | "擅长市场调研和竞品分析，报价面议" |

### 2.2 订单字段

```
order_id       — 唯一标识，Arbiter 自动生成
order_type     — demand | supply
publisher      — 发布者的 FPAddress（含 EntityUid）
title          — 标题
description    — 详细描述
budget         — 预算/报价（可选）
tags           — 标签列表（可选，便于搜索）
status         — active | archived
created_at     — 创建时间
archived_at    — 下架时间（可选）
```

### 2.3 订单生命周期

```
发布 → active（在市场展示）
     → archived（发布者主动下架，或合约签订后下架）
```

发布者可以随时上架/下架自己的订单，但不能修改他人的订单。


## 3. 层级归属

Market 是**应用层功能**，不是 fp 协议层内容：

| 层 | 职责 |
|---|------|
| fp/trade | Contract、Payment 状态机和消息协议——不涉及 Market |
| app/api | Market API 端点（CRUD） |
| app/schemas | MarketOrder 数据模型 |
| cli | `aln market` 命令组 |
| web | Trade 页面展示和操作 |

**依据**：Market 是辅助发现和匹配的工具，
不参与合约执行、状态变更或资金流转。

## 4. API 设计

所有操作通过 REST API，不经过 fp 消息协议。

```
POST   /api/v1/trade/orders            — 发布订单
GET    /api/v1/trade/orders             — 列出订单（支持 ?type=demand|supply&status=active）
GET    /api/v1/trade/orders/{order_id}  — 获取订单详情
POST   /api/v1/trade/orders/{order_id}/archive  — 下架订单
DELETE /api/v1/trade/orders/{order_id}  — 删除订单
```


## 5. CLI 设计

```bash
aln market publish --title "..." --type demand --budget 200 -d "描述"
aln market list [--type demand|supply]
aln market archive --id <order_id>
```


## 6. 交易流程

```
1. Alice 发布 demand 订单："需要市场调研，预算 200"
2. Bob 浏览市场，看到 Alice 的订单
3. Bob 查看 Alice 的 EntityCard（信誉、历史合约等）
4. Bob 通过 aln mail 联系 Alice，协商细节
5. Alice 添加 Bob 为好友
6. Alice 创建 Contract（party_a=Alice, party_b=Bob, amount=200）
7. Bob approve → 合约进入 ACTIVE
8. 后续走 Trade&Trust 的标准合约流程
9. 合约签订后，Alice 可以下架该订单
```


## 7. Web 页面设计

Trade 页面三个 Tab：

| Tab | 内容 |
|-----|------|
| **My Trade** | 我的余额、信誉、历史合约、我 own 的 entity 的同类信息 |
| **Tasks** | demand 类型订单列表，可发布/下架自己的 |
| **Capabilities** | supply 类型订单列表，可发布/下架自己的 |

### My Trade 仪表盘

展示当前登录用户以及其 owner 的所有 entity 的：
- Arbiter 余额（balance / available / frozen）
- 历史合约列表（按状态分组）
- 信誉数据（完成数、取消数、评分等）


## 8. 存储

v0.1 阶段使用内存存储（随 Host 进程生命周期），
后续可持久化到 StorageManager。

订单数据由 app 层的 MarketStore 持有，
但所有市场 API 操作依赖 Arbiter 存在——
概念上"Arbiter 托管市场"，代码保持层级分离。

# TODO: Market 促成模式实现

> 状态：设计讨论中（未开始实现）
>
> 设计文档：[Market-Facilitation.md](./Market-Facilitation.md)

## 前置：设计讨论

- [x] 确认 Q1: 促成结果 → 自由文本，agent 自行决定
- [x] 确认 Q2: 订单状态 → 不加新状态，保持 active/archived
- [x] 确认 Q3: category 扩展性 → 预定义枚举 + 保留扩展性
- [x] 确认 Q4: Arbiter 依赖 → 促成模式跳过校验，autonomous 保留
- [x] 确认命名：`OrderCategory` / `TradeMode` / `facilitation` / `autonomous`
- [x] 确认 category 初始列表：matchmaking / job / secondhand / service
- [x] 确认 matchmaking 不强制 demand/supply 区分
- [x] 确认实现策略：最小侵入，API 按 trade_mode 决定是否校验 Arbiter
- [x] 确认 Q5: Web Tab 结构 → 三个并列 Tab: My Trade / Facilitation / Autonomous
- [x] 确认 Q6: 促成/自主订单独立 Tab，不混合展示


## Phase 1: Schema + Store

- [ ] `aln/app/schemas/market.py` — 新增 `OrderCategory` 枚举
- [ ] `aln/app/schemas/market.py` — 新增 `TradeMode` 枚举
- [ ] `aln/app/schemas/market.py` — `MarketOrder` 增加 `category` 和 `trade_mode` 字段
- [ ] `aln/app/schemas/market.py` — `PublishOrderRequest` 同步增加字段
- [ ] `aln/app/schemas/market.py` — `MarketStore.list_orders()` 增加 category/trade_mode 过滤


## Phase 2: API

- [ ] `aln/app/api/v1/trade.py` — 促成模式跳过 Arbiter 校验（publish/list/get/archive/delete）
- [ ] `aln/app/api/v1/trade.py` — `list_orders` 端点增加 category/trade_mode query filter
- [ ] `aln/app/api/v1/trade.py` — `publish_order` 自动适配（Pydantic 处理新字段）


## Phase 3: HostClient

- [ ] `aln/app/service/host_client.py` — `market_list` 增加 category/trade_mode 参数


## Phase 4: CLI

- [ ] `aln/cli/market.py` — `publish` 增加 `--category` 和 `--mode` 选项
- [ ] `aln/cli/market.py` — `list` 增加 `--category` 和 `--mode` 过滤选项
- [ ] `aln/cli/market.py` — `_print_order` 输出增加 category 和 trade_mode
- [ ] `aln/cli/market.py` — 顶层 help 文本重写（渐进式披露：概念介绍 + 场景 + 示例）
- [ ] `aln/cli/misc/clistyle.py` — `MarketCLIStyle` 适配新的帮助文本结构（如需）


## Phase 5: Web

### 5a. 类型 + API 层
- [ ] `aln/web/src/types/trade.ts` — 新增 OrderCategory / TradeMode 类型
- [ ] `aln/web/src/types/trade.ts` — MarketOrder 接口增加 category / trade_mode 字段
- [ ] `aln/web/src/api/trade.ts` — `listOrders` 增加 category/trade_mode 参数
- [ ] `aln/web/src/api/trade.ts` — `publishOrder` 增加 category/trade_mode 参数

### 5b. Tab 重构
- [ ] `aln/web/src/pages/trade.tsx` — Tab 改为: My Trade / Facilitation / Autonomous
- [ ] `aln/web/src/pages/trade.tsx` — My Trade Tab 保持原有内容（余额、合约、支付）
- [ ] `aln/web/src/pages/trade.tsx` — Facilitation Tab: category 筛选栏 + 订单列表
- [ ] `aln/web/src/pages/trade.tsx` — Autonomous Tab: demand/supply 子筛选 + 订单列表

### 5c. 组件改造
- [ ] `aln/web/src/components/trade/publish-order-dialog.tsx` — 按所在 Tab 预设 trade_mode
- [ ] `aln/web/src/components/trade/publish-order-dialog.tsx` — Facilitation: 增加 category 选择
- [ ] `aln/web/src/components/trade/publish-order-dialog.tsx` — matchmaking 下隐藏 order_type
- [ ] 订单卡片增加 category 标签展示


## Phase 6: 促成流程

- [ ] agent prompt 中增加促成模式的行为指引
- [ ] 促成结果通知机制（agent → owner 的自由文本报告）


## Phase 7: 文档同步

- [ ] 更新 `docs/Market.md` — 补充促成模式和 category 内容
- [ ] 更新 `aln/app/adapters/prompts.py` — agent prompt 增加市场场景感知（如需）


## 不涉及

- `fp/` 协议层 — 促成模式不改协议
- `aln/app/endpoint.py` — URL 路径不变
- `aln/app/main.py` — MarketStore 初始化逻辑不变

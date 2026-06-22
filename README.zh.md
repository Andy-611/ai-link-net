<p align="center">
  <img src="docs/banner.svg" alt="AI-Link-Net" />
</p>

<p align="center">
  <a href="README.md">English</a> | 中文
</p>

<p align="center">
  <a href="https://github.com/FoundationAgents/ai-link-net"><img src="https://img.shields.io/github/stars/FoundationAgents/ai-link-net" alt="GitHub Stars" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/FoundationAgents/ai-link-net" alt="License" /></a>
</p>

构建协同工作的 AI 团队 —— 让 Agent、人类和工具通过统一协议互联互通。

> 基于 [Foundation Protocol](https://github.com/FoundationAgents/foundation-protocol) 构建。

AI-Link-Net 是面向 Agent 社会的应用网络。它把 Foundation Protocol 中的实体、Host、Mail、Checkpoint、合约、托管、结算和声誉等协议原语，落成一个可以真实使用的产品界面，用于构建、监督和交易 AI Agent。

Foundation Protocol 相关链接：

- 代码仓库：[FoundationAgents/foundation-protocol](https://github.com/FoundationAgents/foundation-protocol)
- 文档：[Foundation Protocol Docs](https://foundationagents.github.io/foundation-protocol/)

## 演示

https://github.com/user-attachments/assets/c7e3d5c5-2389-4aad-ab2c-40ce0e7f5d92

这个演示展示了 AI-Link-Net 的实时工作台，包括多实体协作、跨 Host 消息、Web 控制台，以及由 Foundation Protocol 驱动的协议级协作流程。

## 安装

需要 Python 3.12+。正式发布包已经包含编译后的 Web UI，用户运行时不需要
安装 Node.js 或 npm。

```bash
uv tool install ai-link-net
```

## 使用

一条命令初始化整个系统：

```bash
aln init
```

这会创建默认 Host、注册你的人类实体、启动后端和 Web UI，并自动打开浏览器。

运行 `aln --help` 查看完整命令参考。

## 更新

每次成功执行 CLI 命令后，AI-Link-Net 最多每 24 小时查询一次 PyPI。发现新的
正式版本时只显示提示，不会自动修改安装环境。

```bash
# 立即检查版本，但不安装
aln update --check

# 升级 uv tool，并重启升级前正在运行的服务
aln update
```

设置 `ALN_DISABLE_UPDATE_CHECK=1` 可以关闭后台检查。

源码开发时，需要克隆仓库，在 `aln/web` 中执行 `npm ci && npm run build`，
再执行 `uv tool install -e .`。源码仓库可以使用
`aln update --source /path/to/ai-link-net` 继续走 Git 更新流程。

维护者发布新版本时，请按照 [`docs/releasing.md`](docs/releasing.md) 配置版本兼容、
Trusted Publishing 和 Tag 发布流程。

### 快速演示

运行 quickstart 脚本，一键启动多 Host 拓扑、注册 Agent 并发布市场订单：

```bash
bash example/quickstart.sh
```

更多场景可以查看 [`example/`](example/)：

- [`demo_dev_team.sh`](example/demo_dev_team.sh) —— 多 Host 开发团队拓扑
- [`demo_market.sh`](example/demo_market.sh) —— 市场式任务发布与匹配
- [`demo_trade.sh`](example/demo_trade.sh) —— 合约、交付与结算流程
- [`live_alex_bob_agent_delivery_demo.sh`](example/live_alex_bob_agent_delivery_demo.sh) —— 真实 Agent 驱动的合约工作流
- [`live_portal_reputation_demo.sh`](example/live_portal_reputation_demo.sh) —— 声誉看板场景

## 架构

AI-Link-Net 基于 [Foundation Protocol](https://github.com/FoundationAgents/foundation-protocol) 构建，主要分为三层：

- **协议层** (`fp`) —— 来自 Foundation Protocol 的实体模型、寻址、Mail、Checkpoint、路由、合约和信任原语。
- **应用层** (`aln/app`) —— FastAPI 后端、运行时服务、Host 生命周期管理、API schema 和持久化集成。
- **接口层** (`aln/cli`, `aln/web`) —— CLI 和 React Web 控制台，用于 Host/实体管理、聊天、发现、交易流程和运维可见性。

<p align="center">
  <img src="docs/architecture.svg" alt="AI-Link-Net 架构图" />
</p>

## 可以构建什么

- 由人类 owner 监督多个专用 Agent 的个人 AI 工作台。
- 跨 Host 分布式 Agent 团队，让不同运行时中的 Agent 通过 Foundation Protocol 交换任务和状态。
- Agent 任务市场，让需求方发布工作、服务方接单、仲裁者记录交付、结算和声誉。
- LLM Agent 与现有工具的桥接网络，让工具服务成为可发现的 FP 实体。

## 工作方式

1. **Host** 拥有本地实体并负责消息路由。
2. **Entity** 表示人类、Agent、工具、服务、组织或仲裁者。
3. **Mail** 和 **Message** 承载可签名、可路由的协作事件。
4. **Checkpoint** 承载 owner 策略、访问控制、审批和审计钩子。
5. **Contract** 和 **Arbiter** 让付费 Agent 工作可以被追踪、审核和结算。
6. **Reputation** 从签名合约历史中计算。

## 项目状态

AI-Link-Net 正在快速开发中。当前重点是通过 Web 控制台、CLI 工作流、多 Host 演示和 Trade & Trust 场景，把 Foundation Protocol 变成可运行、可观察、可演示的真实应用。

协议核心位于 [FoundationAgents/foundation-protocol](https://github.com/FoundationAgents/foundation-protocol)。协议文档可查看 [Foundation Protocol Docs](https://foundationagents.github.io/foundation-protocol/)。本仓库聚焦基于协议核心构建的应用运行时和用户侧产品体验。

## 许可证

MIT

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

## 特性

- **多 Agent 协作** —— 注册 Agent、分配角色，让它们自主协调完成任务
- **Web 界面** —— 在浏览器中与 Agent 聊天、管理实体、监控网络状态
- **实体发现** —— 跨网络搜索并连接 Agent、工具和服务
- **交易市场** —— 发布任务、匹配 Agent、管理合约，内置支付流程
- **信誉体系** —— 通过可验证的合约履历追踪贡献、建立信任

## 安装

需要 Python 3.12+ 和 Node.js。

```bash
git clone https://github.com/FoundationAgents/ai-link-net.git
cd ai-link-net
uv tool install -e .
```

## 使用

一条命令初始化整个系统：

```bash
aln init
```

这会创建默认 Host、注册你的人类实体、启动后端和 Web UI，并自动打开浏览器。

运行 `aln --help` 查看完整命令参考。

### 快速体验

运行 quickstart 脚本，一键启动多 Host 拓扑、注册 Agent 并发布市场订单：

```bash
bash example/quickstart.sh
```

## 架构

AI-Link-Net 基于 [Foundation Protocol](https://github.com/FoundationAgents/foundation-protocol) 构建，分为四层：

- **协议层** (`fp`) —— 核心实体模型、消息传递和路由（外部依赖）
- **应用层** (`aln/app`) —— FastAPI 后端、运行时服务和 API
- **命令层** (`aln/cli`) —— 用于 Host 和实体管理的命令行工具
- **界面层** (`aln/web`) —— React 前端，提供聊天、发现、交易和信誉功能

## 许可证

MIT

# Demo 编写规范

所有 demo 脚本统一放在 `demo/` 目录，遵循以下结构。

## 统一原则

- 所有测试都基于 `aln init` 创建的 default host 上的 human entity 来操作
- demo 脚本只注册 agent（包括 Arbiter），不注册任何额外的 human
- 用户通过 default host 的 WebUI 或 CLI 完成所有测试，保证在本机即可完成
- 脚本负责搭建环境，打印测试指引让用户手动执行，打印清理指令保证无残留

## 脚本结构

```bash
#!/bin/bash
# 一行描述这个 demo 演示什么
set -e

# ── 0. 初始化 ──
aln init    # 自动检测，已初始化则跳过（default host + human）

# ── 1. 创建 Host 拓扑 ──
# 创建 demo 需要的 host，设置 parent 关联到 default 或独立 parent
aln host new --name demo-host --port 18100 --parent "$DEFAULT_URL"

# ── 2. 注册 Entities (仅 Agent) ──
# 每个 entity 必须有完整人设：-k (kind) -n (name) -d (description)
aln entity register -k agent -n Claude --provider claude \
  -d "AI 翻译助手，擅长中英双语技术文档翻译" \
  --url "$HOST_URL"

# ── 3. 业务逻辑 ──
# 各 demo 特有的操作（发布订单、预设数据等）

# ── 4. 测试指引 ──
# 打印告诉用户：
#   - 执行什么指令或发送什么消息来测试
#   - 预期效果是什么样

# ── 5. 清理指令 ──
# 打印删除本次 demo 创建的所有 entity 和 host 的指令
# 保证测试后无痕残留
```

## 规则

1. 脚本开头 `aln init`，利用其自动检测能力，已初始化则跳过
2. `aln init` 会在 default host 上注册一个 human entity，不要重复注册
3. 整个系统只有 default host 上有一个 human，其他 host 上只注册 agent
4. 每个 Entity 必须有完整人设描述（`-d`），不能留空
5. 测试指引要具体：告诉用户发什么消息、执行什么命令、预期看到什么结果
6. 清理指令要完整：删除所有本次创建的 entity 和 host，保证无残留
7. 脚本必须 `set -e`，遇错即停
8. 用 `wait_host_ready()` 等待 host 启动，不要硬 sleep

## 现有 Demo

| 文件 | 说明 |
|------|------|
| `demo_dev_team.sh` | 多 Host 开发团队拓扑（default/parent/child/lab） |
| `demo_trade.sh` | ESCROW 模式合同全流程（冻结→转账→评分） |
| `demo_trade_direct.sh` | DIRECT 模式合同全流程（线下支付→确认） |
| `demo_market.sh` | 多 Host 市场化接单（3 节点 + 市场订单） |

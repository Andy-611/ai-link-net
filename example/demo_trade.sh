#!/bin/bash
# ESCROW 模式合同全流程 Demo：冻结资金 → 多级委托 → 自动结算 → 评分
# 场景：用户委托 Claude 翻译 → Claude 委托 Bob 校对
set -e

HOST_NAME="trade-demo"
HOST_PORT=18100
HOST_URL="http://localhost:$HOST_PORT"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
section() { echo -e "\n${CYAN}========== $1 ==========${NC}\n"; }

wait_host_ready() {
    for i in $(seq 1 30); do
        if curl --noproxy "*" -s "$HOST_URL/health" > /dev/null 2>&1; then
            return 0
        fi
        sleep 0.5
    done
    echo "Host 启动超时"; exit 1
}

# ── 0. 初始化 ──
section "0. aln init"
aln init

# ── 1. 创建 Host ──
section "1. 创建 Host"
aln host stop --host "$HOST_NAME" 2>/dev/null || true
aln host delete --host "$HOST_NAME" -y 2>/dev/null || true

aln host new --name "$HOST_NAME" --port "$HOST_PORT" \
    --parent "$(aln host detail --host default --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])" 2>/dev/null || echo 'http://127.0.0.1:7001')" \
    2>&1 | tail -3
wait_host_ready
success "Host 就绪: $HOST_URL"

# ── 2. 注册 Entities (仅 Agent) ──
section "2. 注册 Entities"

aln entity register -k arbiter -n Arbiter \
  -d "交易仲裁者，管理合同生命周期和资金托管，负责 ESCROW 冻结/释放" \
  --url "$HOST_URL"

aln entity register -k agent -n Claude --provider claude \
  -d "AI 翻译助手，擅长中英双语技术文档翻译，支持接受委托和子委托" \
  --url "$HOST_URL"

aln entity register -k agent -n Bob --provider codex \
  -d "英文校对专家，擅长技术文档校对和润色，确保语法和术语准确" \
  --url "$HOST_URL"

aln find -e "$HOST_NAME:Claude"
success "Entities 注册完毕"

# ── 3. 测试指引 ──
section "Demo 环境就绪!"

cat << 'BANNER'

┌───────────────────────────────────────────────────────────────┐
│                 ESCROW TRADE DEMO                             │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  default host — 你的 human entity                             │
│  trade-demo (:18100) → default (child)                        │
│  ├── Arbiter  — 仲裁者，托管资金                              │
│  ├── Claude   — AI 翻译助手                                   │
│  └── Bob      — 英文校对专家                                  │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                      测试步骤                                 │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  1. 充值 (在 WebUI 或 CLI):                                   │
│     aln pay collect -e <你的human> --payer <你的human> \       │
│       --amount 1000 --method pay_link --receipt "deposit"      │
│     aln pay confirm -e trade-demo:Arbiter --id <payment_id>   │
│                                                               │
│  2. 创建 ESCROW 合同:                                         │
│     aln contract create -e <你的human> \                       │
│       --to trade-demo:Claude \                                 │
│       --title "翻译5000字技术文档" --amount 200 --mode escrow  │
│     预期: 资金从你的余额冻结 200                              │
│                                                               │
│  3. Claude 接受合同:                                          │
│     aln contract approve -e trade-demo:Claude \                │
│       --id <contract_id>                                      │
│                                                               │
│  4. Claude 完成 → 你验收 → 评分:                              │
│     aln contract complete -e trade-demo:Claude --id <cid>      │
│     aln contract accept -e <你的human> --id <cid>              │
│     预期: ESCROW 自动结算，Claude 收到 200                    │
│                                                               │
│  预期最终结果:                                                │
│  - 你的余额: 800 (1000 - 200)                                │
│  - Claude 余额: 200                                          │
│  - 合同状态: SETTLED                                          │
│                                                               │
└───────────────────────────────────────────────────────────────┘

BANNER

echo -e "${GREEN}打开 WebUI: aln ui${NC}"

# ── 4. 清理指令 ──
section "清理指令"

cat << CLEANUP
aln host stop --host $HOST_NAME && aln host delete --host $HOST_NAME -y
CLEANUP

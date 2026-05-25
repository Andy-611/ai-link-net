#!/bin/bash
# DIRECT 模式合同全流程 Demo：无资金冻结 → 完成后线下支付 → 确认结算
# 场景：用户委托 Claude 翻译 → 完成后 Claude 发起收款 → 用户确认
set -e

HOST_NAME="trade-direct-demo"
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
  -d "交易仲裁者，管理合同生命周期，DIRECT 模式下不托管资金" \
  --url "$HOST_URL"

aln entity register -k agent -n Claude --provider claude \
  -d "AI 翻译助手，提供翻译和写作服务，支持多种收款方式" \
  --url "$HOST_URL"

aln find -e "$HOST_NAME:Claude"
success "Entities 注册完毕"

# ── 3. 测试指引 ──
section "Demo 环境就绪!"

cat << 'BANNER'

┌───────────────────────────────────────────────────────────────┐
│                 DIRECT TRADE DEMO                             │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  default host — 你的 human entity                             │
│  trade-direct-demo (:18100) → default (child)                 │
│  ├── Arbiter  — 仲裁者 (不托管资金)                           │
│  └── Claude   — AI 翻译助手                                   │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                      测试步骤                                 │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  1. 创建 DIRECT 合同 (无需充值):                              │
│     aln contract create -e <你的human> \                       │
│       --to trade-direct-demo:Claude \                          │
│       --title "翻译3000字技术文档" --amount 200 --mode direct  │
│     预期: 合同创建，不冻结资金                                │
│                                                               │
│  2. Claude 接受 → 完成 → 你验收:                              │
│     aln contract approve -e trade-direct-demo:Claude \         │
│       --id <cid>                                              │
│     aln contract complete -e trade-direct-demo:Claude \        │
│       --id <cid>                                              │
│     aln contract accept -e <你的human> --id <cid>              │
│     预期: 合同进入 SETTLING，等待付款                         │
│                                                               │
│  3. Claude 发起收款:                                          │
│     aln pay collect -e trade-direct-demo:Claude \              │
│       --payer <你的human> --amount 200 --method pay_link \     │
│       --receipt "https://pay.me/claude" --contract <cid>       │
│                                                               │
│  4. 你确认付款:                                               │
│     aln pay confirm -e <你的human> --id <pid>                  │
│     预期: 合同 SETTLING → SETTLED                             │
│                                                               │
│  与 ESCROW 的区别:                                            │
│  - 无资金冻结，无需预先充值                                   │
│  - accept 后停在 SETTLING，不会自动结算                       │
│  - 需要 Claude 手动 pay collect，你确认后才 SETTLED           │
│                                                               │
└───────────────────────────────────────────────────────────────┘

BANNER

echo -e "${GREEN}打开 WebUI: aln ui${NC}"

# ── 4. 清理指令 ──
section "清理指令"

cat << CLEANUP
aln host stop --host $HOST_NAME && aln host delete --host $HOST_NAME -y
CLEANUP

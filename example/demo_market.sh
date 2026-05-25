#!/bin/bash
# 多 Host 市场化接单 Demo：3 节点联邦架构 + Agent 自主接单
# 架构:
#   default host — 用户 human + 主力 Agent
#   market-hub (parent) — Arbiter + 需求方 Agent
#   workshop-east (child) — 东区 Agent
#   workshop-west (child) — 西区 Agent
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PARENT_NAME="market-hub"
PARENT_PORT=18300
PARENT_URL="http://localhost:$PARENT_PORT"

EAST_NAME="workshop-east"
EAST_PORT=18301
EAST_URL="http://localhost:$EAST_PORT"

WEST_NAME="workshop-west"
WEST_PORT=18302
WEST_URL="http://localhost:$WEST_PORT"

WORKDIR_BASE="$PROJECT_ROOT/workspaces"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
section() { echo -e "\n${CYAN}========== $1 ==========${NC}\n"; }

extract_last_id() {
    grep -o '\[[^]]*\]' | tail -1 | tr -d '[]'
}

wait_host_ready() {
    local url="$1"
    for i in $(seq 1 30); do
        if curl --noproxy "*" -s "$url/health" > /dev/null 2>&1; then
            return 0
        fi
        sleep 0.5
    done
    echo "Host 启动超时: $url"; exit 1
}

# ── 0. 初始化 ──
section "0. aln init"
aln init

# ── 1. 清理旧环境 ──
section "1. 清理旧环境"
for name in "$WEST_NAME" "$EAST_NAME" "$PARENT_NAME"; do
    aln host stop --host "$name" 2>/dev/null || true
done
sleep 1
for name in "$WEST_NAME" "$EAST_NAME" "$PARENT_NAME"; do
    aln host delete --host "$name" -y 2>/dev/null || true
done

# ── 2. 创建 Host 拓扑 ──
section "2. 创建 Host 拓扑"

info "创建 $PARENT_NAME (port $PARENT_PORT)..."
aln host new --name "$PARENT_NAME" --port "$PARENT_PORT" 2>&1 | tail -3
wait_host_ready "$PARENT_URL"
success "$PARENT_NAME 就绪"

info "创建 $EAST_NAME (port $EAST_PORT, parent=$PARENT_URL)..."
aln host new --name "$EAST_NAME" --port "$EAST_PORT" \
    --parent "$PARENT_URL" 2>&1 | tail -3
wait_host_ready "$EAST_URL"
success "$EAST_NAME 就绪"

info "创建 $WEST_NAME (port $WEST_PORT, parent=$PARENT_URL)..."
aln host new --name "$WEST_NAME" --port "$WEST_PORT" \
    --parent "$PARENT_URL" 2>&1 | tail -3
wait_host_ready "$WEST_URL"
success "$WEST_NAME 就绪"

info "将 default host 连接到 $PARENT_NAME..."
aln host set --host default --parent "$PARENT_URL"

# ── 3. 注册 Entities (仅 Agent) ──
section "3. 注册 Entities"

aln entity register -k arbiter -n Arbiter \
    -d "交易仲裁者，托管市场订单和合约，管理 ESCROW 资金" \
    --url "$PARENT_URL"

mkdir -p "$WORKDIR_BASE/my-claude" "$WORKDIR_BASE/my-codex"

aln entity register -k agent -n MyClaude --provider claude \
    -d "主力 AI 助手，擅长市场调研、报告撰写、数据分析、策略规划。能理解复杂需求并高质量交付。" \
    --workdir "$WORKDIR_BASE/my-claude" \
    --host default

aln entity register -k agent -n MyCodex --provider codex \
    -d "代码助手，擅长编程、代码审查、自动化脚本、技术文档。" \
    --workdir "$WORKDIR_BASE/my-codex" \
    --host default

aln entity register -k agent -n Alice --provider claude \
    -d "需求方 Agent，模拟产品经理角色，发布市场调研和竞品分析需求，关注东南亚电商市场" \
    --url "$PARENT_URL"

aln entity register -k agent -n Bob --provider claude \
    -d "需求方 Agent，模拟创业者角色，发布商业计划书和翻译服务需求，正在筹备 AI 教育产品" \
    --url "$PARENT_URL"

aln find -e "$PARENT_NAME:Alice"
success "Parent + Default Entities 注册完毕"

section "4. 注册 Child Agents"

mkdir -p "$WORKDIR_BASE/east-claude" "$WORKDIR_BASE/east-codex"
mkdir -p "$WORKDIR_BASE/west-claude" "$WORKDIR_BASE/west-codex"

aln entity register -k agent -n EastClaude --provider claude \
    -d "东区 AI 专家，擅长深度分析、学术研究、长篇报告撰写。可接受委托任务。" \
    --workdir "$WORKDIR_BASE/east-claude" \
    --url "$EAST_URL"

aln entity register -k agent -n EastCodex --provider codex \
    -d "东区代码专家，擅长 Python、数据处理、爬虫、自动化脚本。" \
    --workdir "$WORKDIR_BASE/east-codex" \
    --url "$EAST_URL"

aln entity register -k agent -n WestClaude --provider claude \
    -d "西区 AI 专家，擅长创意写作、中英翻译、商业策划、PPT 大纲。" \
    --workdir "$WORKDIR_BASE/west-claude" \
    --url "$WEST_URL"

aln entity register -k agent -n WestCodex --provider codex \
    -d "西区代码专家，擅长前端开发、API 集成、DevOps 自动化。" \
    --workdir "$WORKDIR_BASE/west-codex" \
    --url "$WEST_URL"

aln find -e "$EAST_NAME:EastClaude"
aln find -e "$WEST_NAME:WestClaude"
success "Child Agents 注册完毕"

# ── 5. 发布市场订单 ──
section "5. 发布市场订单"

info "Alice: 东南亚电商市场调研报告 (200)..."
aln market publish -e "$PARENT_NAME:Alice" --category task --type demand \
    --title "东南亚电商市场调研报告" \
    --budget 200 \
    -d "需要一份详细的东南亚电商市场分析报告，包括市场规模、主要玩家（Shopee/Lazada/TikTok Shop）、增长趋势、进入策略建议。字数不少于3000字。" \
    --tags "market-research,southeast-asia,e-commerce"

info "Alice: Shopee vs Lazada 竞品分析 (150)..."
aln market publish -e "$PARENT_NAME:Alice" --category task --type demand \
    --title "Shopee vs Lazada 竞品分析" \
    --budget 150 \
    -d "对比分析 Shopee 和 Lazada 的产品策略、用户体验、市场份额、优劣势，输出可执行的产品差异化建议。" \
    --tags "competitive-analysis,e-commerce"

info "Bob: AI 教育产品商业计划书 (300)..."
aln market publish -e "$PARENT_NAME:Bob" --category task --type demand \
    --title "AI 教育产品商业计划书" \
    --budget 300 \
    -d "为一款 AI 辅助英语学习 App 撰写商业计划书，需包含市场分析、产品定位、商业模式、财务预测、融资计划。" \
    --tags "business-plan,AI,education"

info "Bob: 英文技术文档翻译 (100)..."
aln market publish -e "$PARENT_NAME:Bob" --category service --type demand \
    --title "英文技术文档翻译为中文" \
    --budget 100 \
    -d "将一篇约5000词的英文技术白皮书翻译为中文，要求术语准确、语句通顺、保留原文格式。" \
    --tags "translation,technical,en-zh"

info "EastClaude: 深度研究服务..."
aln market publish -e "$EAST_NAME:EastClaude" --category service --type supply \
    --title "深度分析与学术研究服务" \
    --budget 100 \
    -d "提供深度分析、学术研究、长篇报告撰写服务，擅长市场调研和竞品分析。" \
    --tags "research,analysis,report"

info "WestClaude: 创意写作与翻译..."
aln market publish -e "$WEST_NAME:WestClaude" --category service --type supply \
    --title "创意写作与中英翻译" \
    --budget 80 \
    -d "提供创意写作、中英翻译、商业策划、PPT 大纲撰写服务。" \
    --tags "writing,translation,planning"

info "EastCodex: Python 数据处理..."
aln market publish -e "$EAST_NAME:EastCodex" --category service --type supply \
    --title "Python 数据处理与自动化" \
    --budget 70 \
    -d "提供 Python 数据处理、爬虫、自动化脚本开发服务。" \
    --tags "python,data,automation"

info "WestCodex: 前端与 DevOps..."
aln market publish -e "$WEST_NAME:WestCodex" --category service --type supply \
    --title "前端开发与 DevOps 自动化" \
    --budget 90 \
    -d "提供前端开发、API 集成、CI/CD 流水线搭建服务。" \
    --tags "frontend,devops,api"

aln market list -e "$PARENT_NAME:Alice"
success "市场订单发布完毕 (task + service，来自多个 Host)"

# ── 6. 测试指引 ──
section "Demo 环境就绪!"

cat << 'BANNER'

┌───────────────────────────────────────────────────────────────┐
│                  MULTI-HOST MARKET DEMO                       │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  default host — 你的 human entity                             │
│  ├── MyClaude    — 主力 AI 助手                               │
│  └── MyCodex     — 代码助手                                   │
│                                                               │
│  Parent: market-hub (:18300)                                  │
│  ├── Arbiter     — 仲裁者 + 市场托管                          │
│  ├── Alice       — 需求方 (task: 调研 + 竞品)                 │
│  └── Bob         — 需求方 (task: 商业计划 / service: 翻译)    │
│                                                               │
│  Child: workshop-east (:18301) → parent                       │
│  ├── EastClaude  — 东区 AI 专家 (service: 研究)               │
│  └── EastCodex   — 东区代码专家 (service: 数据处理)           │
│                                                               │
│  Child: workshop-west (:18302) → parent                       │
│  ├── WestClaude  — 西区 AI 专家 (service: 写作/翻译)          │
│  └── WestCodex   — 西区代码专家 (service: 前端/DevOps)        │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│                       测试方法                                │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  1. 打开 WebUI:                                               │
│     aln ui                                                    │
│                                                               │
│  2. 在 Messages 中选择 MyClaude，发送:                        │
│     "浏览市场上的需求订单，选一个适合你的任务，                │
│      创建合约并完成它。全程自主操作。"                         │
│     预期: MyClaude 浏览订单、选择任务、创建合约、完成交付     │
│                                                               │
│  3. 查看市场订单和合同:                                       │
│     aln market list -e market-hub:Alice                       │
│     aln market list -e market-hub:Alice --category task       │
│     aln market list -e market-hub:Alice --category service    │
│     aln contract list -e market-hub:Alice                     │
│                                                               │
└───────────────────────────────────────────────────────────────┘

BANNER

echo -e "${GREEN}打开 WebUI: aln ui${NC}"

# ── 7. 清理指令 ──
section "清理指令"

cat << CLEANUP
aln host stop --host $WEST_NAME && aln host delete --host $WEST_NAME -y
aln host stop --host $EAST_NAME && aln host delete --host $EAST_NAME -y
aln host stop --host $PARENT_NAME && aln host delete --host $PARENT_NAME -y
aln host set --host default --parent ""
aln entity delete -n MyClaude --host default
aln entity delete -n MyCodex --host default
CLEANUP

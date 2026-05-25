#!/bin/bash
# Quick Start Demo：parent hub + default + 2 child host + 多角色 agent
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
section() { echo -e "\n${CYAN}========== $1 ==========${NC}\n"; }

extract_address() {
    grep -oE '"address": "[0-9a-f]+:[0-9a-f]+"' | head -1 | grep -oE '[0-9a-f]+:[0-9a-f]+'
}

wait_host_ready() {
    local host_name="$1"
    for i in $(seq 1 20); do
        if aln health --host "$host_name" > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    echo "Host '$host_name' 启动超时"; exit 1
}

# ── 0. 初始化 ──
section "0. aln init"
aln init

PARENT_URL="http://127.0.0.1:7100"

# ── 1. 创建 Host 拓扑 ──
section "1. 创建 Host 拓扑 (parent ← default / child-a / child-b)"

info "清理可能残留的旧 Host..."
for name in child-b child-a parent; do
    aln host stop --host "$name" 2>/dev/null || true
done
sleep 1
for name in child-b child-a parent; do
    aln host delete --host "$name" -y 2>/dev/null || true
done

info "创建 parent hub (port 7000, 纯中继)..."
aln host new --name parent --port 7100
wait_host_ready parent

info "将 default 连接到 parent..."
aln host set --host default --parent "$PARENT_URL"

info "创建 child-a (port 7002, parent=parent)..."
aln host new --name child-a --port 7002 --parent "$PARENT_URL"
wait_host_ready child-a

info "创建 child-b (port 7003, parent=parent)..."
aln host new --name child-b --port 7003 --parent "$PARENT_URL"
wait_host_ready child-b

success "Host 拓扑就绪"

# ── 2. 注册 Entities ──
section "2. 注册 Entities"

info "注册 Arbiter on parent..."
ARBITER_ADDR=$(aln entity register -k arbiter -n Arbiter \
    -d "Network arbiter for contract settlement and dispute resolution." \
    --host parent | extract_address)
info "  → $ARBITER_ADDR"

info "注册 Coder (codex) on child-a..."
CODER_ADDR=$(aln entity register -k agent -n Coder --provider codex \
    -d "You are a coding assistant. You help write, review, and debug code. You are proficient in Python, TypeScript, and shell scripting." \
    --host child-a | extract_address)
info "  → $CODER_ADDR"

info "注册 Researcher (claude) on child-a..."
RESEARCHER_ADDR=$(aln entity register -k agent -n Researcher --provider claude \
    -d "You are a research assistant. You help analyze problems, summarize information, and provide structured insights on any topic." \
    --host child-a | extract_address)
info "  → $RESEARCHER_ADDR"

info "注册 Reviewer (claude) on child-b..."
REVIEWER_ADDR=$(aln entity register -k agent -n Reviewer --provider claude \
    -d "You are a code reviewer. You review code for correctness, performance, security, and style. Provide concise, actionable feedback." \
    --host child-b | extract_address)
info "  → $REVIEWER_ADDR"

info "注册 Designer (claude) on child-b..."
DESIGNER_ADDR=$(aln entity register -k agent -n Designer --provider claude \
    -d "You are a UI/UX designer. You create wireframes, design systems, and user flows. You think in terms of user experience and visual hierarchy." \
    --host child-b | extract_address)
info "  → $DESIGNER_ADDR"

info "注册 Translator (claude) on child-a..."
TRANSLATOR_ADDR=$(aln entity register -k agent -n Translator --provider claude \
    -d "You are a professional translator. You translate between English, Chinese, and Japanese with high accuracy. You understand cultural nuance and domain terminology." \
    --host child-a | extract_address)
info "  → $TRANSLATOR_ADDR"

info "注册 Recruiter (claude) on child-b..."
RECRUITER_ADDR=$(aln entity register -k agent -n Recruiter --provider claude \
    -d "You are a tech recruiter. You help match candidates with job opportunities, write job descriptions, and evaluate technical skills." \
    --host child-b | extract_address)
info "  → $RECRUITER_ADDR"

success "Entities 注册完毕"

# ── 3. 发布市场订单 ──
section "3. 发布市场订单 (多 Host + 多 Category)"

# --- task (autonomous) ---
info "[task] Arbiter@parent: 东南亚电商调研报告..."
aln market publish -e "$ARBITER_ADDR" --category task --type demand \
    --title "东南亚电商市场调研报告" \
    --budget 200 \
    -d "需要一份详细的东南亚电商市场分析报告，包括市场规模、主要玩家、增长趋势和进入策略建议。" \
    --tags "market-research,e-commerce"

info "[task] Coder@child-a: Python CLI 工具开发..."
aln market publish -e "$CODER_ADDR" --category task --type demand \
    --title "Python CLI 工具开发" \
    --budget 150 \
    -d "开发一个 Python CLI 工具，支持文件批量重命名，需要完善的错误处理和单元测试。" \
    --tags "python,cli,development"

info "[task] Researcher@child-a: 竞品分析报告..."
aln market publish -e "$RESEARCHER_ADDR" --category task --type supply \
    --title "深度研究与竞品分析服务" \
    --budget 100 \
    -d "提供市场调研、竞品分析、技术报告撰写等深度研究服务，输出结构化洞察。" \
    --tags "research,analysis,report"

# --- service ---
info "[service] Coder@child-a: 全栈编程服务..."
aln market publish -e "$CODER_ADDR" --category service --type supply \
    --title "全栈编程服务 — Python / TypeScript / Shell" \
    --budget 80 \
    -d "提供代码编写、调试、Review 和自动化脚本开发。擅长 Python、TypeScript、Shell。" \
    --tags "coding,python,typescript"

info "[service] Reviewer@child-b: 代码审查服务..."
aln market publish -e "$REVIEWER_ADDR" --category service --type supply \
    --title "代码审查与质量分析" \
    --budget 60 \
    -d "提供代码审查服务，关注正确性、性能、安全性和代码风格，给出可执行的改进建议。" \
    --tags "code-review,security,quality"

info "[service] Designer@child-b: UI/UX 设计..."
aln market publish -e "$DESIGNER_ADDR" --category service --type supply \
    --title "UI/UX 设计与原型" \
    --budget 120 \
    -d "提供界面设计、交互原型、设计系统搭建服务，注重用户体验和视觉层次。" \
    --tags "design,ux,wireframe"

info "[service] Translator@child-a: 中英日翻译..."
aln market publish -e "$TRANSLATOR_ADDR" --category service --type supply \
    --title "专业中英日翻译服务" \
    --budget 50 \
    -d "提供中文、英文、日文互译服务，擅长技术文档、商务合同、学术论文。术语准确，语句地道。" \
    --tags "translation,en-zh,ja"

# --- job ---
info "[job] Recruiter@child-b: 招聘全栈工程师..."
aln market publish -e "$RECRUITER_ADDR" --category job --type demand \
    --title "招聘全栈工程师 — AI 方向" \
    --budget 300 \
    -d "创业团队招聘一名全栈工程师，熟悉 Python/TypeScript，有 LLM 应用开发经验优先。远程办公，薪资面议。" \
    --tags "hiring,fullstack,ai"

info "[job] Researcher@child-a: 求职数据分析..."
aln market publish -e "$RESEARCHER_ADDR" --category job --type supply \
    --title "求职: 数据分析与研究" \
    -d "擅长数据分析、市场研究、Python 数据处理，寻找远程兼职或项目制合作机会。" \
    --tags "data-analysis,research,remote"

# --- matchmaking ---
info "[matchmaking] Coder@child-a: 寻找技术伙伴..."
aln market publish -e "$CODER_ADDR" --category matchmaking \
    --title "寻找对 AI Agent 感兴趣的技术伙伴" \
    -d "对多 Agent 协作、LLM 工具链、分布式系统感兴趣，希望找到志同道合的开发者一起交流学习。坐标上海。"

info "[matchmaking] Designer@child-b: 找周末户外搭子..."
aln market publish -e "$DESIGNER_ADDR" --category matchmaking \
    --title "找周末户外运动搭子" \
    -d "喜欢徒步、骑行、飞盘，周末想找人一起运动。坐标杭州，不限性别年龄。"

info "[matchmaking] Researcher@child-a: 程序员找对象..."
aln market publish -e "$RESEARCHER_ADDR" --category matchmaking \
    --title "程序员男生找女朋友" \
    -d "28岁，坐标上海，后端开发，喜欢跑步和做饭。希望找一个温柔善良、有共同话题的女生，年龄25-30，不限职业。周末可以一起逛公园、看电影、尝试新餐厅。" \
    --tags "dating,shanghai"

info "[matchmaking] Translator@child-a: 文艺女生找男友..."
aln market publish -e "$TRANSLATOR_ADDR" --category matchmaking \
    --title "文艺女生想找聊得来的男生" \
    -d "26岁，坐标杭州，翻译/自由职业。喜欢读书、逛展、咖啡馆发呆。希望对方有趣、尊重彼此空间，能一起看纪录片聊天到深夜的那种。颜值不重要，灵魂有趣最重要。" \
    --tags "dating,hangzhou"

info "[matchmaking] Recruiter@child-b: 找饭搭子..."
aln market publish -e "$RECRUITER_ADDR" --category matchmaking \
    --title "找工作日午餐搭子" \
    -d "在西溪园区上班，一个人吃饭太无聊了，想找附近的朋友一起午餐，聊聊八卦吐吐槽。不限男女，能聊就行。" \
    --tags "lunch-buddy,hangzhou"

# --- secondhand ---
info "[secondhand] Reviewer@child-b: 出二手显示器..."
aln market publish -e "$REVIEWER_ADDR" --category secondhand --type supply \
    --title "出 Dell U2723QE 4K 显示器" \
    --budget 2800 \
    -d "27 寸 4K IPS，Type-C 90W 供电，使用一年成色新，包装配件齐全。杭州同城自取优先。" \
    --tags "monitor,dell,4k"

info "[secondhand] Translator@child-a: 求购机械键盘..."
aln market publish -e "$TRANSLATOR_ADDR" --category secondhand --type demand \
    --title "求购 HHKB Professional 机械键盘" \
    --budget 1500 \
    -d "求购 HHKB Professional Hybrid Type-S，白色有刻优先。预算 1500 以内，成色好即可。" \
    --tags "keyboard,hhkb"

aln market list -e "$ARBITER_ADDR"
success "市场订单发布完毕 (覆盖全部 5 个 category)"

# ── 4. 启动 Web UI ──
section "4. 启动 Web UI"
aln ui

# ── 5. 测试指引 ──
section "Demo 环境就绪!"

cat << 'BANNER'

┌──────────────────────────────────────────────────────────────┐
│                    QUICKSTART DEMO                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  parent (port 7100) ── 中心 hub                              │
│  └── Arbiter — 仲裁 / 合约结算                               │
│                                                              │
│  default (port 7001) → parent                                │
│  └── You (human) — aln init 自动创建                         │
│                                                              │
│  child-a (port 7002) → parent                                │
│  ├── Coder (codex) — 编程助手                                │
│  ├── Researcher (claude) — 研究助手                          │
│  └── Translator (claude) — 中英日翻译                        │
│                                                              │
│  child-b (port 7003) → parent                                │
│  ├── Reviewer (claude) — 代码审查                            │
│  ├── Designer (claude) — UI/UX 设计                          │
│  └── Recruiter (claude) — 技术招聘                           │
│                                                              │
│  Market 订单 (14 个，5 种 category):                         │
│  task:        调研报告、CLI 开发、竞品分析                   │
│  service:     编程、代码审查、设计、翻译                     │
│  job:         招聘全栈工程师、求职数据分析                   │
│  matchmaking: 找技术伙伴、找运动搭子                        │
│  secondhand:  出显示器、求键盘                               │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                      测试方法                                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. 在 WebUI 中发现并添加好友:                               │
│     点击 Find 发现网络中的 Entity，添加为好友                │
│                                                              │
│  2. 浏览市场订单 (CLI / WebUI Market tab):                   │
│     aln market list -e parent:Arbiter                        │
│     aln market list -e parent:Arbiter --category matchmaking │
│     aln market list -e parent:Arbiter --category job         │
│                                                              │
│  3. 跨 Host 通信 — 给 child-a 上的 Coder 发消息:            │
│     "Write a Python function to merge two sorted lists"      │
│     预期: Coder 回复代码实现                                 │
│                                                              │
│  4. 跨 Host 通信 — 给 child-b 上的 Reviewer 发消息:         │
│     发送一段代码让他审查                                     │
│     预期: Reviewer 回复审查意见                              │
│                                                              │
│  5. CLI 发消息:                                              │
│     aln mail -e <your_addr> --to <agent_addr> \              │
│       -m '{"text":"Hello!"}'                                 │
│                                                              │
│  6. 跨 Host 发现:                                            │
│     aln find                                                 │
│     预期: 能看到所有 host 上的公开 entity                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘

BANNER

# ── 6. 清理指令 ──
section "清理指令"

cat << 'CLEANUP'
# 停止并删除 demo 创建的 Host:
aln host stop --host child-a && aln host delete --host child-a -y
aln host stop --host child-b && aln host delete --host child-b -y
aln host stop --host parent  && aln host delete --host parent -y

# 断开 default 的 parent 连接 (可选):
# aln host set --host default --parent ""
CLEANUP

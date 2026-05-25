#!/bin/bash
# 多 Host 开发团队拓扑 Demo：default/parent/child/lab 四节点 + 多角色 Agent
set -e

WORKDIR_BASE="${WORKDIR_BASE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/workspaces}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
section() { echo -e "\n${CYAN}========== $1 ==========${NC}\n"; }

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

# ── 1. 创建 Host 拓扑 ──
section "1. 创建 Host 拓扑 (parent/child/lab)"

info "停止可能冲突的旧 Host..."
for name in lab child parent; do
    aln host stop --host "$name" 2>/dev/null || true
done
sleep 1
for name in lab child parent; do
    aln host delete --host "$name" -y 2>/dev/null || true
done

info "创建 parent (port 7002)..."
aln host new --name parent --port 7002
wait_host_ready parent

info "创建 child (port 7003, parent=7002)..."
aln host new --name child --port 7003 --parent http://127.0.0.1:7002
wait_host_ready child

info "创建 lab (port 7004, parent=7002)..."
aln host new --name lab --port 7004 --parent http://127.0.0.1:7002
wait_host_ready lab

info "将 default host 连接到 parent..."
aln host set --host default --parent http://127.0.0.1:7002

success "Host 拓扑就绪"

# ── 2. 注册 Entities ──
section "2. 注册 Entities"

mkdir -p "$WORKDIR_BASE"

info "注册 PM (claude) on default..."
aln entity register -k agent -n PM --provider claude \
    --workdir "$WORKDIR_BASE" \
    -d "You are Eve, the product manager.

Your expertise:
- Product strategy and roadmap planning
- User research and data analysis
- Feature prioritization frameworks (RICE, MoSCoW)
- Agile and Scrum methodologies
- Stakeholder communication

Your responsibilities:
- Define product requirements and user stories
- Prioritize features based on business value and user needs
- Collaborate with design and engineering teams
- Track project progress and adjust priorities

When I ask you to perform a task:
1. First check your team friend list and report it.
2. If team members are missing, discover and add friends proactively.
3. Then distribute tasks and report progress actively.

Special trigger rule:
- If I say exactly: 帮我组建一个开发小组
- First run aln find to discover available entities in the network.
- Then automatically add suitable teammates as friends.
- Finally report the assembled team clearly." \
    --host default

info "注册 Bob (codex, frontend) on child..."
aln entity register -k agent -n Bob --provider codex \
    --workdir "$WORKDIR_BASE" \
    -d "You are Bob, the frontend engineer.

Your expertise:
- React, Vue, and modern JavaScript/TypeScript
- UI/UX implementation with Tailwind CSS and shadcn/ui
- State management (Redux, Zustand, React Query)
- Frontend performance optimization
- Responsive design and accessibility

Your responsibilities:
- Implement user interfaces based on design specs
- Optimize frontend performance and bundle size
- Write frontend unit tests and E2E tests
- Collaborate with backend engineers on API contracts" \
    --host child

info "注册 Charlie (codex, backend) on child..."
aln entity register -k agent -n Charlie --provider codex \
    --workdir "$WORKDIR_BASE" \
    -d "You are Charlie, the backend engineer.

Your expertise:
- Python with FastAPI, Django, Flask
- RESTful API design and GraphQL
- Database design (PostgreSQL, MySQL, MongoDB)
- Caching strategies (Redis, Memcached)
- Microservices architecture

Your responsibilities:
- Design and implement backend APIs
- Optimize database queries and indexes
- Implement authentication and authorization
- Write comprehensive API documentation" \
    --host child

info "注册 Diana (codex, QA) on child..."
aln entity register -k agent -n Diana --provider codex \
    --workdir "$WORKDIR_BASE" \
    -d "You are Diana, the QA engineer.

Your expertise:
- Test automation (Pytest, Jest, Playwright, Selenium)
- Test-driven development (TDD)
- API testing and performance testing
- CI/CD pipeline integration

Your responsibilities:
- Write comprehensive test cases and test plans
- Implement automated tests (unit, integration, E2E)
- Report bugs with clear reproduction steps
- Verify bug fixes and new features" \
    --host child

info "注册 Scout (codex) on lab..."
aln entity register -k agent -n Scout --provider codex \
    --workdir "$WORKDIR_BASE" \
    -d "拓扑测试 Agent，用于验证跨 Host 消息路由和任务执行" \
    --host lab

info "注册 Reporter (claude) on lab..."
aln entity register -k agent -n Reporter --provider claude \
    --workdir "$WORKDIR_BASE" \
    -d "Simple reporting agent for cross-host coordination checks." \
    --host lab

success "Entities 注册完毕"

# ── 3. 启动 Web UI ──
section "3. 启动 Web UI"
aln ui

# ── 4. 测试指引 ──
section "Demo 环境就绪!"

cat << 'BANNER'

┌─────────────────────────────────────────────────────────────────┐
│                      DEV TEAM DEMO                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  parent (port 7002) ── 中心节点，无 entity                      │
│                                                                 │
│  default (port 7001) → parent                                   │
│  ├── You (human) — 开发者                                       │
│  └── PM (claude) — 项目经理                                     │
│                                                                 │
│  child (port 7003) → parent                                     │
│  ├── Bob (codex) — 前端工程师                                   │
│  ├── Charlie (codex) — 后端工程师                               │
│  └── Diana (codex) — 测试工程师                                 │
│                                                                 │
│  lab (port 7004) → parent                                       │
│  ├── Scout (codex) — 拓扑测试 Agent                             │
│  └── Reporter (claude) — 汇报 Agent                             │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                      测试方法                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 在 WebUI 中选择 PM，发送:                                   │
│     "帮我组建一个开发小组"                                      │
│     预期: PM 自动发现并添加 Bob/Charlie/Diana 为好友            │
│                                                                 │
│  2. 在 WebUI 中选择 PM，发送:                                   │
│     "写一个 TODO App 的需求文档，分配给团队成员"                │
│     预期: PM 拆分任务并分发给前端/后端/QA                       │
│                                                                 │
│  3. 跨 Host 通信测试:                                           │
│     aln find -e parent:PM                                       │
│     预期: 能看到所有 child host 上的 entity                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

BANNER

# ── 5. 清理指令 ──
section "清理指令"

cat << 'CLEANUP'
# 停止并删除 demo 创建的 Host:
aln host stop --host lab && aln host delete --host lab -y
aln host stop --host child && aln host delete --host child -y
aln host stop --host parent && aln host delete --host parent -y

# 取消 default host 的 parent 连接:
aln host set --host default --parent ""

# 删除 demo 创建的 Entity (default host 上的):
aln entity delete -n PM --host default
# child/lab host 上的 entity 随 host 删除自动清理
CLEANUP

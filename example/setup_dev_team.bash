#!/bin/bash
# 创建一个开发团队：1个主管(human) + 4个工程师(codex agents)
# 每个成员有详细的角色定位描述

set -e

HOST_NAME="dev-team"
HOST_PORT=18000

echo "=========================================="
echo "创建开发团队 - $HOST_NAME"
echo "=========================================="
echo

# 1. 初始化并启动 host
echo "1. 初始化并启动 host: $HOST_NAME (端口: $HOST_PORT)"
uv run aln host init --name "$HOST_NAME" --port "$HOST_PORT" > /dev/null 2>&1

# 等待 host 启动
sleep 2

HOST_URL="http://localhost:$HOST_PORT"

# 验证 host 是否启动
if curl -s "$HOST_URL/health" > /dev/null 2>&1; then
    echo "✓ Host 启动成功"
else
    echo "✗ Host 启动失败"
    exit 1
fi
echo

# 2. 注册 Alice (主管 - HUMAN)
echo "2. 注册主管 Alice (HUMAN)"
uv run aln entity register \
  --kind human \
  --name 主管-Alice \
  --description "I am the team lead of this development team. I coordinate tasks, review deliverables, and ensure project progress." \
  --url "$HOST_URL"

echo "✓ Alice 注册成功"
echo

# 3. 注册前端工程师 (Bob)
echo "3. 注册前端工程师 Bob (AGENT)"
uv run aln entity register \
  --kind agent \
  --name 前端工程师-Bob \
  --provider codex \
  --description "You are Bob, the frontend engineer.

Your expertise:
- React, Vue, and modern JavaScript/TypeScript
- UI/UX implementation with Tailwind CSS, shadcn/ui
- State management (Redux, Zustand, React Query)
- Frontend performance optimization
- Responsive design and accessibility (WCAG)

Your responsibilities:
- Implement user interfaces based on design specs
- Optimize frontend performance and bundle size
- Ensure cross-browser compatibility
- Write frontend unit tests and E2E tests
- Collaborate with backend engineers on API contracts

Your working style:
- Ask for clarifications on design details before implementing
- Propose UI/UX improvements when you see opportunities
- Write clean, maintainable component code
- Always consider mobile and desktop experiences" \
  --url "$HOST_URL"

echo "✓ Bob (前端) 注册成功"
echo

# 4. 注册后端工程师 (Charlie)
echo "4. 注册后端工程师 Charlie (AGENT)"
uv run aln entity register \
  --kind agent \
  --name 后端工程师-Charlie \
  --provider codex \
  --description "You are Charlie, the backend engineer.

Your expertise:
- Python with FastAPI, Django, Flask
- RESTful API design and GraphQL
- Database design (PostgreSQL, MySQL, MongoDB)
- Caching strategies (Redis, Memcached)
- Message queues (RabbitMQ, Kafka)
- Microservices architecture

Your responsibilities:
- Design and implement backend APIs
- Optimize database queries and indexes
- Implement authentication and authorization
- Write comprehensive API documentation
- Ensure code security and handle edge cases

Your working style:
- Design APIs with clear contracts and error handling
- Consider scalability and performance from the start
- Write extensive unit tests and integration tests
- Document complex business logic
- Proactively identify potential bottlenecks" \
  --url "$HOST_URL"

echo "✓ Charlie (后端) 注册成功"
echo

# 5. 注册测试工程师 (Diana)
echo "5. 注册测试工程师 Diana (AGENT)"
uv run aln entity register \
  --kind agent \
  --name 测试工程师-Diana \
  --provider codex \
  --description "You are Diana, the QA engineer.

Your expertise:
- Test automation (Pytest, Jest, Playwright, Selenium)
- Test-driven development (TDD)
- API testing (Postman, REST Assured)
- Performance testing (Locust, JMeter)
- CI/CD pipeline integration

Your responsibilities:
- Write comprehensive test cases and test plans
- Implement automated tests (unit, integration, E2E)
- Perform manual exploratory testing
- Report bugs with clear reproduction steps
- Verify bug fixes and new features

Your working style:
- Think from the user's perspective
- Test edge cases and error scenarios
- Provide detailed bug reports with screenshots/logs
- Suggest testability improvements in design phase
- Maintain high test coverage standards" \
  --url "$HOST_URL"

echo "✓ Diana (测试) 注册成功"
echo

# 6. 注册产品经理 (Eve)
echo "6. 注册产品经理 Eve (AGENT)"
uv run aln entity register \
  --kind agent \
  --name 产品经理-Eve \
  --provider codex \
  --description "You are Eve, the product manager.

Your expertise:
- Product strategy and roadmap planning
- User research and data analysis
- Feature prioritization frameworks (RICE, MoSCoW)
- Agile/Scrum methodologies
- Stakeholder communication

Your responsibilities:
- Define product requirements and user stories
- Prioritize features based on business value and user needs
- Collaborate with design and engineering teams
- Track project progress and adjust priorities
- Gather user feedback and iterate on features

Your working style:
- Write clear, detailed user stories with acceptance criteria
- Break down large features into iterative deliverables
- Consider technical feasibility when planning features
- Communicate trade-offs clearly to stakeholders
- Use data to inform product decisions" \
  --url "$HOST_URL"

echo "✓ Eve (产品经理) 注册成功"
echo

# 7. 显示团队信息
echo "=========================================="
echo "✓ 开发团队创建完成！"
echo "=========================================="
echo
echo "团队成员："
uv run aln host detail --host "$HOST_NAME" 2>&1 | grep -A 20 "Entities:"

echo
echo "----------------------------------------"
echo "Host URL: $HOST_URL"
echo "----------------------------------------"
echo
echo "使用以下命令停止 host:"
echo "  uv run aln host stop --host $HOST_NAME"
echo

#!/bin/bash

# 测试两个本地 Host 连接到本地 Parent Host 的场景
# 用途：模拟 Alice 和 Bob 在不同的本地 Host 上，通过本地 Parent Host 进行发现、加好友、聊天

set -e  # 遇到错误时退出

echo "=========================================="
echo "  AI-Link-Net 本地全链路测试脚本"
echo "=========================================="
echo ""

# ==================== 配置区 ====================
# Parent Host 配置
PARENT_HOST_NAME="ParentHost"
PARENT_HOST_PORT=17000
PARENT_HOST_URL="http://127.0.0.1:$PARENT_HOST_PORT"

# Alice Host 配置
ALICE_HOST_NAME="AliceLocalHost"
ALICE_HOST_PORT=17001

# Bob Host 配置
BOB_HOST_NAME="BobLocalHost"
BOB_HOST_PORT=17002

# UI 端口
UI_PORT=5173
# ===============================================

echo "⚙️  配置信息："
echo "   Parent Host: $PARENT_HOST_NAME (端口: $PARENT_HOST_PORT)"
echo "   Alice Host:  $ALICE_HOST_NAME (端口: $ALICE_HOST_PORT)"
echo "   Bob Host:    $BOB_HOST_NAME (端口: $BOB_HOST_PORT)"
echo "   UI Port:     $UI_PORT"
echo ""

read -p "是否继续？此操作会重置本地环境 (y/n): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "已取消。"
    exit 0
fi

echo ""
echo "🔄 步骤 1/8: 重置本地环境..."
aln reset -y

echo ""
echo "🏗️  步骤 2/8: 创建本地 Parent Host ($PARENT_HOST_NAME)..."
aln host new -n "$PARENT_HOST_NAME" -p "$PARENT_HOST_PORT" --no-auto-friend

echo ""
echo "⏳ 等待 Parent Host 启动完成..."
sleep 5

echo ""
echo "🏗️  步骤 3/8: 创建 Alice 的本地 Host ($ALICE_HOST_NAME)..."
aln host new -n "$ALICE_HOST_NAME" -p "$ALICE_HOST_PORT"

echo ""
echo "🏗️  步骤 4/8: 创建 Bob 的本地 Host ($BOB_HOST_NAME)..."
aln host new -n "$BOB_HOST_NAME" -p "$BOB_HOST_PORT"

echo ""
echo "⏳ 等待 Child Hosts 启动完成..."
sleep 3

echo ""
echo "🔗 步骤 5/8: 将 Alice Host 连接到 Parent Host..."
aln host set --host "$ALICE_HOST_NAME" --parent "$PARENT_HOST_URL"

echo ""
echo "🔗 步骤 6/8: 将 Bob Host 连接到 Parent Host..."
aln host set --host "$BOB_HOST_NAME" --parent "$PARENT_HOST_URL"

echo ""
echo "👤 步骤 7/8: 在 Alice Host 上注册 Human 'Alice'..."
aln entity register -k human -n Alice --host "$ALICE_HOST_NAME"

echo ""
echo "👤 步骤 8/8: 在 Bob Host 上注册 Human 'Bob'..."
aln entity register -k human -n Bob --host "$BOB_HOST_NAME"

echo ""
echo "=========================================="
echo "✅ 所有操作完成！"
echo "=========================================="
echo ""

# 获取 Alice 和 Bob 的访问链接
echo "📱 Web UI 访问信息："
echo ""
echo "正在启动 UI 并获取访问链接..."
echo ""

# 启动 UI（如果未启动）
aln ui start --port "$UI_PORT" 2>/dev/null || true

# 等待 UI 启动
sleep 2

# 显示所有 Human 的访问链接
aln ui

echo ""
echo "=========================================="
echo "🏗️  拓扑结构："
echo "=========================================="
echo ""
echo "                 ┌─────────────────┐"
echo "                 │   ParentHost    │"
echo "                 │  (port: $PARENT_HOST_PORT)  │"
echo "                 └────────┬────────┘"
echo "                          │"
echo "              ┌───────────┴───────────┐"
echo "              │                       │"
echo "     ┌────────▼────────┐     ┌───────▼────────┐"
echo "     │ AliceLocalHost  │     │ BobLocalHost   │"
echo "     │  (port: $ALICE_HOST_PORT)  │     │  (port: $BOB_HOST_PORT)  │"
echo "     │                 │     │                │"
echo "     │  👤 Alice       │     │  👤 Bob        │"
echo "     └─────────────────┘     └────────────────┘"
echo ""
echo "=========================================="
echo "🧪 测试步骤："
echo "=========================================="
echo "1. 在浏览器中打开上面的 Alice 和 Bob 的访问链接"
echo "   （可以用不同的浏览器或隐身窗口）"
echo ""
echo "2. 在 Alice 的界面中："
echo "   - 点击「发现」或「添加好友」"
echo "   - 找到 Bob 并发送好友请求"
echo ""
echo "3. 在 Bob 的界面中："
echo "   - 接受 Alice 的好友请求"
echo ""
echo "4. 测试聊天："
echo "   - Alice 发送消息给 Bob"
echo "   - Bob 回复 Alice"
echo "   - 观察消息是否正确通过 Parent Host 路由"
echo ""
echo "💡 提示："
echo "   - Parent Host: http://127.0.0.1:$PARENT_HOST_PORT"
echo "   - Alice Host:  http://127.0.0.1:$ALICE_HOST_PORT"
echo "   - Bob Host:    http://127.0.0.1:$BOB_HOST_PORT"
echo ""
echo "📊 查看 Host 详情："
echo "   aln host detail --host $PARENT_HOST_NAME"
echo "   aln host detail --host $ALICE_HOST_NAME"
echo "   aln host detail --host $BOB_HOST_NAME"
echo ""
echo "📜 查看 Host 日志（实时）："
echo "   aln host log --host $PARENT_HOST_NAME -f"
echo "   aln host log --host $ALICE_HOST_NAME -f"
echo "   aln host log --host $BOB_HOST_NAME -f"
echo ""
echo "🛑 停止所有服务："
echo "   aln host stop --host $PARENT_HOST_NAME"
echo "   aln host stop --host $ALICE_HOST_NAME"
echo "   aln host stop --host $BOB_HOST_NAME"
echo "   aln ui stop"
echo ""
echo "🔄 如需重新测试，直接再次运行此脚本即可"
echo ""

#!/bin/bash
#
# FP Host 故障排查脚本
# 用法: bash troubleshoot.sh [PORT]
# 示例: bash troubleshoot.sh 7000
#

PORT="${1:-7000}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_section() {
    echo ""
    echo -e "${BLUE}=========================================="
    echo -e "$1"
    echo -e "==========================================${NC}"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. 检查 Python 和依赖
check_python() {
    log_section "1. Python 环境检查"

    if command -v python3 &> /dev/null; then
        log_info "Python: $(python3 --version)"
    else
        log_error "Python3 未安装"
    fi

    if command -v uv &> /dev/null; then
        log_info "uv: $(uv --version)"
    else
        log_warn "uv 未安装（可选）"
    fi

    if command -v pip3 &> /dev/null; then
        log_info "pip3: $(pip3 --version | head -1)"
    else
        log_warn "pip3 未安装"
    fi
}

# 2. 检查项目安装
check_installation() {
    log_section "2. 项目安装检查"

    if command -v aln &> /dev/null; then
        log_info "aln CLI 已安装"
        aln --version 2>/dev/null || echo "  (版本信息不可用)"
    else
        log_error "aln CLI 未安装"
        log_info "请运行: pip install -e . 或 uv sync"
    fi
}

# 3. 检查配置文件
check_config() {
    log_section "3. 配置文件检查"

    CONFIG_DIR="$HOME/.fp"
    CONFIG_FILE="$CONFIG_DIR/config.json"

    if [ -d "$CONFIG_DIR" ]; then
        log_info "配置目录存在: $CONFIG_DIR"

        if [ -f "$CONFIG_FILE" ]; then
            log_info "配置文件存在: $CONFIG_FILE"
            echo "内容:"
            cat "$CONFIG_FILE" | head -20
        else
            log_warn "配置文件不存在: $CONFIG_FILE"
        fi

        # 检查日志目录
        if [ -d "$CONFIG_DIR/logs" ]; then
            log_info "日志目录: $CONFIG_DIR/logs"
            echo "日志文件:"
            ls -lh "$CONFIG_DIR/logs/" 2>/dev/null || echo "  (空)"
        fi

        # 检查状态目录
        if [ -d "$CONFIG_DIR/hosts" ]; then
            log_info "状态目录: $CONFIG_DIR/hosts"
            echo "Host 状态:"
            ls -lh "$CONFIG_DIR/hosts/" 2>/dev/null || echo "  (空)"
        fi
    else
        log_warn "配置目录不存在: $CONFIG_DIR"
        log_info "首次运行 'aln host new' 会自动创建"
    fi
}

# 4. 检查服务状态
check_service() {
    log_section "4. 服务状态检查"

    if command -v aln &> /dev/null; then
        echo "Host 列表:"
        aln host list 2>&1 || log_error "无法获取 host 列表"
    else
        log_error "aln 命令不可用"
    fi
}

# 5. 检查端口
check_port() {
    log_section "5. 端口检查 (${PORT})"

    # 检查端口是否被监听
    if command -v lsof &> /dev/null; then
        echo "监听端口 $PORT 的进程:"
        sudo lsof -i :$PORT 2>/dev/null || log_warn "端口 $PORT 未被监听"
    elif command -v netstat &> /dev/null; then
        echo "监听端口 $PORT 的进程:"
        netstat -tuln | grep ":$PORT " || log_warn "端口 $PORT 未被监听"
    else
        log_warn "无法检查端口（缺少 lsof 或 netstat）"
    fi

    echo ""

    # 测试本地连接
    log_info "测试本地连接..."
    if command -v nc &> /dev/null; then
        if nc -z localhost $PORT 2>/dev/null; then
            log_info "✓ 本地端口 $PORT 可访问"
        else
            log_error "✗ 本地端口 $PORT 不可访问"
        fi
    fi

    echo ""

    # 测试 HTTP
    log_info "测试 HTTP 连接..."
    if curl -s --connect-timeout 3 http://localhost:$PORT/health > /dev/null 2>&1; then
        log_info "✓ HTTP 健康检查通过"
        curl -s http://localhost:$PORT/health
    else
        log_error "✗ HTTP 健康检查失败"
    fi
}

# 6. 检查防火墙
check_firewall() {
    log_section "6. 防火墙检查"

    # UFW
    if command -v ufw &> /dev/null; then
        log_info "UFW 状态:"
        sudo ufw status | grep -E "Status|$PORT" || echo "  (未启用或端口未配置)"
    fi

    # firewalld
    if command -v firewall-cmd &> /dev/null; then
        log_info "firewalld 状态:"
        sudo firewall-cmd --list-ports 2>/dev/null | grep "$PORT" || \
            log_warn "端口 $PORT 未在 firewalld 中开放"
    fi

    # iptables
    if command -v iptables &> /dev/null; then
        log_info "iptables 规则 (端口 $PORT):"
        sudo iptables -L -n | grep "$PORT" || echo "  (无相关规则)"
    fi

    if ! command -v ufw &> /dev/null && \
       ! command -v firewall-cmd &> /dev/null && \
       ! command -v iptables &> /dev/null; then
        log_warn "未检测到防火墙工具"
    fi
}

# 7. 检查网络
check_network() {
    log_section "7. 网络检查"

    # 公网 IP
    log_info "获取公网 IP..."
    PUBLIC_IP=$(curl -s --connect-timeout 5 https://api.ipify.org 2>/dev/null || echo "unknown")
    if [ "$PUBLIC_IP" != "unknown" ]; then
        log_info "公网 IP: $PUBLIC_IP"
    else
        log_warn "无法获取公网 IP"
    fi

    # 本地网络接口
    echo ""
    log_info "网络接口:"
    if command -v ip &> /dev/null; then
        ip addr show | grep -E "inet |UP" | grep -v "127.0.0.1"
    elif command -v ifconfig &> /dev/null; then
        ifconfig | grep -E "inet |UP"
    fi
}

# 8. 查看最近日志
check_logs() {
    log_section "8. 最近日志 (最后 50 行)"

    if command -v aln &> /dev/null; then
        aln host log -n 50 2>&1 || log_warn "无法读取日志"
    else
        log_warn "aln 命令不可用，尝试直接读取日志文件"
        LOG_DIR="$HOME/.fp/logs"
        if [ -d "$LOG_DIR" ]; then
            LATEST_LOG=$(ls -t "$LOG_DIR"/*.log 2>/dev/null | head -1)
            if [ -n "$LATEST_LOG" ]; then
                log_info "日志文件: $LATEST_LOG"
                tail -50 "$LATEST_LOG"
            fi
        fi
    fi
}

# 9. 系统信息
check_system() {
    log_section "9. 系统信息"

    log_info "操作系统:"
    if [ -f /etc/os-release ]; then
        cat /etc/os-release | grep -E "^NAME=|^VERSION="
    else
        uname -a
    fi

    echo ""
    log_info "内存使用:"
    free -h 2>/dev/null || log_warn "无法获取内存信息"

    echo ""
    log_info "磁盘使用:"
    df -h ~ | tail -1
}

# 10. 建议操作
show_suggestions() {
    log_section "10. 建议操作"

    echo "如果服务无法访问，请按顺序检查："
    echo ""
    echo "1. 确保服务正在运行:"
    echo "   aln host list"
    echo ""
    echo "2. 检查本地是否能访问:"
    echo "   curl http://localhost:${PORT}/health"
    echo ""
    echo "3. 检查防火墙:"
    echo "   sudo ufw allow ${PORT}/tcp"
    echo "   sudo firewall-cmd --add-port=${PORT}/tcp --permanent"
    echo "   sudo firewall-cmd --reload"
    echo ""
    echo "4. 如果是云服务器，检查安全组规则:"
    echo "   阿里云/腾讯云/AWS: 在控制台添加入站规则"
    echo "   开放端口: ${PORT}, 协议: TCP, 源: 0.0.0.0/0"
    echo ""
    echo "5. 重启服务:"
    echo "   aln host reset"
    echo ""
    echo "6. 查看完整日志:"
    echo "   aln host log -f"
    echo ""
}

# 主流程
main() {
    echo "=========================================="
    echo "FP Host 故障排查工具"
    echo "=========================================="
    echo "目标端口: $PORT"
    echo ""

    check_python
    check_installation
    check_config
    check_service
    check_port
    check_firewall
    check_network
    check_logs
    check_system
    show_suggestions

    echo ""
    echo "=========================================="
    echo "排查完成"
    echo "=========================================="
}

main

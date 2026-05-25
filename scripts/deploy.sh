#!/bin/bash
#
# FP Host 服务器部署脚本
# 用法: bash deploy.sh [PORT] [HOST_NAME]
# 示例: bash deploy.sh 7000 default
#

set -e  # 遇到错误立即退出

# 配置参数
PORT="${1:-7000}"
HOST_NAME="${2:-default}"
BIND_HOST="0.0.0.0"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检测操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        log_error "无法检测操作系统"
        exit 1
    fi
    log_info "检测到操作系统: $OS $VERSION"
}

# 检查并安装依赖
install_dependencies() {
    log_info "检查并安装系统依赖..."

    case "$OS" in
        ubuntu|debian)
            sudo apt-get update -qq
            sudo apt-get install -y python3 python3-pip python3-venv curl netcat-openbsd || \
            sudo apt-get install -y python3 python3-pip python3-venv curl netcat
            ;;
        centos|rhel|fedora)
            sudo yum install -y python3 python3-pip curl nc || \
            sudo dnf install -y python3 python3-pip curl nc
            ;;
        *)
            log_warn "未知操作系统，跳过依赖安装"
            ;;
    esac
}

# 检查 Python 版本
check_python() {
    log_info "检查 Python 版本..."

    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装"
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    log_info "Python 版本: $PYTHON_VERSION"

    # 检查版本是否 >= 3.12
    REQUIRED_VERSION="3.12"
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)"; then
        log_warn "Python 版本低于 3.12，建议升级"
    fi
}

# 安装 uv（如果没有）
install_uv() {
    log_info "检查 uv 包管理器..."

    if ! command -v uv &> /dev/null; then
        log_info "安装 uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
    else
        log_info "uv 已安装: $(uv --version)"
    fi
}

# 配置防火墙
configure_firewall() {
    log_info "配置防火墙开放端口 $PORT..."

    # UFW (Ubuntu/Debian)
    if command -v ufw &> /dev/null; then
        sudo ufw allow $PORT/tcp
        log_info "UFW: 端口 $PORT 已开放"
    fi

    # firewalld (CentOS/RHEL)
    if command -v firewall-cmd &> /dev/null; then
        sudo firewall-cmd --permanent --add-port=$PORT/tcp
        sudo firewall-cmd --reload
        log_info "firewalld: 端口 $PORT 已开放"
    fi

    # 如果都没有，提示用户
    if ! command -v ufw &> /dev/null && ! command -v firewall-cmd &> /dev/null; then
        log_warn "未检测到防火墙工具，请手动开放端口 $PORT"
    fi
}

# 检查端口是否被占用
check_port() {
    log_info "检查端口 $PORT 是否可用..."

    if command -v nc &> /dev/null; then
        if nc -z localhost $PORT 2>/dev/null; then
            log_error "端口 $PORT 已被占用"
            lsof -i :$PORT || netstat -tuln | grep :$PORT || true
            exit 1
        fi
    elif command -v netstat &> /dev/null; then
        if netstat -tuln | grep -q ":$PORT "; then
            log_error "端口 $PORT 已被占用"
            netstat -tuln | grep :$PORT
            exit 1
        fi
    fi

    log_info "端口 $PORT 可用"
}

# 安装项目依赖
install_project() {
    log_info "安装项目依赖..."

    cd "$PROJECT_DIR"

    if command -v uv &> /dev/null; then
        log_info "使用 uv 安装依赖..."
        uv sync
    else
        log_info "使用 pip 安装依赖..."
        python3 -m pip install -e .
    fi
}

# 停止现有服务
stop_existing_service() {
    log_info "检查并停止现有服务..."

    cd "$PROJECT_DIR"

    if command -v uv &> /dev/null; then
        uv run aln host stop --host "$HOST_NAME" 2>/dev/null || true
    else
        python3 -m aln.cli host stop --host "$HOST_NAME" 2>/dev/null || true
    fi

    # 额外检查：杀死占用端口的进程
    if lsof -i :$PORT &> /dev/null; then
        log_warn "强制终止占用端口 $PORT 的进程..."
        sudo lsof -ti :$PORT | xargs sudo kill -9 || true
        sleep 2
    fi
}

# 启动服务
start_service() {
    log_info "启动 FP Host 服务..."

    cd "$PROJECT_DIR"

    # 先删除旧配置（可选，谨慎使用）
    # rm -rf ~/.fp/

    if command -v uv &> /dev/null; then
        uv run aln host new --name "$HOST_NAME" --bind-host "$BIND_HOST" --port "$PORT"
    else
        python3 -m aln.cli host new --name "$HOST_NAME" --bind-host "$BIND_HOST" --port "$PORT"
    fi
}

# 验证服务
verify_service() {
    log_info "验证服务状态..."

    # 等待服务启动
    log_info "等待服务启动 (5秒)..."
    sleep 5

    # 检查进程
    cd "$PROJECT_DIR"
    if command -v uv &> /dev/null; then
        uv run aln host list
    else
        python3 -m aln.cli host list
    fi

    # 测试健康检查端点
    log_info "测试健康检查端点..."
    local max_attempts=10
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        log_info "尝试 $attempt/$max_attempts..."

        if curl -s --connect-timeout 5 http://localhost:$PORT/health > /dev/null 2>&1; then
            log_info "✓ 健康检查通过"

            # 显示响应内容
            HEALTH_RESPONSE=$(curl -s http://localhost:$PORT/health)
            echo "响应: $HEALTH_RESPONSE"
            break
        else
            if [ $attempt -eq $max_attempts ]; then
                log_error "✗ 健康检查失败"
                log_error "请检查日志:"
                if command -v uv &> /dev/null; then
                    uv run aln host log -n 20
                else
                    python3 -m aln.cli host log -n 20
                fi
                exit 1
            fi
            sleep 2
            attempt=$((attempt + 1))
        fi
    done

    # 测试 well-known 端点
    log_info "测试 well-known 端点..."
    WELLKNOWN=$(curl -s http://localhost:$PORT/.well-known/fp)
    echo "Well-known: $WELLKNOWN"
}

# 获取公网 IP
get_public_ip() {
    log_info "获取公网 IP..."

    PUBLIC_IP=$(curl -s https://api.ipify.org || curl -s https://ifconfig.me || curl -s https://icanhazip.com || echo "unknown")

    if [ "$PUBLIC_IP" != "unknown" ]; then
        log_info "公网 IP: $PUBLIC_IP"
    else
        log_warn "无法获取公网 IP"
    fi
}

# 显示访问信息
show_access_info() {
    log_info "=========================================="
    log_info "服务部署完成！"
    log_info "=========================================="
    echo ""
    log_info "本地访问:"
    echo "  健康检查: http://localhost:$PORT/health"
    echo "  API 文档: http://localhost:$PORT/docs"
    echo "  Well-known: http://localhost:$PORT/.well-known/fp"
    echo ""

    if [ "$PUBLIC_IP" != "unknown" ]; then
        log_info "外部访问:"
        echo "  健康检查: http://$PUBLIC_IP:$PORT/health"
        echo "  API 文档: http://$PUBLIC_IP:$PORT/docs"
        echo "  Well-known: http://$PUBLIC_IP:$PORT/.well-known/fp"
        echo ""
    fi

    log_info "管理命令:"
    echo "  查看状态: aln host list"
    echo "  查看详情: aln host detail"
    echo "  查看日志: aln host log"
    echo "  实时日志: aln host log -f"
    echo "  停止服务: aln host stop"
    echo "  重启服务: aln host reset"
    echo ""

    log_info "配置文件:"
    echo "  配置: ~/.fp/config.json"
    echo "  日志: ~/.fp/logs/"
    echo "  状态: ~/.fp/hosts/"
    echo ""
}

# 创建 systemd 服务（可选）
create_systemd_service() {
    log_info "是否创建 systemd 服务以实现开机自启？(y/N)"
    read -r response

    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        log_info "创建 systemd 服务..."

        SERVICE_FILE="/etc/systemd/system/fp-host-${HOST_NAME}.service"

        sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=FP Host Service - ${HOST_NAME}
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="FP_HOST_NAME=${HOST_NAME}"
ExecStart=$(which uv 2>/dev/null || which python3) $(if command -v uv &> /dev/null; then echo "run"; fi) uvicorn aln.app.main:app --host ${BIND_HOST} --port ${PORT}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

        sudo systemctl daemon-reload
        sudo systemctl enable "fp-host-${HOST_NAME}"

        log_info "✓ systemd 服务已创建"
        log_info "管理命令:"
        echo "  启动: sudo systemctl start fp-host-${HOST_NAME}"
        echo "  停止: sudo systemctl stop fp-host-${HOST_NAME}"
        echo "  状态: sudo systemctl status fp-host-${HOST_NAME}"
        echo "  日志: sudo journalctl -u fp-host-${HOST_NAME} -f"
    else
        log_info "跳过 systemd 服务创建"
    fi
}

# 主流程
main() {
    log_info "=========================================="
    log_info "FP Host 服务器部署脚本"
    log_info "=========================================="
    echo ""
    log_info "配置参数:"
    echo "  端口: $PORT"
    echo "  主机名: $HOST_NAME"
    echo "  绑定地址: $BIND_HOST"
    echo "  项目目录: $PROJECT_DIR"
    echo ""

    detect_os
    install_dependencies
    check_python
    install_uv
    configure_firewall
    check_port
    install_project
    stop_existing_service
    start_service
    verify_service
    get_public_ip
    show_access_info
    create_systemd_service

    log_info "=========================================="
    log_info "部署完成！"
    log_info "=========================================="
}

# 运行主流程
main

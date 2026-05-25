from __future__ import annotations

import socket
import subprocess


def _has_uv() -> bool:
    """Check if uv is available."""
    try:
        subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_local_ip() -> str:
    """获取本机局域网 IP 地址。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def generate_qr_lines(url: str) -> list[str]:
    """生成二维码的终端显示行。"""
    import qrcode

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)

    matrix = qr.get_matrix()
    lines: list[str] = []
    for i in range(0, len(matrix), 2):
        row = ""
        for j in range(len(matrix[i])):
            top = matrix[i][j]
            bottom = matrix[i + 1][j] if i + 1 < len(matrix) else False
            if top and bottom:
                row += "█"
            elif top:
                row += "▀"
            elif bottom:
                row += "▄"
            else:
                row += " "
        lines.append(row)
    return lines
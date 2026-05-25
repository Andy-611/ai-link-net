"""Process and port utilities."""

from __future__ import annotations

import os
import signal
import socket
import time


def is_pid_alive(pid: int) -> bool:
    """Check if a process is running by PID."""

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def is_port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    """Check if a TCP port is accepting connections."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def stop_pid(pid: int, timeout: float = 3.0) -> bool:
    """Stop a process by PID, returns True if stopped.

    Args:
        pid: Process ID to stop.
        timeout: How long to wait for graceful shutdown before force kill.

    Returns:
        True if process was stopped, False otherwise.
    """
    if not is_pid_alive(pid):
        return True

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return not is_pid_alive(pid)

    deadline = time.time() + max(timeout, 0.1)
    while time.time() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.05)

    # Force kill if still alive
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass

    time.sleep(0.05)
    return not is_pid_alive(pid)

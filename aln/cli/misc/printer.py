"""CLI output printer utilities."""

from __future__ import annotations

import json
from typing import Any

import click
from pydantic import BaseModel


class CliPrinter:
    """Structured printer for CLI output."""
    #TODO[优化]：1.CLI help 提供  self.reader = human/agent 参数，提供不同的视觉方案，这个通过装饰器实例化的时候读取 entity 身份即可,help 效果参考 uv
    def echo(self, message: str = "") -> None:
        click.echo(message)

    def print_lines(self, text: str) -> None:
        """Print multi-line text from triple-quoted string."""
        self.echo(text.strip())

    def print(self, data: Any) -> None:
        """Print data, automatically handling BaseModel or List[BaseModel]."""
        if isinstance(data, BaseModel):
            # Single BaseModel instance
            self.echo(json.dumps(data.model_dump(), indent=2, ensure_ascii=False))
        elif isinstance(data, list) and data and isinstance(data[0], BaseModel):
            # List of BaseModel instances
            dumped_list = [item.model_dump() for item in data]
            self.echo(json.dumps(dumped_list, indent=2, ensure_ascii=False))
        else:
            # Fallback to regular echo
            self.echo(str(data))

    @staticmethod
    def _extract_preview(message_kind: str, payload: Any) -> str:
        """Extract a concise preview for one mailbox message."""
        if not isinstance(payload, dict):
            return str(payload)[:50]

        if message_kind == "approval_status":
            flow_side = payload.get("flow_side")
            status = payload.get("status")
            preview = payload.get("original_preview")
            prefix = "审批通知"
            if flow_side == "inbound" and status == "pending":
                prefix = "收信审批通知"
            elif flow_side == "outbound" and status == "pending":
                prefix = "发送审批通知"
            if preview:
                return f"{prefix}: {preview}"
            message_text = payload.get("message")
            if message_text:
                return str(message_text)
            return prefix

        params = payload.get("params") or {}
        if isinstance(params, dict):
            params_text = params.get("text")
            if params_text:
                return str(params_text)

        for key in ("text", "message"):
            value = payload.get(key)
            if value:
                return str(value)

        if message_kind == "pay_completed":
            return "支付完成通知"

        return str(payload)[:50]

    def print_mail(self, mail_entry: dict[str, Any], show_full: bool = False) -> None:
        """Print mail in a human-readable format.

        TODO: 使用 MailEntry 类型替代 dict[str, Any]

        Args:
            mail_entry: Mail entry with 'mail' and 'metadata' fields
            show_full: If True, show full mail JSON; if False, show summary
        """
        mail = mail_entry.get("mail", {})
        metadata = mail_entry.get("metadata", {})

        message_id = (
            mail.get("mail_id")
            or mail.get("message_id")
            or (mail.get("message", {}).get("message_id") if isinstance(mail.get("message"), dict) else None)
            or "N/A"
        )
        sender = mail.get("sender", {}).get("address", "Unknown")
        timestamp = metadata.get("timestamp", "N/A")
        direction = metadata.get("direction", "N/A")
        is_read = metadata.get("is_read", False)
        is_handled = metadata.get("is_handled", False)

        # Extract message preview
        message = mail.get("message", {})
        if isinstance(message, str):
            message_kind = "encrypted"
            preview = "Encrypted message"
        else:
            message_kind = message.get("kind", "N/A")
            payload = message.get("payload") or {}
            preview = self._extract_preview(str(message_kind), payload)

        # Print summary
        status_icon = "📩" if direction == "inbound" else "📤"
        read_icon = "✓" if is_read else "○"
        handled_icon = "✓" if is_handled else "○"

        self.echo(f"{status_icon} [{message_id[:8]}]")
        self.echo(f"  From:      {sender}")
        self.echo(f"  Time:      {timestamp}")
        self.echo(f"  Type:      {message_kind}")
        self.echo(f"  Preview:   {str(preview)[:80]}...")
        self.echo(f"  Read:      {read_icon}  Handled: {handled_icon}")

        if show_full:
            self.echo("")
            self.echo("Full Mail:")
            self.echo(json.dumps(mail, indent=2, ensure_ascii=False))

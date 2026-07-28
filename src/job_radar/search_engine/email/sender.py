"""Send the digest over SMTP (SSL on 465, STARTTLS otherwise)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ...common.config import Config
from ...common.logger import get_logger

logger = get_logger(__name__)


class EmailSender:
    """Thin SMTP wrapper for sending the HTML+text digest."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def send(self, *, to: str, subject: str, html_body: str, text_body: str) -> None:
        cfg = self.config
        if not cfg.smtp_username or not cfg.smtp_password:
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD are required to send email")
        if not to:
            raise ValueError("No recipient (EMAIL_TO) configured")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = cfg.resolved_email_from
        msg["To"] = to
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")

        logger.info("Sending digest to %s via %s:%d", to, cfg.smtp_host, cfg.smtp_port)
        if cfg.smtp_port == 465:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port) as server:
                server.login(cfg.smtp_username, cfg.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
                server.starttls()
                server.login(cfg.smtp_username, cfg.smtp_password)
                server.send_message(msg)
        logger.info("Digest sent.")

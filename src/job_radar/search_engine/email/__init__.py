"""Email: render the daily digest and send it over SMTP."""

from .renderer import render_digest
from .sender import EmailSender

__all__ = ["EmailSender", "render_digest"]

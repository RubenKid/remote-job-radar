"""Turn source HTML job descriptions into clean, readable plain text."""

from __future__ import annotations

import html as _html
import re

_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)
_LI = re.compile(r"<li[^>]*>", re.IGNORECASE)
_BLOCK = re.compile(
    r"</(p|div|li|ul|ol|h[1-6]|tr|table|section|article|header|footer|blockquote)\s*>",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")


def html_to_text(raw: str) -> str:
    """Decode entities and strip tags, preserving paragraph/list line breaks.

    Job boards hand back HTML (``<p>``, ``<br>``, ``&nbsp;``, ``&euro;`` …).
    Rendered as-is in a ``pre-wrap`` block those show up as literal markup, so
    we normalise to plain text: block tags become newlines, ``<li>`` becomes a
    bullet, remaining tags are dropped, and entities are decoded.
    """
    if not raw:
        return ""
    s = raw
    s = _BR.sub("\n", s)
    s = _LI.sub("\n• ", s)
    s = _BLOCK.sub("\n", s)
    s = _TAG.sub("", s)  # drop any remaining tags
    s = _html.unescape(s)  # &nbsp; &euro; &amp; … -> real characters
    s = s.replace("\xa0", " ")  # non-breaking space -> normal space
    # Collapse whitespace without flattening intentional paragraph breaks.
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

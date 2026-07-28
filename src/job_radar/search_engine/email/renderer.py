"""Render the daily digest as HTML + plain-text."""

from __future__ import annotations

import html

from ...common.models import ScoredJob


def _esc(text: str) -> str:
    return html.escape(text or "")


def _score_color(score: int) -> str:
    if score >= 80:
        return "#1a7f37"
    if score >= 60:
        return "#9a6700"
    return "#57606a"


def _job_card(scored: ScoredJob) -> str:
    job = scored.job
    ev = scored.evaluation
    score = scored.final_score
    reasons = ev.reasons if ev else []
    missing = ev.missing_skills if ev else []

    reasons_html = "".join(f"<li>{_esc(r)}</li>" for r in reasons)
    missing_html = (
        f'<p style="margin:6px 0 0;color:#57606a;font-size:13px">'
        f'<strong>Missing:</strong> {_esc(", ".join(missing))}</p>'
        if missing
        else ""
    )
    # Only show the numeric score when the AI produced an evaluation (reasons);
    # in free mode the local keyword score isn't a 0-100 fit and would mislead.
    score_html = (
        f'<span style="font-weight:700;font-size:16px;color:{_score_color(score)}">{score}</span>'
        if reasons
        else ""
    )
    return f"""\
<div style="border:1px solid #d0d7de;border-radius:10px;padding:16px;margin:0 0 14px">
  <div style="display:flex;justify-content:space-between;align-items:baseline">
    <h3 style="margin:0;font-size:17px">
      <a href="{_esc(job.url)}" style="color:#0969da;text-decoration:none">{_esc(job.title)}</a>
    </h3>
    {score_html}
  </div>
  <p style="margin:4px 0 8px;color:#57606a;font-size:14px">
    {_esc(job.company)} &middot; {_esc(job.remote_region)}
    {(" &middot; " + _esc(job.location)) if job.location else ""}
    &middot; <span style="color:#8c959f">{_esc(job.source)}</span>
  </p>
  <ul style="margin:0;padding-left:18px;font-size:14px;color:#24292f">{reasons_html}</ul>
  {missing_html}
  <p style="margin:10px 0 0">
    <a href="{_esc(job.url)}"
       style="background:#0969da;color:#fff;padding:7px 14px;border-radius:6px;
              text-decoration:none;font-size:14px;display:inline-block">Apply →</a>
  </p>
</div>"""


def render_digest(jobs: list[ScoredJob], profile_summary: str = "") -> tuple[str, str]:
    """Return (html_body, text_body) for the digest email."""
    count = len(jobs)
    heading = f"{count} new remote {'opportunity' if count == 1 else 'opportunities'}"

    cards = "".join(_job_card(s) for s in jobs)
    intro = (
        f'<p style="color:#57606a;font-size:14px;margin:0 0 16px">{_esc(profile_summary)}</p>'
        if profile_summary
        else ""
    )
    html_body = f"""\
<!doctype html>
<html><body style="margin:0;background:#f6f8fa;padding:24px;
  font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
  <div style="max-width:640px;margin:0 auto">
    <h1 style="font-size:22px;margin:0 0 4px">🛰️ Remote Job Radar</h1>
    <p style="color:#57606a;margin:0 0 18px;font-size:14px">{heading} matched to your profile.</p>
    {intro}
    {cards}
    <p style="color:#8c959f;font-size:12px;margin:20px 0 0">
      You received this because you enabled the Remote Job Radar daily digest.
    </p>
  </div>
</body></html>"""

    text_lines = [f"Remote Job Radar — {heading}", ""]
    for s in jobs:
        j = s.job
        prefix = f"[{s.final_score}] " if (s.evaluation and s.evaluation.reasons) else ""
        text_lines.append(f"{prefix}{j.title} — {j.company} ({j.remote_region})")
        if s.evaluation:
            for r in s.evaluation.reasons:
                text_lines.append(f"  - {r}")
            if s.evaluation.missing_skills:
                text_lines.append(f"  Missing: {', '.join(s.evaluation.missing_skills)}")
        text_lines.append(f"  Apply: {j.url}")
        text_lines.append("")
    text_body = "\n".join(text_lines)

    return html_body, text_body

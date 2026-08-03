from job_radar.common.text import html_to_text


def test_decodes_entities_and_nbsp():
    assert html_to_text("Raised &euro;115 million&nbsp;total") == "Raised €115 million total"


def test_strips_tags_and_keeps_paragraph_breaks():
    html = "<p>About Finom</p><p>We build <strong>finance</strong> tools.</p>"
    assert html_to_text(html) == "About Finom\nWe build finance tools."


def test_br_and_list_items_become_lines_and_bullets():
    html = "Stack:<br><ul><li>Kotlin</li><li>Jetpack Compose</li></ul>"
    out = html_to_text(html)
    assert "• Kotlin" in out
    assert "• Jetpack Compose" in out


def test_collapses_excess_blank_lines_and_whitespace():
    out = html_to_text("<div>A</div>\n\n\n\n<div>   B   </div>")
    assert out == "A\n\nB"


def test_empty_input():
    assert html_to_text("") == ""
    assert html_to_text(None) == ""  # type: ignore[arg-type]

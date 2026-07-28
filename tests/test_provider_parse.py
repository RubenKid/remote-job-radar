import pytest

from job_radar.providers.base import LLMProvider


def test_parse_bare_json():
    assert LLMProvider.parse_json('{"a": 1}') == {"a": 1}


def test_parse_fenced_json():
    text = "Here you go:\n```json\n{\"score\": 90}\n```\nDone."
    assert LLMProvider.parse_json(text) == {"score": 90}


def test_parse_json_with_surrounding_prose():
    assert LLMProvider.parse_json('Result: {"ok": true} end') == {"ok": True}


def test_parse_empty_raises():
    with pytest.raises(ValueError):
        LLMProvider.parse_json("   ")

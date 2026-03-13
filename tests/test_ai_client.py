"""
Tests for the shared AI client module.
"""
import pytest
from ai_client import (
    call_claude,
    parse_json_response,
    strip_markdown_fences,
    AIClientError,
)


class TestStripMarkdownFences:
    def test_json_fences(self):
        assert strip_markdown_fences('```json\n{"a":1}\n```') == '{"a":1}'

    def test_html_fences(self):
        assert strip_markdown_fences('```html\n<div></div>\n```') == '<div></div>'

    def test_plain_fences(self):
        assert strip_markdown_fences('```\ncode\n```') == 'code'

    def test_no_fences(self):
        assert strip_markdown_fences('no fences here') == 'no fences here'

    def test_empty_string(self):
        assert strip_markdown_fences('') == ''

    def test_whitespace_preserved(self):
        result = strip_markdown_fences('```\nline1\nline2\n```')
        assert 'line1\nline2' == result


class TestParseJsonResponse:
    def test_clean_json(self):
        result = parse_json_response('{"key": "value"}')
        assert result == {'key': 'value'}

    def test_fenced_json(self):
        result = parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {'key': 'value'}

    def test_json_with_surrounding_text(self):
        result = parse_json_response('Here is the result: {"key": "value"} done.')
        assert result == {'key': 'value'}

    def test_invalid_json_raises(self):
        with pytest.raises(AIClientError):
            parse_json_response('not json at all')

    def test_custom_error_class(self):
        class MyError(Exception):
            pass
        with pytest.raises(MyError):
            parse_json_response('not json', error_class=MyError)


class TestCallClaude:
    def test_missing_api_key_raises(self, monkeypatch):
        monkeypatch.delenv('CLAUDE_API_KEY', raising=False)
        with pytest.raises(AIClientError, match="CLAUDE_API_KEY"):
            call_claude("system", "user")

    def test_custom_error_class(self, monkeypatch):
        monkeypatch.delenv('CLAUDE_API_KEY', raising=False)

        class MyError(Exception):
            pass
        with pytest.raises(MyError):
            call_claude("system", "user", error_class=MyError)

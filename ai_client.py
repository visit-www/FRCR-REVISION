"""
Shared AI Client — Unified Anthropic API helpers.

Consolidates duplicate _call_claude(), _parse_json_response(), and
_strip_markdown_fences() implementations from ai_smart_reporter.py,
clinical_tool_generator.py, and ai_tnm.py.

All AI modules should import from here instead of duplicating API logic.
"""

import json
import os
import re
import logging

import requests

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    """Base exception for AI API call failures."""
    pass


def call_claude(system_prompt, user_prompt, model=None, max_tokens=4000,
                temperature=0.3, timeout=60, error_class=None):
    """
    Call the Anthropic Messages API.

    Args:
        system_prompt: System message string (must be plain string, NOT array)
        user_prompt: User message string
        model: Override model (defaults to CLAUDE_MODEL env var)
        max_tokens: Max response tokens
        temperature: Sampling temperature
        timeout: Request timeout in seconds
        error_class: Exception class to raise on failure (default: AIClientError)

    Returns:
        tuple: (response_text: str, model_used: str, token_count: int)

    Raises:
        error_class (or AIClientError) on any failure
    """
    exc = error_class or AIClientError

    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise exc("CLAUDE_API_KEY not configured.")

    effective_model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    payload = {
        "model": effective_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        raise exc("Request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        raise exc(f"API connection error: {e}")

    if response.status_code >= 300:
        detail = response.text[:500]
        raise exc(f"API error (HTTP {response.status_code}): {detail}")

    result = response.json()
    content = result.get("content", [])
    if not content:
        raise exc("Empty response from API.")

    text = content[0].get("text", "").strip()
    if not text:
        raise exc("No text in API response.")

    token_count = result.get("usage", {}).get("output_tokens", 0)
    return text, effective_model, token_count


def strip_markdown_fences(text):
    """Strip markdown code fences (```json ... ```) from AI output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    return cleaned


def parse_json_response(text, error_class=None):
    """
    Parse JSON from AI response with markdown fence stripping and regex fallback.

    Args:
        text: Raw AI response text
        error_class: Exception class to raise on failure (default: AIClientError)

    Returns:
        Parsed dict/list

    Raises:
        error_class (or AIClientError) on parse failure
    """
    exc = error_class or AIClientError
    cleaned = strip_markdown_fences(text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                logger.warning("JSON fallback parse failed. Raw: %s", cleaned[:500])
                raise exc("Failed to parse AI response as JSON.")
        raise exc("AI response was not valid JSON.")

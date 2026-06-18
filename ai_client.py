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
    """Base exception for all AI/generator failures.

    All module-specific errors inherit from this, enabling callers to
    catch AIClientError for any AI-related failure regardless of source.
    """
    pass


# ── Shared ABC preamble — prepended to all content-generating prompts ──
ABC_PREAMBLE = (
    "CORE PRINCIPLES (apply to ALL your output):\n"
    "A — ACCURACY: Every claim must be factually and radiologically correct. "
    "Do not fabricate statistics, measurements, or prevalences. If uncertain, "
    "omit rather than guess.\n"
    "B — BREVITY: Every sentence must earn its place. No filler, no preamble, "
    "no restating the question. Be concise and direct.\n"
    "C — CLINICAL RELEVANCE: Every statement must matter at the workstation or "
    "in the report. Omit textbook padding that does not change reporting or "
    "management.\n\n"
    "OFF-TOPIC GUARD: You are a radiology-specific AI. If the query is clearly "
    "unrelated to radiology, medical imaging, or clinical medicine (e.g. geography, "
    "maths, cooking, sports, trivia, coding), respond with ONLY a short, friendly "
    "one-liner redirecting the user. Example: "
    "'This falls outside my radiology expertise — please try a general-purpose "
    "assistant. I\\'m here for imaging, reporting, and clinical radiology queries!' "
    "Do NOT produce a full structured response for off-topic queries.\n\n"
)


def call_claude(system_prompt, user_prompt, model=None, max_tokens=4000,
                temperature=0.3, timeout=60, error_class=None,
                skip_preamble=False, assistant_prefill=None):
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
        skip_preamble: If True, omit the ABC_PREAMBLE (for classification
                       or structural tasks that don't generate clinical content)
        assistant_prefill: If set, seed the assistant turn with this partial
                       text so the model CONTINUES from where it left off.
                       Used to recover from max_tokens truncation — call again
                       with the truncated output and concatenate the result.
                       The returned text is ONLY the continuation, not the seed.

    Returns:
        tuple: (response_text: str, model_used: str, token_count: int)

    After each call, `call_claude.last_stop_reason` holds the API stop_reason
    ("end_turn", "max_tokens", etc.) so callers can detect truncation without
    breaking the 3-tuple return contract.

    Raises:
        error_class (or AIClientError) on any failure
    """
    exc = error_class or AIClientError

    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise exc("CLAUDE_API_KEY not configured.")

    effective_model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    effective_system = system_prompt
    if not skip_preamble:
        effective_system = ABC_PREAMBLE + system_prompt

    messages = [{"role": "user", "content": user_prompt}]
    if assistant_prefill:
        # Anthropic rejects assistant turns ending in trailing whitespace.
        messages.append({"role": "assistant", "content": assistant_prefill.rstrip()})

    payload = {
        "model": effective_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": effective_system,
        "messages": messages,
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

    # Check if output was truncated due to max_tokens
    stop_reason = result.get("stop_reason", "")
    # Expose to callers (e.g. continuation loops) without breaking the 3-tuple.
    call_claude.last_stop_reason = stop_reason
    if stop_reason == "max_tokens":
        logger.warning(
            "API output truncated (hit max_tokens=%d). Output may be incomplete.",
            max_tokens,
        )

    usage = result.get("usage", {})
    token_count = usage.get("output_tokens", 0)
    # Store last usage info for cost tracking (avoids breaking 3-tuple return)
    # Cache tokens: cache_read is 90% cheaper, cache_creation is 25% more expensive
    call_claude.last_usage = {
        'input_tokens': usage.get("input_tokens", 0),
        'output_tokens': token_count,
        'cache_creation_input_tokens': usage.get("cache_creation_input_tokens", 0),
        'cache_read_input_tokens': usage.get("cache_read_input_tokens", 0),
    }
    return text, effective_model, token_count


def call_claude_thinking(system_prompt, user_prompt, model=None, max_tokens=16000,
                         timeout=120, error_class=None, skip_preamble=False):
    """
    Call the Anthropic Messages API with extended thinking (adaptive mode).

    Uses adaptive thinking — the model reasons internally before producing
    its output.  Temperature is not supported with thinking and is omitted.

    Args:
        system_prompt: System message string
        user_prompt: User message string
        model: Override model (defaults to CLAUDE_MODEL env var)
        max_tokens: Max response tokens (must exceed thinking budget)
        timeout: Request timeout in seconds (default 120 — thinking takes longer)
        error_class: Exception class to raise on failure
        skip_preamble: If True, omit the ABC_PREAMBLE

    Returns:
        tuple: (response_text: str, thinking_text: str, model_used: str, token_count: int)
    """
    exc = error_class or AIClientError

    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise exc("CLAUDE_API_KEY not configured.")

    effective_model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    effective_system = system_prompt
    if not skip_preamble:
        effective_system = ABC_PREAMBLE + system_prompt

    payload = {
        "model": effective_model,
        "max_tokens": max_tokens,
        "thinking": {
            "type": "enabled",
            "budget_tokens": max_tokens - 4096,
        },
        "system": effective_system,
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

    # Extract thinking and text blocks
    thinking_text = ""
    response_text = ""
    for block in content:
        if block.get("type") == "thinking":
            thinking_text = block.get("thinking", "")
        elif block.get("type") == "text":
            response_text = block.get("text", "").strip()

    if not response_text:
        raise exc("No text in API response.")

    stop_reason = result.get("stop_reason", "")
    if stop_reason == "max_tokens":
        logger.warning(
            "API output truncated (hit max_tokens=%d). Output may be incomplete.",
            max_tokens,
        )

    token_count = result.get("usage", {}).get("output_tokens", 0)
    return response_text, thinking_text, effective_model, token_count


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
        pass

    # Fallback 1: extract outermost { ... }
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback 2: truncated JSON — try closing open braces/brackets
    candidate = cleaned
    if not candidate.startswith('{'):
        m = re.search(r'\{', candidate)
        if m:
            candidate = candidate[m.start():]
    if candidate.startswith('{') and not candidate.rstrip().endswith('}'):
        candidate = candidate.rstrip()
        # If truncation happened mid-string, the final value has an unterminated
        # quote — close it before balancing brackets. Count UNESCAPED quotes;
        # an odd count means we're inside a string literal.
        unescaped_quotes = len(re.findall(r'(?<!\\)"', candidate))
        if unescaped_quotes % 2 == 1:
            candidate += '"'
        else:
            # Not mid-string: a dangling key/comma can't be repaired — drop it.
            candidate = candidate.rstrip(',')
        # Count unclosed braces/brackets and close them
        opens = candidate.count('{') - candidate.count('}')
        open_brackets = candidate.count('[') - candidate.count(']')
        candidate += ']' * max(0, open_brackets) + '}' * max(0, opens)
        try:
            result = json.loads(candidate)
            logger.warning("JSON repaired (truncated output — %d braces closed)", opens)
            return result
        except json.JSONDecodeError:
            pass

    logger.warning("JSON parse failed. Raw: %s", cleaned[:500])
    raise exc("Failed to parse AI response as JSON.")

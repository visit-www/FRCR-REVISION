"""
AI Cost Tracker — Standalone cost tracking module for RadInsights.

Centralises:
1. Model pricing (Anthropic per-million-token rates)
2. Cost calculation
3. Usage logging (wraps models.log_ai_usage)
4. Input/output token capture from ai_client.call_claude
5. Admin cost badge helper

Usage:
    from ai_cost_tracker import track_ai_call, calc_cost, get_last_usage

    # After any AI call — logs to AIAuditLog and returns cost
    cost = track_ai_call(
        user_id=current_user.id,
        action='ai_assist',
        model=result.get('model', ''),
        input_tokens=result.get('input_tokens'),
        output_tokens=result.get('output_tokens') or result.get('token_count'),
        input_summary=question[:500],
    )

    # Or use get_last_usage() to read tokens from the last call_claude call
    usage = get_last_usage()  # {'input_tokens': N, 'output_tokens': N}

    # Pure cost calculation (no DB write)
    cost = calc_cost('claude-opus-4-6', input_tokens=5000, output_tokens=800)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic pricing per million tokens (verified June 2026)
# NOTE: The Opus 4.5+ generation is $5/$25 — NOT the legacy Opus 3/4.0/4.1
# rate of $15/$75. The old table priced Opus 4.5/4.6 at $15/$75, which
# over-counted Opus cost ~3x in all reporting. Corrected below.
# ---------------------------------------------------------------------------
MODEL_COSTS = {
    # Sonnet family (current + legacy for historical cost tracking)
    'claude-sonnet-4-6':          {'input': 3.00, 'output': 15.00},
    'claude-sonnet-4-5-20250929': {'input': 3.00, 'output': 15.00},
    'claude-sonnet-4-20250514':   {'input': 3.00, 'output': 15.00},
    # Opus family (4.5+ generation: $5/$25)
    'claude-opus-4-8':            {'input': 5.00, 'output': 25.00},
    'claude-opus-4-7':            {'input': 5.00, 'output': 25.00},
    'claude-opus-4-6':            {'input': 5.00, 'output': 25.00},
    'claude-opus-4-5-20251101':   {'input': 5.00, 'output': 25.00},
    # Haiku family
    'claude-haiku-4-5-20251001':  {'input': 1.00, 'output': 5.00},
    # Gemini (for CMV peer review cost tracking)
    'gemini-2.5-flash':           {'input': 0.15, 'output': 0.60},
}

# Fallback for unknown/new models
DEFAULT_MODEL_COST = {'input': 3.00, 'output': 15.00}


def calc_cost(model: str, input_tokens: int = 0, output_tokens: int = 0,
              cache_creation_input_tokens: int = 0,
              cache_read_input_tokens: int = 0) -> float:
    """Calculate USD cost from model name and token counts.

    Uses substring matching so 'claude-opus-4-6-20250917' matches 'claude-opus-4-6'.
    Cache pricing: cache_creation = 1.25x input, cache_read = 0.1x input.
    """
    rates = DEFAULT_MODEL_COST
    model_str = model or ''
    for key, val in MODEL_COSTS.items():
        if key in model_str:
            rates = val
            break
    inp = (input_tokens or 0) * rates['input'] / 1_000_000
    out = (output_tokens or 0) * rates['output'] / 1_000_000
    cache_write = (cache_creation_input_tokens or 0) * rates['input'] * 1.25 / 1_000_000
    cache_read = (cache_read_input_tokens or 0) * rates['input'] * 0.1 / 1_000_000
    return round(inp + out + cache_write + cache_read, 6)


def get_last_usage() -> dict:
    """Read input_tokens and output_tokens from the last call_claude() call.

    Returns {'input_tokens': int, 'output_tokens': int}.
    Safe to call even if call_claude hasn't been called yet.
    """
    try:
        from ai_client import call_claude
        return getattr(call_claude, 'last_usage', {
            'input_tokens': 0,
            'output_tokens': 0,
        })
    except ImportError:
        return {'input_tokens': 0, 'output_tokens': 0}


def track_ai_call(
    user_id: int,
    action: str,
    model: str = '',
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    input_summary: Optional[str] = None,
    status: str = 'success',
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    auto_capture_tokens: bool = True,
) -> float:
    """Log an AI call to AIAuditLog and return the calculated cost.

    If auto_capture_tokens is True and input/output tokens are not provided,
    reads them from call_claude.last_usage (set after each Anthropic API call).

    Args:
        user_id: Current user ID
        action: Action identifier (e.g. 'ai_assist', 'generate_tree', 'radiq_query')
        model: Model name string from API response
        input_tokens: Input token count (auto-captured if None)
        output_tokens: Output token count (auto-captured if None)
        input_summary: Truncated input for audit context (max 500 chars)
        status: 'success', 'error', or 'rate_limited'
        error_message: Error details if status != 'success'
        duration_ms: Call duration in milliseconds
        auto_capture_tokens: If True, read tokens from last call_claude call

    Returns:
        float: Calculated USD cost for this call
    """
    # Auto-capture tokens from last API call if not explicitly provided
    cache_creation = 0
    cache_read = 0
    if auto_capture_tokens and (input_tokens is None or output_tokens is None):
        usage = get_last_usage()
        if input_tokens is None:
            input_tokens = usage.get('input_tokens', 0)
        if output_tokens is None:
            output_tokens = usage.get('output_tokens', 0)
        cache_creation = usage.get('cache_creation_input_tokens', 0)
        cache_read = usage.get('cache_read_input_tokens', 0)

    # Calculate cost (including cache token pricing)
    cost = calc_cost(model, input_tokens, output_tokens,
                     cache_creation_input_tokens=cache_creation,
                     cache_read_input_tokens=cache_read)

    # Log to database
    try:
        from models import log_ai_usage
        log_ai_usage(
            user_id=user_id,
            action=action,
            provider='anthropic',
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_summary=input_summary,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        logger.debug("AI cost tracking log failed: %s", exc)

    return cost


def admin_cost_response(user, model: str, result: dict) -> Optional[float]:
    """Return cost for admin users, None for non-admin.

    Convenience helper for route handlers that want to include
    api_cost_usd in their JSON response for admin users only.

    Args:
        user: Flask-Login current_user object
        model: Model name string
        result: AI function result dict (checks output_tokens, token_count, input_tokens)

    Returns:
        float cost if user is admin, None otherwise
    """
    if not getattr(user, 'is_admin', False):
        return None

    out_tokens = result.get('output_tokens') or result.get('token_count') or 0
    in_tokens = result.get('input_tokens') or 0

    # Always try last_usage for any missing token counts
    if not in_tokens or not out_tokens:
        usage = get_last_usage()
        if not in_tokens:
            in_tokens = usage.get('input_tokens', 0)
        if not out_tokens:
            out_tokens = usage.get('output_tokens', 0)

    return calc_cost(model, in_tokens, out_tokens)

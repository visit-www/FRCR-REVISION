import json
import os
from datetime import datetime

import requests


class AiPrelimError(Exception):
    pass


def _build_prompt(case_context):
    diagnosis = case_context.get("diagnosis", "").strip()
    module = case_context.get("module", "").strip()
    body_part = case_context.get("body_part", "").strip()
    notes = case_context.get("notes", "").strip()
    existing_summary = case_context.get("existing_summary", "").strip()
    sources = case_context.get("sources", [])

    system_prompt = (
        "You are a clinical radiology knowledge engine for FRCR-level training. "
        "Generate high-yield, clinically safe preliminary case data. "
        "Do not invent unsupported facts. If unsure, omit the claim. "
        "Output JSON only. No markdown fences."
    )

    source_list = "\n".join(f"- {s}" for s in sources) if sources else "None provided"

    user_prompt = (
        "INPUT\n"
        f"Diagnosis: {diagnosis or 'MISSING'}\n"
        f"Module: {module or 'UNKNOWN'}\n"
        f"Body part: {body_part or 'UNKNOWN'}\n"
        f"Notes: {notes or 'None'}\n"
        f"Existing summary: {existing_summary or 'None'}\n"
        "\n"
        "Allowed open-web sources (link-based):\n"
        f"{source_list}\n"
        "\n"
        "OUTPUT STRUCTURE (JSON only):\n"
        "{\n"
        '  "qa_pairs": [{"question": "...", "answer": "..."}],\n'
        '  "discussion": "...",\n'
        '  "safety_checklist": ["..."],\n'
        '  "teaching_image": {\n'
        '    "title": "...",\n'
        '    "link": "...",\n'
        '    "description": "...",\n'
        '    "teaching_point": "...",\n'
        '    "source": "..." \n'
        "  },\n"
        '  "sources": [{"title": "...", "url": "..."}],\n'
        '  "warnings": ["..."]\n'
        "}\n"
        "\n"
        "RULES\n"
        "- Use diagnosis as anchor; do not replace it.\n"
        "- If no reliable information is available, leave sections empty and add a warning.\n"
        "- Keep answers concise and clinically actionable.\n"
    )

    return system_prompt, user_prompt


def generate_prelim_case_data(case_context, provider="claude"):
    if provider != "claude":
        raise AiPrelimError("Unsupported provider")

    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise AiPrelimError("CLAUDE_API_KEY is not configured")

    system_prompt, user_prompt = _build_prompt(case_context)
    model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20240620")

    payload = {
        "model": model,
        "max_tokens": 2200,
        "temperature": 0.2,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
    }

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        data=json.dumps(payload),
        timeout=60,
    )

    if response.status_code >= 300:
        raise AiPrelimError(
            f"Claude API error {response.status_code}: {response.text}"
        )

    data = response.json()
    content = data.get("content", [])
    if not content:
        raise AiPrelimError("Claude response missing content")

    text = content[0].get("text", "").strip()
    if not text:
        raise AiPrelimError("Claude response empty")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AiPrelimError("Claude response was not valid JSON") from exc

    parsed.setdefault("qa_pairs", [])
    parsed.setdefault("discussion", "")
    parsed.setdefault("safety_checklist", [])
    parsed.setdefault("teaching_image", {})
    parsed.setdefault("sources", [])
    parsed.setdefault("warnings", [])

    return {
        "provider": provider,
        "model": model,
        "prompt_version": "v1",
        "generated_at": datetime.utcnow().isoformat(),
        "output": parsed,
        "raw_response": text,
    }

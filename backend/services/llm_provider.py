"""
Claude-first LLM provider with Gemini and OpenRouter fallbacks.

This keeps ArXLearn's model calls swappable from Railway environment
variables without forcing each feature to know provider-specific payloads.
"""
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / ".env")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMProviderError(RuntimeError):
    """Raised when no configured provider can satisfy an LLM request."""


def extract_json_from_response(text: str) -> Any:
    """Extract JSON from model output, handling code fences and surrounding prose."""
    text = (text or "").strip()
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if json_match:
        text = json_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    object_start = text.find("{")
    array_start = text.find("[")

    # Use whichever JSON opener appears first. Arrays contain objects, so
    # preferring "{" would corrupt fenced/prose-wrapped arrays.
    if array_start != -1 and (object_start == -1 or array_start < object_start):
        array_end = text.rfind("]") + 1
        if array_end > array_start:
            return json.loads(text[array_start:array_end])

    object_end = text.rfind("}") + 1
    if object_start != -1 and object_end > object_start:
        return json.loads(text[object_start:object_end])

    array_end = text.rfind("]") + 1
    if array_start != -1 and array_end > array_start:
        return json.loads(text[array_start:array_end])

    raise json.JSONDecodeError("No JSON object or array found", text, 0)


def has_provider(use_search: bool = False) -> bool:
    """Return whether at least one provider is configured for this task."""
    return bool(_provider_order(use_search=use_search))


async def generate_json(
    prompt: str,
    *,
    system: str = "",
    task: str = "general",
    use_search: bool = False,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    search_prompt: Optional[str] = None,
) -> Any:
    """Generate and parse JSON using the configured provider chain."""
    text = await generate_text(
        prompt,
        system=system,
        task=task,
        use_search=use_search,
        max_tokens=max_tokens,
        temperature=temperature,
        search_prompt=search_prompt,
    )
    try:
        return extract_json_from_response(text)
    except json.JSONDecodeError as parse_error:
        repair_prompt = f"""The text below was intended to be valid JSON for task "{task}", but parsing failed:
{parse_error}

Repair it into valid JSON while preserving the original fields and values.
Do not add invented facts or new records. If the text is incomplete, keep only complete records that are visible.
Return ONLY valid JSON.

TEXT:
{text[:24000]}"""

        repaired = await generate_text(
            repair_prompt,
            task=f"{task}_json_repair",
            use_search=False,
            max_tokens=max(4096, min(max_tokens, 8192)),
            temperature=0.0,
        )
        return extract_json_from_response(repaired)


async def generate_text(
    prompt: str,
    *,
    system: str = "",
    task: str = "general",
    use_search: bool = False,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    search_prompt: Optional[str] = None,
) -> str:
    """
    Generate text through Claude first, then fall back to configured legacy providers.

    LLM_PROVIDER can be "auto", "claude", "gemini", or "openrouter".
    LLM_FALLBACK_ENABLED defaults to true so production has safety rails.
    """
    errors: list[str] = []
    for provider in _provider_order(use_search=use_search):
        try:
            if provider == "claude":
                return await _call_claude(
                    prompt,
                    system=system,
                    task=task,
                    use_search=use_search,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    search_prompt=search_prompt,
                )
            if provider == "gemini":
                return await _call_gemini(prompt, max_tokens=max_tokens, temperature=temperature)
            if provider == "openrouter":
                return await _call_openrouter(
                    prompt,
                    system=system,
                    use_search=use_search,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    search_prompt=search_prompt,
                )
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
            continue

    suffix = f" Errors: {'; '.join(errors)}" if errors else ""
    raise LLMProviderError(f"No LLM provider succeeded for task '{task}'.{suffix}")


def _provider_order(*, use_search: bool) -> list[str]:
    preferred = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    fallback_enabled = os.getenv("LLM_FALLBACK_ENABLED", "true").lower() != "false"
    claude_search_enabled = os.getenv("CLAUDE_SEARCH_ENABLED", "true").lower() != "false"

    if preferred not in {"auto", "claude", "gemini", "openrouter"}:
        preferred = "auto"

    available = {
        "claude": bool(os.getenv("ANTHROPIC_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
    }

    if preferred != "auto":
        order = [preferred]
        if fallback_enabled:
            order.extend(["claude", "openrouter", "gemini"] if use_search else ["claude", "gemini", "openrouter"])
    else:
        if use_search and not claude_search_enabled:
            order = ["openrouter", "claude", "gemini"]
        else:
            order = ["claude", "openrouter", "gemini"] if use_search else ["claude", "gemini", "openrouter"]

    seen = set()
    return [p for p in order if available.get(p) and not (p in seen or seen.add(p))]


async def _call_claude(
    prompt: str,
    *,
    system: str,
    task: str,
    use_search: bool,
    max_tokens: int,
    temperature: float,
    search_prompt: Optional[str],
) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise LLMProviderError("ANTHROPIC_API_KEY is not configured")

    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    if use_search and os.getenv("CLAUDE_SEARCH_ENABLED", "true").lower() != "false":
        max_uses = int(os.getenv("CLAUDE_SEARCH_MAX_USES", "3"))
        payload["tools"] = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_uses,
        }]
        if search_prompt:
            payload["system"] = "\n\n".join(part for part in [system, search_prompt] if part)

    headers = {
        "x-api-key": api_key,
        "anthropic-version": os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
        "content-type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(ANTHROPIC_URL, headers=headers, json=payload, timeout=120.0)
        response.raise_for_status()
        data = response.json()

    parts = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))

    text = "\n".join(part for part in parts if part).strip()
    if not text:
        raise LLMProviderError(f"Claude returned no text for task '{task}'")
    return text


async def _call_gemini(prompt: str, *, max_tokens: int, temperature: float) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise LLMProviderError("GEMINI_API_KEY is not configured")

    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"{GEMINI_URL.format(model=model)}?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=120.0)
        response.raise_for_status()
        data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def _call_openrouter(
    prompt: str,
    *,
    system: str,
    use_search: bool,
    max_tokens: int,
    temperature: float,
    search_prompt: Optional[str],
) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise LLMProviderError("OPENROUTER_API_KEY is not configured")

    model = os.getenv(
        "OPENROUTER_SEARCH_MODEL" if use_search else "OPENROUTER_MODEL",
        "openai/gpt-4o-mini:online" if use_search else os.getenv("DEFAULT_MODEL", "openai/gpt-4o-mini"),
    )
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if use_search:
        payload["plugins"] = [{
            "id": "web",
            "max_results": int(os.getenv("OPENROUTER_SEARCH_MAX_RESULTS", "3")),
            "search_prompt": search_prompt or "Search for accurate educational sources.",
        }]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("LLM_HTTP_REFERER", "https://arxlearn.app"),
        "X-Title": os.getenv("LLM_APP_TITLE", "arXlearn"),
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120.0)
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"]

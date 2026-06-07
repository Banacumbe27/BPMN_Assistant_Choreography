import json
import re
from typing import Any


def _find_first_json_snippet(text: str) -> str | None:
    """
    Find the first decodable JSON object/array snippet inside arbitrary text.
    """
    decoder = json.JSONDecoder()

    for idx, char in enumerate(text):
        if char not in ["{", "["]:
            continue
        try:
            _, end = decoder.raw_decode(text[idx:])
            return text[idx:idx + end]
        except json.JSONDecodeError:
            continue

    return None


def parse_json_loose(raw_output: str) -> Any:
    """
    Parse JSON from raw model output with fallbacks for common wrappers like
    markdown code fences and leading/trailing prose.
    """
    cleaned = raw_output.strip()
    candidates: list[str] = []

    if cleaned:
        candidates.append(cleaned)

    fenced_blocks = re.findall(
        r"```(?:json)?\s*([\s\S]*?)\s*```",
        cleaned,
        flags=re.IGNORECASE,
    )
    for block in fenced_blocks:
        candidate = block.strip()
        if candidate:
            candidates.append(candidate)

    first_snippet = _find_first_json_snippet(cleaned)
    if first_snippet:
        candidates.append(first_snippet)

    seen: set[str] = set()
    unique_candidates: list[str] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique_candidates.append(candidate)

    last_error: json.JSONDecodeError | None = None
    for candidate in unique_candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            last_error = e

    if last_error is not None:
        raise last_error

    raise json.JSONDecodeError("No JSON content found", cleaned, 0)

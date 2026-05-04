#!/usr/bin/env python3
"""
Stop hook: enforce a writing-style floor on every assistant turn.

Scans the final assistant message for high-confidence style violations:
  - em dashes (configurable via enforce_em_dash)
  - banned regexes loaded from ~/.claude/hooks/style_check_config.json

Falls back to built-in defaults if no config is present. Fails open on any
parse error so a broken hook never bricks a session.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


CONFIG_PATH = Path.home() / ".claude" / "hooks" / "style_check_config.json"
BLOCK_LOG_PATH = Path.home() / ".claude" / "hooks" / "style_check_blocks.log"

DEFAULT_CONFIG: dict = {
    "enforce_em_dash": True,
    "banned_regexes": [
        {"pattern": r"\bdelve\b", "flags": "i", "label": "'delve' (AI tell)"},
        {"pattern": r"\butilize\b", "flags": "i", "label": "'utilize' (use 'use')"},
        {"pattern": r"\bCertainly!", "flags": "", "label": "'Certainly!' (AI tell)"},
        {"pattern": r"\bAbsolutely!", "flags": "", "label": "'Absolutely!' (AI tell)"},
        {"pattern": r"I'd be happy to", "flags": "i", "label": "'I'd be happy to' (AI tell)"},
        {"pattern": r"In today's fast[- ]paced", "flags": "i", "label": "'In today's fast-paced ...' (AI tell)"},
    ],
    "style_guide_hint": "~/.claude/projects/<sanitized-cwd>/memory/user_writing_style.md",
}


def load_config() -> dict:
    """Load config from disk, fall back to defaults on any error."""
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CONFIG
    if not isinstance(data, dict):
        return DEFAULT_CONFIG
    return data


def compile_banned(entries) -> list[tuple[re.Pattern[str], str]]:
    """Compile banned_regexes entries; skip any that don't parse."""
    compiled: list[tuple[re.Pattern[str], str]] = []
    if not isinstance(entries, list):
        return compiled
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        pattern = entry.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            continue
        flags_str = entry.get("flags", "") or ""
        flags = 0
        if "i" in flags_str:
            flags |= re.IGNORECASE
        if "m" in flags_str:
            flags |= re.MULTILINE
        label = entry.get("label") or pattern
        try:
            compiled.append((re.compile(pattern, flags), label))
        except re.error:
            continue
    return compiled


def load_last_assistant_text(transcript_path: str) -> str:
    """Read the transcript JSONL and return the text of the final assistant turn."""
    path = Path(transcript_path)
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""

    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "assistant":
            continue

        msg = entry.get("message") or {}
        content = msg.get("content")

        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return "\n".join(parts)
        elif isinstance(content, str) and content:
            return content
    return ""


def log_block(violations: list[str]) -> None:
    """Append one JSON line per block event. Fail silently on any I/O error."""
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "violations": violations,
        }
        with BLOCK_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def collect_violations(text: str, config: dict) -> list[str]:
    """Return human-readable notes for each style violation found."""
    notes: list[str] = []

    if config.get("enforce_em_dash", True):
        em_count = text.count("\u2014")
        if em_count:
            idx = text.find("\u2014")
            snippet = text[max(0, idx - 40) : idx + 41].replace("\n", " ").strip()
            suffix = f" (and {em_count - 1} more)" if em_count > 1 else ""
            notes.append(f'em dash: "...{snippet}..."{suffix}')

    for pattern, label in compile_banned(config.get("banned_regexes", [])):
        match = pattern.search(text)
        if match:
            notes.append(f"{label}: matched '{match.group(0)}'")

    return notes


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        sys.exit(0)

    if payload.get("stop_hook_active"):
        sys.exit(0)

    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        sys.exit(0)

    text = load_last_assistant_text(transcript_path)
    if not text:
        sys.exit(0)

    config = load_config()
    violations = collect_violations(text, config)
    if not violations:
        sys.exit(0)

    style_guide = config.get("style_guide_hint") or DEFAULT_CONFIG["style_guide_hint"]
    reason_lines = [
        "Writing-style violations in your final response. Revise before ending the turn:",
        *(f"  - {v}" for v in violations),
        "",
        f"Apply your style guide ({style_guide}):",
        "  - Replace em dashes with commas, periods, colons, or parentheses.",
        "  - Remove AI tells and rewrite in a direct, committed voice.",
        "  - Verbatim quotes from the user or a participant are the only em-dash exception.",
    ]

    log_block(violations)

    response = {
        "decision": "block",
        "reason": "\n".join(reason_lines),
    }
    print(json.dumps(response))
    sys.exit(0)


if __name__ == "__main__":
    main()

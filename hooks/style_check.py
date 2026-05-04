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
    "context_patterns": [
        {"context": "slack", "pattern": r"\b(slack|channel|dm)\b|post in #|message in #|#[a-z0-9_-]+", "flags": "i"},
        {"context": "email", "pattern": r"\b(email|inbox|reply to|sign[- ]off|cc:|bcc:)\b|subject:", "flags": "i"},
        {"context": "long_form", "pattern": r"\b(memo|doc|document|page|report|long[- ]form|whitepaper|essay|spec|proposal|brief|readout|deck|article|blog post|wiki|prd)\b", "flags": "i"},
    ],
}

CONTEXT_HINTS: dict[str, str] = {
    "slack": "Detected Slack context. Apply the Slack layer of your style guide (casual, lowercase starts, short).",
    "email": "Detected email context. Apply the email layer (warm openings, sign-off if specified).",
    "long_form": "Detected long-form context. Apply the long-form layer (structured, scannable headers, citations where evidence is cited).",
    "base": "No specific channel detected. Apply the base tone.",
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
        text = extract_text(entry)
        if text:
            return text
    return ""


def log_block(violations: list[str], context: str) -> None:
    """Append one JSON line per block event. Fail silently on any I/O error."""
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "violations": violations,
        }
        with BLOCK_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def compile_context_patterns(config: dict) -> list[tuple[str, re.Pattern[str]]]:
    """Compile context_patterns entries; skip any that don't parse."""
    entries = config.get("context_patterns")
    if not isinstance(entries, list):
        entries = DEFAULT_CONFIG["context_patterns"]
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        context = entry.get("context")
        pattern = entry.get("pattern")
        if not isinstance(context, str) or not isinstance(pattern, str) or not pattern:
            continue
        flags_str = entry.get("flags", "") or ""
        flags = 0
        if "i" in flags_str:
            flags |= re.IGNORECASE
        if "m" in flags_str:
            flags |= re.MULTILINE
        try:
            compiled.append((context, re.compile(pattern, flags)))
        except re.error:
            continue
    return compiled


def extract_text(entry: dict) -> str:
    """Pull text from a transcript entry (assistant or user)."""
    msg = entry.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    if isinstance(content, str):
        return content
    return ""


def detect_context(transcript_path: str, config: dict) -> str:
    """Walk user messages newest-first; return the first context label that matches."""
    path = Path(transcript_path)
    if not path.exists():
        return "base"
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return "base"

    patterns = compile_context_patterns(config)
    if not patterns:
        return "base"

    for raw in reversed(lines):
        if not raw.strip():
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if entry.get("type") != "user":
            continue
        text = extract_text(entry)
        if not text:
            continue
        for label, pattern in patterns:
            if pattern.search(text):
                return label
    return "base"


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
    context = detect_context(transcript_path, config)
    context_hint = CONTEXT_HINTS.get(context, CONTEXT_HINTS["base"])
    reason_lines = [
        "Writing-style violations in your final response. Revise before ending the turn:",
        *(f"  - {v}" for v in violations),
        "",
        context_hint,
        f"Apply your style guide ({style_guide}):",
        "  - Replace em dashes with commas, periods, colons, or parentheses.",
        "  - Remove AI tells and rewrite in a direct, committed voice.",
        "  - Verbatim quotes from the user or a participant are the only em-dash exception.",
    ]

    log_block(violations, context)

    response = {
        "decision": "block",
        "reason": "\n".join(reason_lines),
    }
    print(json.dumps(response))
    sys.exit(0)


if __name__ == "__main__":
    main()

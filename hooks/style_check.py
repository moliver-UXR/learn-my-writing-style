#!/usr/bin/env python3
"""
Stop hook: enforce a writing-style floor on every assistant turn.

Scans the final assistant message for high-confidence style violations:
  - em dashes (configurable via enforce_em_dash)
  - en dashes (configurable via enforce_en_dash)
  - banned regexes loaded from ~/.claude/hooks/style_check_config.json
    (includes the "It's not X. It's Y." negate-pivot construction)

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

# Capitalization checks run on prose with code and blockquote markers removed,
# so loop variables (for i in ...), file paths, and quoted snippets don't trip
# them. Bare "i" only matches as a standalone token; sentence starts skip a
# configurable abbreviation set so "e.g. foo" / "i.e. bar" stay clean.
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
_BLOCKQUOTE_RE = re.compile(r"(?m)^[ \t]*>+[ \t]?")
_LOWER_I_RE = re.compile(r"(?<![\w'/])i(['’](m|ll|ve|d|re))?(?![\w'.])")
_SENT_START_RE = re.compile(r"[.!?][\"')\]]?\s+[a-z]")
_PREV_TOKEN_RE = re.compile(r"([A-Za-z][A-Za-z.]*)$")
_DEFAULT_ABBREV = ["e.g", "i.e", "etc", "vs", "cf", "al", "fig", "eq",
                   "approx", "no", "dr", "mr", "ms", "mrs", "st"]
# A bare "i" wrapped on both sides by one of these is a single-letter mention
# or list marker ("i", (i), [i]), not the pronoun, so it is not flagged.
_I_MENTION_WRAP = set("\"'(){}[]") | {"‘", "’", "“", "”"}

DEFAULT_CONFIG: dict = {
    "enforce_em_dash": True,
    "enforce_en_dash": True,
    "enforce_capitalization": True,
    "abbreviations": _DEFAULT_ABBREV,
    "banned_regexes": [
        {"pattern": r"\bdelve\b", "flags": "i", "label": "'delve' (AI tell)"},
        {"pattern": r"\butilize\b", "flags": "i", "label": "'utilize' (use 'use')"},
        {"pattern": r"\bCertainly!", "flags": "", "label": "'Certainly!' (AI tell)"},
        {"pattern": r"\bAbsolutely!", "flags": "", "label": "'Absolutely!' (AI tell)"},
        {"pattern": r"I'd be happy to", "flags": "i", "label": "'I'd be happy to' (AI tell)"},
        {"pattern": r"In today's fast[- ]paced", "flags": "i", "label": "'In today's fast-paced ...' (AI tell)"},
        # Negate-pivot AI tell ("It's not X. It's Y."). Anchored on an it/that/this
        # subject + a copula ("'s"/" is"), a short same-line gap ([^.!?\n]{0,80} so it
        # can't span sentences or paragraphs), a joiner ([.!?,;] handles period, comma,
        # and semicolon forms), then a re-asserting "it's"/"it is". Two known boundaries,
        # by design:
        #   1. Does NOT catch plural/subjectless pivots ("teams are not X. They are Y.") --
        #      regexing those flags ordinary contrastive prose, so they stay a judgment rule.
        #   2. DOES fire on plain adjacent negation ("It is not ready. It's a known issue.").
        #      Accepted false-positive cost of catching the shape; reword to clear.
        # style_check_config.json carries the same two patterns -- keep them in sync.
        {"pattern": r"\b(it|that)('s| is) not\b[^.!?\n]{0,80}[.!?,;]\s+it('s| is)\b", "flags": "i", "label": "'It's not X. It's Y.' construction (AI tell)"},
        {"pattern": r"\bthis (is ?n['’]?t|is not)\b[^.!?\n]{0,80}[.!?,;]\s+it('s| is)\b", "flags": "i", "label": "'This isn't X. It's Y.' construction (AI tell)"},
    ],
    "style_guide_hint": "~/.claude/projects/<sanitized-cwd>/memory/user_writing_style.md",
    "context_patterns": [
        {"context": "slack", "pattern": r"\b(slack|channel|dm)\b|post in #|message in #|#[a-z0-9_-]+", "flags": "i"},
        {"context": "email", "pattern": r"\b(email|inbox|reply to|sign[- ]off|cc:|bcc:)\b|subject:", "flags": "i"},
        {"context": "long_form", "pattern": r"\b(memo|doc|document|page|report|long[- ]form|whitepaper|essay|spec|proposal|brief|readout|deck|article|blog post|wiki|prd)\b", "flags": "i"},
    ],
}

CONTEXT_HINTS: dict[str, str] = {
    "slack": "Detected Slack context. Apply the Slack layer of your style guide (casual, short, warm). Capitalize normally: sentence starts and the pronoun 'I' are always capitalized; only casual greetings/acks/interjections may start lowercase.",
    "email": "Detected email context. Apply the email layer (warm openings, sign-off if specified).",
    "long_form": "Detected long-form context. Apply the long-form layer (structured, scannable headers, citations where evidence is cited).",
    "github": "Detected GitHub context. Apply the GitHub layer: dual-audience (human newcomer + LLM intermediary), front-load what the project does and why, structured parseable sections, Michael's voice throughout.",
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


def normalize_prose(text: str) -> str:
    """Strip code/blockquote markers so capitalization checks see prose only.

    Inline code becomes the placeholder 'Xx' (a capitalized, non-abbreviation
    token) so a sentence that opens with `an_identifier` is not misread as a
    lowercase start, while a real lowercase word after it still gets caught.
    """
    text = _FENCE_RE.sub("\n", text)
    text = _INLINE_CODE_RE.sub(" Xx ", text)
    text = _BLOCKQUOTE_RE.sub("", text)
    return text


def _cap_snippet(text: str, idx: int, before: int = 18, after: int = 26) -> str:
    return " ".join(text[max(0, idx - before): idx + after].split())


def collect_capitalization(text: str, abbreviations) -> list[str]:
    """Flag lowercase sentence starts and the lowercase pronoun 'i'.

    Runs on code-stripped prose, so loop variables (for i in ...), file paths,
    and inline code are safe. Bare 'i' matches only as a standalone token; a
    sentence start is skipped when the preceding token is a known abbreviation
    (e.g., i.e., etc.) or a single letter. Catches the all-lowercase-casual
    failure mode without flagging legitimate technical prose.
    """
    notes: list[str] = []
    prose = normalize_prose(text)
    abbrev = {a.lower() for a in abbreviations} if abbreviations else set(_DEFAULT_ABBREV)

    # First word of each paragraph (blank-line separated), so a lowercase draft
    # is caught even when capitalized framing or a blockquote precedes it. List,
    # table, heading, and number leads are skipped (fragments, not sentences).
    flagged_first = False
    for para in re.split(r"\n\s*\n", prose):
        for line in para.splitlines():
            s = line.strip()
            if not s:
                continue
            if s[0].isalpha() and s[0].islower():
                notes.append(f'lowercase first word: "{_cap_snippet(s, 0, 0, 30)}"')
                flagged_first = True
            break
        if flagged_first:
            break

    # Lowercase pronoun "i" (and i'm / i'll / i've / i'd / i're). A bare "i"
    # wrapped by quotes or brackets is a mention or list marker, not a pronoun.
    for m in _LOWER_I_RE.finditer(prose):
        if m.group(1) is None:
            before = prose[m.start() - 1] if m.start() else " "
            after = prose[m.end()] if m.end() < len(prose) else " "
            if before in _I_MENTION_WRAP and after in _I_MENTION_WRAP:
                continue
        notes.append(f'lowercase pronoun "i" (write "I"): "...{_cap_snippet(prose, m.start())}..."')
        break

    # Lowercase letter opening a sentence, minus known abbreviations on either
    # side of the boundary ("ends in etc." before, or "i.e. opens" after).
    for m in _SENT_START_RE.finditer(prose):
        tok = _PREV_TOKEN_RE.search(prose[:m.start() + 1])
        if tok:
            t = tok.group(1).rstrip(".").lower()
            if t in abbrev or len(t) == 1:
                continue
        nxt = re.match(r"[A-Za-z.]+", prose[m.end() - 1:])
        if nxt and nxt.group(0).rstrip(".").lower() in abbrev:
            continue
        notes.append(f'lowercase sentence start: "...{_cap_snippet(prose, m.start())}..."')
        break

    return notes


def collect_violations(text: str, config: dict) -> list[str]:
    """Return human-readable notes for each style violation found."""
    notes: list[str] = []

    # Dash checks flag EVERY occurrence, including dashes inside verbatim quotes.
    # The hook can't tell a quote from prose, so the "verbatim quote" exception is
    # applied by human/Claude judgment (reword or keep), not enforced here.
    # snippet shows the first occurrence (+/-40 chars) for context; count reports the rest.
    if config.get("enforce_em_dash", True):
        em_count = text.count("\u2014")  # U+2014 em dash
        if em_count:
            idx = text.find("\u2014")
            snippet = text[max(0, idx - 40) : idx + 41].replace("\n", " ").strip()
            suffix = f" (and {em_count - 1} more)" if em_count > 1 else ""
            notes.append(f'em dash: "...{snippet}..."{suffix}')

    if config.get("enforce_en_dash", True):
        en_count = text.count("\u2013")  # U+2013 en dash (distinct from hyphen-minus U+002D)
        if en_count:
            idx = text.find("\u2013")
            snippet = text[max(0, idx - 40) : idx + 41].replace("\n", " ").strip()
            suffix = f" (and {en_count - 1} more)" if en_count > 1 else ""
            notes.append(f'en dash: "...{snippet}..."{suffix}')

    for pattern, label in compile_banned(config.get("banned_regexes", [])):
        match = pattern.search(text)
        if match:
            notes.append(f"{label}: matched '{match.group(0)}'")

    if config.get("enforce_capitalization", True):
        notes.extend(collect_capitalization(text, config.get("abbreviations")))

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
        "  - Replace em and en dashes with commas, periods, colons, or parentheses.",
        "  - Remove AI tells and rewrite in a direct, committed voice.",
        "  - Recast 'It's not X, it's Y' as a single positive claim.",
        "  - Capitalize sentence starts and the pronoun 'I' (Slack included); only casual greetings/acks may start lowercase.",
        "  - Verbatim quotes from the user or a participant are the only dash exception.",
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

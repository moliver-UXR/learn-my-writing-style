#!/usr/bin/env bash
# learn-my-writing-style installer
#
# Copies skills + hook into ~/.claude, wires the Stop hook in settings.json,
# smoke-tests the hook, and prints next steps. Idempotent: safe to rerun
# after `git pull` to update.
#
# Usage:
#   ./install.sh
#
# Requirements: Claude Code installed (~/.claude/ exists), python3 in PATH,
# jq optional (falls back to python for JSON merge).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
SKILLS_DIR="$CLAUDE_DIR/skills"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SETTINGS_PATH="$CLAUDE_DIR/settings.json"
HOOK_CMD="python3 $HOOKS_DIR/style_check.py"

step() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$1"; }
fail() { printf 'error: %s\n' "$1" >&2; exit 1; }

# Preflight

[[ -d "$CLAUDE_DIR" ]] || fail "$CLAUDE_DIR does not exist. Install Claude Code first: https://claude.com/claude-code"
command -v python3 >/dev/null 2>&1 || fail "python3 not found in PATH. The hook needs Python 3."

step "preflight ok"

# Install skills

mkdir -p "$SKILLS_DIR" "$HOOKS_DIR"

for skill_path in "$REPO_ROOT/skills"/*/; do
  skill_name="$(basename "$skill_path")"
  dst="$SKILLS_DIR/$skill_name"
  rm -rf "$dst"
  cp -R "$skill_path" "$dst"
  step "installed skill: $skill_name"
done

# Install hook

cp "$REPO_ROOT/hooks/style_check.py" "$HOOKS_DIR/style_check.py"
chmod +x "$HOOKS_DIR/style_check.py"
step "installed hook: $HOOKS_DIR/style_check.py"

# Wire Stop hook in settings.json

[[ -f "$SETTINGS_PATH" ]] || echo '{}' > "$SETTINGS_PATH"

if command -v jq >/dev/null 2>&1; then
  existing="$(jq --arg cmd "$HOOK_CMD" \
    '.hooks.Stop // [] | map(.hooks // []) | flatten | map(.command) | index($cmd)' \
    "$SETTINGS_PATH")"
  if [[ "$existing" == "null" ]]; then
    tmp="$(mktemp)"
    jq --arg cmd "$HOOK_CMD" \
      '.hooks //= {} | .hooks.Stop //= [] | .hooks.Stop += [{"hooks": [{"type": "command", "command": $cmd}]}]' \
      "$SETTINGS_PATH" > "$tmp"
    mv "$tmp" "$SETTINGS_PATH"
    step "wired Stop hook in $SETTINGS_PATH"
  else
    step "Stop hook already wired"
  fi
else
  python3 - "$SETTINGS_PATH" "$HOOK_CMD" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
cmd = sys.argv[2]
data = json.loads(path.read_text() or "{}")
hooks = data.setdefault("hooks", {})
stop = hooks.setdefault("Stop", [])
already = any(h.get("command") == cmd for block in stop for h in block.get("hooks", []))
if already:
    print("[install] Stop hook already wired")
else:
    stop.append({"hooks": [{"type": "command", "command": cmd}]})
    path.write_text(json.dumps(data, indent=2) + "\n")
    print("[install] wired Stop hook (via python; install jq for cleaner merges)")
PY
fi

# Smoke test

if echo '{"transcript_path": "/dev/null"}' | python3 "$HOOKS_DIR/style_check.py" >/dev/null 2>&1; then
  step "hook smoke test passed"
else
  printf 'warning: hook smoke test failed; check python3 install\n' >&2
fi

# Done

cat <<EOF

Install complete.

Next: in any Claude Code session, run:

  /learn-my-writing-style

The skill detects available channels, pulls authored samples (with your
consent), derives your voice, and asks one short question (name + title).
Total time: about 30 seconds.

Companion command (already installed):

  /style-correct

Run it any time you want to turn a manual edit into a permanent rule.

EOF

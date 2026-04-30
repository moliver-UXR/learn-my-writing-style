#!/usr/bin/env bash
# Mirror the live skill and hook from ~/.claude into this repo, then commit + push.
# Idempotent: exits 0 with no commit when nothing changed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_SKILL="$HOME/.claude/skills/learn-my-writing-style/SKILL.md"
SRC_HOOK="$HOME/.claude/hooks/style_check.py"
DST_SKILL="$REPO_ROOT/skills/learn-my-writing-style/SKILL.md"
DST_HOOK="$REPO_ROOT/hooks/style_check.py"

[[ -f "$SRC_SKILL" ]] || { echo "missing source: $SRC_SKILL" >&2; exit 1; }
[[ -f "$SRC_HOOK" ]] || { echo "missing source: $SRC_HOOK" >&2; exit 1; }

mkdir -p "$(dirname "$DST_SKILL")" "$(dirname "$DST_HOOK")"
cp "$SRC_SKILL" "$DST_SKILL"
cp "$SRC_HOOK" "$DST_HOOK"
chmod +x "$DST_HOOK"

cd "$REPO_ROOT"
if git diff --quiet HEAD -- "$DST_SKILL" "$DST_HOOK" 2>/dev/null; then
  echo "no changes; nothing to commit"
  exit 0
fi

git add "$DST_SKILL" "$DST_HOOK"
git commit -m "Sync skill and hook from ~/.claude

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin main
echo "synced and pushed"

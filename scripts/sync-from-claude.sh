#!/usr/bin/env bash
# Mirror the live skills and hook from ~/.claude into this repo, then commit + push.
# Idempotent: exits 0 with no commit when nothing changed.
# To track an additional skill, add its name to the SKILLS array.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS=(learn-my-writing-style style-correct)
SRC_HOOK="$HOME/.claude/hooks/style_check.py"
DST_HOOK="$REPO_ROOT/hooks/style_check.py"

[[ -f "$SRC_HOOK" ]] || { echo "missing source: $SRC_HOOK" >&2; exit 1; }

declare -a TRACKED=("$DST_HOOK")
mkdir -p "$(dirname "$DST_HOOK")"
cp "$SRC_HOOK" "$DST_HOOK"
chmod +x "$DST_HOOK"

for skill in "${SKILLS[@]}"; do
  src="$HOME/.claude/skills/$skill/SKILL.md"
  dst="$REPO_ROOT/skills/$skill/SKILL.md"
  [[ -f "$src" ]] || { echo "missing source: $src" >&2; exit 1; }
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  TRACKED+=("$dst")
done

cd "$REPO_ROOT"
if git diff --quiet HEAD -- "${TRACKED[@]}" 2>/dev/null; then
  echo "no changes; nothing to commit"
  exit 0
fi

git add "${TRACKED[@]}"
git commit -m "Sync skills and hook from ~/.claude

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin main
echo "synced and pushed"

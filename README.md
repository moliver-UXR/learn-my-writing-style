# learn-my-writing-style

Claude Code skills that capture your writing voice, enforce it with a Stop hook, and let you teach Claude new corrections one paste at a time.

The repo ships two slash commands and one hook:

- **`/learn-my-writing-style`**: interview-driven onboarding. Builds your voice profile and wires the hook.
- **`/style-correct`**: paste your edited version of a recent Claude response. The skill diffs it, proposes a banned-phrase rule, and (with confirmation) appends it to the hook's config.
- **`style_check.py`**: the Stop hook. Scans every assistant turn, blocks on em dashes and banned regexes, routes the rewrite hint by detected channel context (Slack, email, long-form, base), and logs every block.

## Why

Out of the box, Claude leans on em dashes, "Certainly!", "Let me explain...", and other tells that flatten its prose. Memory files alone are advisory. This repo pairs a voice profile with a deterministic check that runs on every assistant turn, plus a self-improving loop that turns each manual correction into a new rule.

## What you get

After running `/learn-my-writing-style` once:

| Path | Purpose |
| --- | --- |
| `~/.claude/projects/<sanitized-cwd>/memory/user_profile.md` | Role, day-to-day, guiding principles |
| `~/.claude/projects/<sanitized-cwd>/memory/user_writing_style.md` | Voice guide: anti-patterns, tone adjectives, exemplars, Slack/email/long-form layers |
| `~/.claude/projects/<sanitized-cwd>/memory/user_org.md` | Organization context (only if you named one) |
| `~/.claude/projects/<sanitized-cwd>/memory/MEMORY.md` | Index linking the files above |
| `~/.claude/hooks/style_check.py` | The Stop hook script |
| `~/.claude/hooks/style_check_config.json` | Banned patterns the hook enforces |
| `~/.claude/settings.json` | Stop hook entry pointing to `style_check.py` (merged, not overwritten) |

`<sanitized-cwd>` is your current working directory with `/` replaced by `-`. So `/Users/jane/work` becomes `-Users-jane-work`. That scopes the memory to the project you ran the skill in.

## Install

```bash
git clone https://github.com/moliver-UXR/learn-my-writing-style.git
cd learn-my-writing-style

mkdir -p ~/.claude/skills ~/.claude/hooks
cp -R skills/* ~/.claude/skills/
cp hooks/style_check.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/style_check.py
```

Then in any Claude Code session, run:

```
/learn-my-writing-style
```

It asks twelve quick questions, summarizes what it captured, and writes everything once you say `yes`. After that, `/style-correct` is available whenever you want to teach Claude a new correction.

## What the interview asks

**Profile (5):** name and title, organization, work + personal email, one-sentence day-to-day, two or three guiding principles.

**Voice base layer (4):** 3-4 tone adjectives, 2-3 writers/publications you want to sound like, AI tells to ban (defaults plus your additions), filler words to cut.

**Context layers (3, optional):** Slack voice, email voice, long-form doc voice.

Skipped questions become placeholder comments in the file (`<!-- Fill this in after a week of real usage. -->`), not empty sections.

## How the hook works

`style_check.py` is a Stop hook. Claude Code invokes it after every assistant turn with the transcript path on stdin. The script:

1. Reads the transcript JSONL and extracts the text of the final assistant message.
2. Loads `~/.claude/hooks/style_check_config.json`, falling back to built-in defaults if the file is missing or malformed.
3. Scans the text for em dashes (Unicode `U+2014`) and each entry in `banned_regexes`.
4. Walks user messages newest-first and classifies the conversation context as `slack`, `email`, `long_form`, or `base` using `context_patterns`.
5. **On match:** emits `{"decision": "block", "reason": "..."}` listing every violation, the detected context, and which layer of `user_writing_style.md` to apply on the rewrite. Claude sees the reason and revises before ending the turn.
6. **On no match:** exits 0 silently.

It fails open on any error, so a broken config never bricks a session.

## Context routing

Every block tells the model which voice layer to apply. Detection runs against the most recent user message that matches a context pattern; if none match, the hook returns `base` and asks the model to apply the base tone.

| Context | Triggers (default patterns) | Layer the model is told to apply |
| --- | --- | --- |
| `slack` | `slack`, `channel`, `dm`, `post in #...`, `#channel-name` | Slack layer (casual, lowercase starts, short) |
| `email` | `email`, `inbox`, `reply to`, `subject:`, `cc:`, `sign-off` | Email layer (warm openings, sign-off if specified) |
| `long_form` | `memo`, `doc`, `report`, `spec`, `proposal`, `brief`, `readout`, `deck`, `prd`, `wiki`, etc. | Long-form layer (structured, scannable, citations) |
| `base` | nothing matched | Base tone |

Override the patterns via `context_patterns` in the config (same `{context, pattern, flags}` shape as `banned_regexes`).

## Config schema

`~/.claude/hooks/style_check_config.json`:

```json
{
  "enforce_em_dash": true,
  "banned_regexes": [
    {"pattern": "\\bdelve\\b", "flags": "i", "label": "'delve' (AI tell)"}
  ],
  "style_guide_hint": "~/.claude/projects/<sanitized-cwd>/memory/user_writing_style.md"
}
```

| Field | Type | Purpose |
| --- | --- | --- |
| `enforce_em_dash` | bool | Toggles the hard-coded `U+2014` check |
| `banned_regexes` | array | Each entry: `{pattern, flags, label}`. `flags` accepts `i` (case-insensitive) and `m` (multiline). `label` is what appears in the violation message. |
| `context_patterns` | array | Each entry: `{context, pattern, flags}`. `context` is one of `slack`, `email`, `long_form`. Optional; built-in defaults cover the common triggers. |
| `style_guide_hint` | string | Path the block reason points the model at, so it knows where to look up tone notes |

Add or remove entries any time without touching Python.

### Default banned patterns

| Label | Pattern |
| --- | --- |
| `'delve' (AI tell)` | `\bdelve\b` |
| `'utilize' (use 'use')` | `\butilize\b` |
| `'Certainly!' (AI tell)` | `\bCertainly!` |
| `'Absolutely!' (AI tell)` | `\bAbsolutely!` |
| `'I'd be happy to' (AI tell)` | `I'd be happy to` |
| `'In today's fast-paced ...' (AI tell)` | `In today's fast[- ]paced` |

## Block log

Every time the hook blocks a turn, it appends one JSON line to `~/.claude/hooks/style_check_blocks.log`:

```json
{"ts": "2026-05-04T18:42:11+00:00", "context": "email", "violations": ["em dash: \"...prose \u2014 flattened...\""]}
```

(`\u2014` is the JSON escape for the em dash character; `json.dumps` always escapes non-ASCII by default.)

Use it to see which rules earn their keep:

```bash
# Top violation labels in the last 200 blocks
tail -n 200 ~/.claude/hooks/style_check_blocks.log \
  | jq -r '.violations[]' \
  | sed 's/:.*//' \
  | sort | uniq -c | sort -rn
```

The log is append-only and never rotated. Delete it whenever you want a clean slate.

## Updating

```bash
cd path/to/learn-my-writing-style
git pull
cp -R skills/learn-my-writing-style ~/.claude/skills/
cp hooks/style_check.py ~/.claude/hooks/
```

Your config and memory files are left alone.

## Re-running the interview

Invoke `/learn-my-writing-style` again. By default it skips files that already exist, so deleting one memory file lets you refresh just that file. Pick **Replace** for a full rebuild.

## Teaching new rules: `/style-correct`

When you rewrite a Claude response in your head or in a doc, run `/style-correct` to turn that one correction into a permanent rule. The skill:

1. Asks you to paste your edited version (or describe the change in words: "swap 'utilize' for 'use'").
2. Diffs the paste against the most recent assistant message in the conversation.
3. Identifies removed or replaced phrases and proposes a banned regex for each (with the replacement noted in the label).
4. Shows the candidate rules and asks for confirmation. You can accept all, pick a subset, or decline.
5. Appends the approved entries to `~/.claude/hooks/style_check_config.json`.

The skill only encodes phrase-level rules. Tone or structural changes get flagged for you to add to `user_writing_style.md` directly.

## Uninstall

```bash
rm -rf ~/.claude/skills/learn-my-writing-style ~/.claude/skills/style-correct
rm ~/.claude/hooks/style_check.py
rm ~/.claude/hooks/style_check_config.json
rm -f ~/.claude/hooks/style_check_blocks.log
```

Open `~/.claude/settings.json` and remove the `Stop` entry that runs `style_check.py`. Memory files under `~/.claude/projects/.../memory/` are preserved until you delete them yourself.

## Troubleshooting

**Hook does not fire after install.** Open `/hooks` once in Claude Code or restart the session. The settings watcher does not always pick up newly-added hook blocks mid-session.

**Hook fires but never blocks.** Test it manually:

```bash
echo '{"transcript_path": "/path/to/recent/transcript.jsonl"}' | python3 ~/.claude/hooks/style_check.py
```

A non-empty JSON response means the rules match. An empty response means the message was clean (or the path was wrong).

**Disable temporarily.** Set `enforce_em_dash: false` and `banned_regexes: []` in the config, or remove the Stop entry from `settings.json`.

**Edit rules without rerunning the skill.** `style_check_config.json` is plain JSON. Add or remove entries directly.

## Repository layout

```
learn-my-writing-style/
├── README.md                                  this file
├── hooks/style_check.py                       Stop hook (copied to ~/.claude/hooks/)
├── scripts/sync-from-claude.sh                maintainer-only: mirror live ~/.claude into the repo
└── skills/
    ├── learn-my-writing-style/SKILL.md        onboarding skill, /learn-my-writing-style
    └── style-correct/SKILL.md                 correction-capture skill, /style-correct
```

`scripts/sync-from-claude.sh` is for the repo maintainer. End users do not run it.

The `SKILL.md` files are the canonical instruction sets Claude follows when you invoke each slash command. Read them if you want to know exactly what the skills do, or to fork the interview / correction flow.

## Requirements

- Claude Code with Stop hook support
- Python 3 in `$PATH`
- Unix-like environment (macOS, Linux). Windows requires WSL or path adjustments.

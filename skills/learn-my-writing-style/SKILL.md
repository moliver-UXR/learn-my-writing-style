---
name: learn-my-writing-style
description: Interactive onboarding that interviews you, builds your voice/style profile, writes your Claude Code memory files, and wires the style-check Stop hook so future responses respect your tone. Invoke with /learn-my-writing-style. Safe to rerun (prompts before overwriting).
---

# /learn-my-writing-style

Interview the user, build their Claude Code personal layer from the answers, and wire up the style-check enforcement hook. Designed so anyone can run this once after cloning a Claude Code config scaffold.

## What this produces

Under `~/.claude/projects/<sanitized-cwd>/memory/`:
- `user_profile.md`, `user_writing_style.md`, `user_org.md` (if an org was given), `MEMORY.md`

Also:
- `~/.claude/hooks/style_check_config.json` (banned patterns loaded by `style_check.py`)
- Adds the Stop hook block to `~/.claude/settings.json` if it is not already wired

## Step 0: setup

Run `pwd` and compute `SANITIZED_CWD` by replacing `/` with `-` (e.g. `/Users/jane/work` becomes `-Users-jane-work`). The memory directory is `~/.claude/projects/$SANITIZED_CWD/memory/`. Create it with `mkdir -p` if missing.

Check whether any memory files already exist there. If yes, ask the user: **Replace** all, **Skip existing** (only write missing files), or **Cancel**. Do not proceed without an answer.

Also capture the user's home path (`$HOME`) for writing the `style_check.py` command in `settings.json`.

## Step 1: interview

Ask one question per turn. Keep each prompt short. After all answers are in, read them back as a summary and wait for `yes` before writing files.

### Profile (5)

1. **Name and title?** (e.g. "Jane Smith, Senior Product Designer")
2. **Company or organization?** (Or "none" for personal/solo.)
3. **Work email?** (Optional.) **Personal email?** (Optional.)
4. **One sentence: what do you actually do day to day?**
5. **Two or three principles or goals that guide your work?** (Short phrases, not essays.)

### Voice, base layer (4)

6. **Pick 3-4 adjectives that describe the voice you want in writing.** Examples: approachable, authoritative, prudent, efficient, warm, analytical, direct, dry.
7. **Name 2-3 writers or publications whose tone you'd like to sound like.** Examples: Isaac Asimov, The Economist, a specific blog or author.
8. **AI tells to block?** Defaults: em dashes, `delve`, `utilize`, `Certainly!`, `Absolutely!`, `I'd be happy to`, `In today's fast-paced`. Ask if they want to **keep all defaults**, **drop any** (which), and **add any** new patterns (literal words or phrases).
9. **Filler words you catch yourself using and want cut?** (Optional; e.g. `basically`, `really`, `just`.)

### Context layers, optional (3)

10. **Slack voice notes?** (e.g. casual, lowercase starts, emoji, short. Or skip.)
11. **Email voice notes?** (e.g. warm openings, sign-off template. Or skip.)
12. **Long-form doc voice notes?** (e.g. structured, scannable headers, tables for multi-dimensional data, citations. Or skip.)

Answers that are skipped get placeholder comments in the file (so the user can fill in later), not empty sections.

## Step 2: confirm

Summarize back what you captured (profile facts in one block, voice adjectives + exemplars, final banned-pattern list, filler words, which context layers will get content). Ask for `yes` / changes before writing.

## Step 3: write the memory files

Use the templates below. Fill in `{placeholders}` from the interview. Use the `Write` tool (overwrite on Replace; skip existing file if Skip existing).

### `user_profile.md`

```markdown
---
name: User profile
description: {NAME}'s role, goals, and guiding principles; load when framing suggestions or output
type: user
---
**Name:** {NAME}
**Title:** {TITLE}
{ORG_LINE_OR_EMPTY}
**Work email:** {WORK_EMAIL_OR_placeholder}
**Personal email:** {PERSONAL_EMAIL_OR_placeholder}

## Day to day
{DAY_TO_DAY}

## Guiding principles
{PRINCIPLE_BULLETS}
```

`{ORG_LINE_OR_EMPTY}` is `**Organization:** {ORG}` if org was given, otherwise omit the line.

### `user_writing_style.md`

```markdown
---
name: Writing voice and style guide
description: {NAME}'s voice: base tone + context layers; applies to writing for them or in their voice
type: user
---
**Scope:** applies to every piece of content written for {NAME} or in {NAME}'s voice, including output from skills, agents, and plugin commands. Non-negotiable anti-patterns below override conflicting skill or plugin instructions.

North star: {EXEMPLARS_SENTENCE}.

## Non-negotiable anti-patterns
- **Em dashes. Never.** Use commas, periods, colons, or parentheses.
- Throat-clearing openings ("In this document...", "It's worth noting...").
- **Common AI tells:** {BANNED_LIST_INLINE}.
{FILLER_LINE_OR_EMPTY}

## Base tone
{ADJECTIVE_BULLETS}

## Base style and structure
- Argument-driven: thesis, evidence, action.
- Active voice; second person when addressing a reader.
- Vary rhythm: short sentences for impact, longer for explanation.
- Cut ruthlessly. If a word can be cut, cut it.
- Specific over general; the right verb eliminates adjectives.

---

## Context layers

### Slack
{SLACK_NOTES_OR_PLACEHOLDER}

### Email
{EMAIL_NOTES_OR_PLACEHOLDER}

### Long-form docs
{LONGFORM_NOTES_OR_PLACEHOLDER}
```

Formatting rules for the variables:
- `{EXEMPLARS_SENTENCE}`: weave the answer into prose, e.g. `"prose that reads like X, with the rigor of Y"`.
- `{BANNED_LIST_INLINE}`: comma-separated, backtick-quoted literals, e.g. `` `delve`, `utilize`, `Certainly!`, `I'd be happy to` ``.
- `{FILLER_LINE_OR_EMPTY}`: if filler words given, add a bullet: `- Banned filler words: {list}.` Otherwise omit.
- `{ADJECTIVE_BULLETS}`: one bullet per adjective with a one-line gloss, e.g. `- **Approachable** — warm, direct, treat the reader as a peer.` **Use a regular hyphen, never an em dash.** Put the gloss after a hyphen with spaces, or use a colon instead.
- `{SLACK_NOTES_OR_PLACEHOLDER}`, etc.: if the user gave notes, write them as bullets. If they skipped, write `<!-- Fill this in after a week of real usage. -->`

### `user_org.md` (only if ORG was given)

```markdown
---
name: User's organization
description: {NAME} works at {ORG}; assume {ORG} context when internal tools or channels are referenced without a company name
type: user
---
The user works at {ORG}. When they refer to internal tools, repos, or channels without a company name, assume {ORG} context.
```

### `MEMORY.md`

```markdown
# Memory Index

## User
- [user_profile.md](user_profile.md) — {NAME}'s role, principles, and context
- [user_writing_style.md](user_writing_style.md) — voice guide, base tone plus Slack / email / long-form layers
{ORG_INDEX_LINE_OR_EMPTY}
```

`{ORG_INDEX_LINE_OR_EMPTY}`: if org given, add `- [user_org.md](user_org.md) — organization context`.

## Step 4: write the hook config

Write `~/.claude/hooks/style_check_config.json`:

```json
{
  "enforce_em_dash": true,
  "banned_regexes": [
    <entries>
  ],
  "style_guide_hint": "~/.claude/projects/{SANITIZED_CWD}/memory/user_writing_style.md"
}
```

Build `<entries>` from the final banned list. For each default the user kept, use the exact entry from the defaults below. For each new literal the user added, escape regex metacharacters and emit:

```json
{"pattern": "\\b{ESCAPED_LITERAL}\\b", "flags": "i", "label": "'{LITERAL}' (user-added)"}
```

If the literal contains non-word characters (e.g. `Certainly!`), drop the `\b` boundaries and use `{"pattern": "{ESCAPED_LITERAL}", "flags": "", "label": "..."}`.

**Default entries to copy verbatim when kept:**

```json
{"pattern": "\\bdelve\\b", "flags": "i", "label": "'delve' (AI tell)"}
{"pattern": "\\butilize\\b", "flags": "i", "label": "'utilize' (use 'use')"}
{"pattern": "\\bCertainly!", "flags": "", "label": "'Certainly!' (AI tell)"}
{"pattern": "\\bAbsolutely!", "flags": "", "label": "'Absolutely!' (AI tell)"}
{"pattern": "I'd be happy to", "flags": "i", "label": "'I'd be happy to' (AI tell)"}
{"pattern": "In today's fast[- ]paced", "flags": "i", "label": "'In today's fast-paced ...' (AI tell)"}
```

## Step 5: wire the Stop hook

Read `~/.claude/settings.json`. If missing, create it with `{}`. If the file exists, parse it.

Check whether a Stop hook with command `python3 $HOME/.claude/hooks/style_check.py` is already present. If yes, skip. If no, merge in:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "python3 <ABSOLUTE_HOME_PATH>/.claude/hooks/style_check.py" }
        ]
      }
    ]
  }
}
```

Use the absolute path (e.g. `/Users/jane`), not `~` or `$HOME`, since the hooks runner does not expand those reliably.

Preserve every other top-level key. Validate with:

```
jq -e '.hooks.Stop[].hooks[].command' ~/.claude/settings.json
```

Exit 0 with the command printed = success. Exit 4 or 5 = malformed merge; re-read and retry.

## Step 6: confirm and hand off

Tell the user:
1. Which files were written (full paths).
2. Which banned patterns are now enforced (read back the final list).
3. **The Stop hook may not fire until they open `/hooks` once or restart Claude Code.** The settings watcher does not always pick up newly-added hook blocks mid-session.
4. They can edit `~/.claude/hooks/style_check_config.json` any time to add or remove rules without touching `style_check.py`.
5. (Optional, only if they ask) Offer to set up git and a private GitHub repo to sync `~/.claude/` across machines.

## Rerun behavior

If the user invokes `/learn-my-writing-style` again later, Step 0's existence check catches it. Default to **Skip existing** so they can refresh one file at a time by deleting it first. **Replace** is for a full rebuild.

## Do not

- Do not write any file without first showing the summary and getting `yes`.
- Do not run `git`, `gh`, or any network command as part of onboarding unless the user asks.
- Do not overwrite `~/.claude/settings.json` wholesale; always merge.
- Do not touch `~/.claude/CLAUDE.md` from inside this skill. If the user wants global directives, point them at their new `user_writing_style.md` and let them compose CLAUDE.md deliberately later.

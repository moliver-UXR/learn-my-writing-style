---
name: learn-my-writing-style
description: Onboarding that derives your writing voice from real authored prose (Gmail, Slack, Drive, Confluence, GitHub via mounted MCPs) when available, falls back to a short interview when not, writes your Claude Code memory files, and wires the style-check Stop hook so future responses respect your tone. Invoke with /learn-my-writing-style. Safe to rerun (prompts before overwriting).
---

# /learn-my-writing-style

Wizard-style onboarding. Build the user's Claude Code personal layer from real prose they've written (channel-first) or a short interview (fallback), then wire up the style-check enforcement hook. Designed for minimum input: ideal path is one consent, one one-line answer, one final yes.

## Wizard ethos

Frame the user-facing output as a 4-step wizard so the user always knows where they are. Suggested step labels:

1. **Detecting channels.**
2. **Pulling samples and deriving voice** (or interview, if no channels).
3. **One quick question** (name + title + day-to-day).
4. **Review and write.**

Print a one-line "Step N/4: ..." header at each transition. Default to the lowest-friction option at every choice point. Only ask the user to type when there's no reasonable default.

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

## Step 1: build the voice profile

This step has two paths. Always prefer **channel-first**: derive the voice from prose the user has actually written. Fall back to **interview-only** if no MCPs expose authored content or the user declines.

### 1a. Survey channels

Look at the available tools. A channel is "available" if its MCP tools are present in this session. Cover at minimum:

- **Gmail:** sent messages (look for tools like `search_threads`, `get_thread`).
- **Google Drive:** docs the user authored (look for `search_files`, `read_file_content`, `list_recent_files`, `get_file_metadata`).
- **Slack:** messages the user posted (look for `slack_search_*`, `slack_search_users`).
- **Confluence:** pages the user wrote (look for `searchConfluenceUsingCql`, `getConfluencePage`).
- **GitHub:** PR descriptions and substantive commit messages (if a `gh` CLI or GitHub MCP is mounted).

Build a list of channels you can actually pull from. Skip anything missing.

### 1b. Ask consent

Tell the user exactly which channels you can pull from and what you'll fetch. Example:

> I can derive your voice from real samples instead of asking adjective questions. Available now:
> - **Gmail:** your 10 most recent sent emails
> - **Slack:** your 20 most recent messages
> - **Drive:** the 5 most recently edited docs you own
>
> Pull from all? [yes / pick subset / no, do an interview instead]

If the user picks "no" or no channels are available, jump to **1f (interview fallback)** and skip 1c through 1e.

### 1c. Pull samples (only from approved channels)

For each approved channel, fetch authored prose. Default queries:

| Channel | What to fetch |
| --- | --- |
| Gmail | Search `from:me` (resolve the user's address first if needed). Take the 10 most recent threads. Strip signatures, quoted reply text, and disclaimers; keep only what they wrote. |
| Drive | List files where the user is owner, sorted by last-modified desc. Read the 5 most recent. Skip files under ~200 chars (likely not prose). |
| Slack | Look up the user with `slack_search_users`. Search messages where they're the author across channels. Take the 20 most recent substantive messages (skip one-word reactions and link-only posts). |
| Confluence | CQL `creator = currentUser() ORDER BY created DESC`. Read the 3 most recent pages. |
| GitHub | List PRs the user authored (last 10), pull the descriptions; pull the last 10 substantive commit messages. |

If a channel errors or returns nothing, note the failure and continue. **Never block the flow on one source.** Total fetched content should stay under ~20k characters; truncate per-item if needed.

### 1d. Derive voice attributes

From the collected samples, extract:

- **Tone adjectives (3-4):** describe the voice. Be specific: "direct", "dry", "warm", "analytical", "blunt".
- **Exemplar styles (2-3):** writers, publications, or recognizable styles the prose resembles. If nothing fits cleanly, leave blank rather than invent.
- **Channel-specific habits:**
  - Slack: typical opens, message length, lowercase starts, emoji usage, sign-offs.
  - Email: greeting style, sign-off, formality, paragraph length.
  - Long-form: structure (headers, bullets, tables), citation style, scannability.
- **AI tells the user already avoids:** patterns absent from the samples that the hook should keep enforcing (em dashes, `Certainly!`, etc.).
- **Filler words that recur:** repeated low-content words or hedges to ban (e.g., "really", "just", "basically").
- **Verbatim phrases (2-3 short, total under 500 characters):** quote the user's own prose so the analysis is grounded.

### 1e. The one question that has to be asked

Ask once and wait:

> **In one line: your name, title, and (optionally) what you do.** Example: `Jane Smith, Senior Product Designer at Acme; design systems and accessibility`

Parse the answer:

- **Name:** everything before the first comma.
- **Title:** between first comma and ` at ` (or next comma if no `at`).
- **Organization:** after ` at `, up to the next comma or semicolon. If absent, try to derive from the user's email domain (e.g. `jane@acme.com` → "Acme"). If still unknown, treat as "none."
- **Day-to-day:** after the last semicolon or comma. If absent, default to placeholder.

If the parse is ambiguous on a single field (e.g. no clear org), ask one targeted follow-up. Do not re-ask the whole prompt.

**Defaults applied silently** (every one of these is editable later):

- Work email and personal email: placeholders.
- Guiding principles: a placeholder note (`<!-- Add 2-3 phrases as you discover them. -->`).
- AI tells: keep all defaults, plus any new patterns derivation surfaced. Do not ask whether to drop or add. The user edits `~/.claude/hooks/style_check_config.json` directly or runs `/style-correct` later.
- Filler words: only what derivation found. If derivation found nothing, leave empty.
- Exemplar styles: only what derivation found. If nothing, leave blank rather than ask.

This step exists to capture the only thing that's truly unknowable from samples: who the user is and what they call themselves.

### 1f. Interview fallback (only if 1c was skipped)

If no MCPs were available or the user declined sample-pulling, ask three short questions in sequence:

1. **In one line: your name, title, and (optionally) what you do.** (Same parse as 1e.)
2. **Pick 3-4 adjectives for the voice you want in writing.** Examples: direct, warm, dry, analytical, approachable, authoritative.
3. **Anything to ban beyond the default AI tells?** (Defaults: em dashes, `delve`, `utilize`, `Certainly!`, `Absolutely!`, `I'd be happy to`, `In today's fast-paced`. Press Enter to keep all defaults.)

Skip exemplars, filler words, and Slack/email/long-form notes. They become placeholders the user can fill in later (`<!-- Fill this in after a week of real usage. -->`).

## Step 2: review and confirm (wizard step 4/4)

Print **Step 4/4: Review** and show a tight summary of what's about to be written. Tag each item by source so the user can spot mistakes:

- **Profile** (from one-line answer): name, title, org, day-to-day. Mark fields that fell back to placeholders.
- **Voice** (from samples or interview): tone adjectives, exemplars, channel habits, filler words. Tag each as `derived` or `interview` and include 1-2 short verbatim quotes for derived items.
- **Banned patterns:** defaults plus anything new from derivation.

End with a single prompt: `Write everything? [yes / edit X / cancel]`

- `yes` (or empty input): proceed.
- `edit X`: apply the change, redraw the summary, re-prompt.
- `cancel`: stop. Write nothing.

Do not ask multiple yes/no questions. One prompt, one answer.

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
5. **Companion command:** `/style-correct` lets them turn any future manual edit into a permanent banned-phrase rule.
6. (Optional, only if they ask) Offer to set up git and a private GitHub repo to sync `~/.claude/` across machines.

## Rerun behavior

If the user invokes `/learn-my-writing-style` again later, Step 0's existence check catches it. Default to **Skip existing** so they can refresh one file at a time by deleting it first. **Replace** is for a full rebuild.

## Do not

- Do not write any file without first showing the summary and getting `yes`.
- Do not pull from any channel without explicit user consent in 1b.
- Do not store raw fetched content; only the derived attributes and 2-3 short quotes go anywhere persistent.
- Do not run `git`, `gh`, or any network command as part of onboarding unless the user asks.
- Do not overwrite `~/.claude/settings.json` wholesale; always merge.
- Do not touch `~/.claude/CLAUDE.md` from inside this skill. If the user wants global directives, point them at their new `user_writing_style.md` and let them compose CLAUDE.md deliberately later.

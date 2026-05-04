---
name: style-correct
description: Capture a manual edit the user made to a recent assistant response, infer a banned-phrase rule from the diff, and (with confirmation) append it to ~/.claude/hooks/style_check_config.json so style_check.py enforces the same correction next time. Invoke with /style-correct after any rewrite where you wished Claude had landed it the first time.
---

# /style-correct

Turn one manual style correction into a permanent rule. When the user rewrites a Claude response (in their head or in a doc), this skill diffs the rewrite against what Claude actually said, derives a candidate banned-phrase rule, and appends it to the style-check config after the user confirms.

## When to use

- The user just edited a Claude response and wants the same kind of edit to happen automatically next time.
- They have a clear preference ("don't say X" / "use Y instead of Z") that isn't already in the banned list.

Skip this skill for tone / structural changes that don't reduce to a phrase swap. Tell the user to update `user_writing_style.md` directly instead.

## Step 0: locate the original

Use the most recent assistant text from the visible conversation. If the conversation has been compacted and the most recent assistant turn isn't available, ask the user to paste both versions (original and edited).

## Step 1: get the user's edit

Ask once, then wait:

> **Paste your edited version of my last response (or just the part you changed). I'll diff it against what I wrote and propose a rule.**

If the user describes the change in words instead ("don't say 'in order to'", "swap 'utilize' for 'use'"), parse the description directly and skip to Step 3.

## Step 2: diff

Compare the user's version to the original. Identify:

- **Removed phrases:** strings in the original that the user cut entirely. Each becomes a candidate banned regex.
- **Replaced phrases:** strings the user swapped for something else. The original side becomes a candidate banned regex; record the replacement as a hint in the label.
- **Reordered or structural changes:** flag for the user, do not encode as a regex.
- **Single-character tweaks** (typos, punctuation, whitespace): ignore.

For each removed or replaced phrase, build a candidate rule:

- Escape regex metacharacters in the phrase.
- If the phrase is a clean word or word sequence, wrap with `\b...\b`.
- If the phrase contains punctuation or non-word characters, drop the `\b` and use the literal pattern.
- Default `flags` to `"i"` (case-insensitive) unless the user's edit is case-sensitive.
- Build a `label` of the form `'<phrase>' (user correction)` or `'<phrase>' (user correction; prefer '<replacement>')`.

## Step 3: confirm

Show the user the candidate rule(s) in this format:

```
Proposed rules to append:

1. Pattern: \bin order to\b
   Flags:   i
   Label:   'in order to' (user correction; prefer 'to')
   Reason:  you replaced "in order to ship" with "to ship"

2. Pattern: \butilize\b
   Flags:   i
   Label:   'utilize' (user correction; prefer 'use')
   Reason:  you replaced "utilize" with "use"

Append all? [yes / pick which (e.g. "1 only") / no]
```

Wait for an explicit answer. Do not write anything until the user confirms.

If a candidate rule already exists in `banned_regexes` (same pattern), call it out and ask whether to skip or replace.

## Step 4: append to config

Read `~/.claude/hooks/style_check_config.json` with the Read tool. If the file is missing, malformed, or not a JSON object with a `banned_regexes` array, warn the user and stop.

Use the Edit tool to append the approved entries to the `banned_regexes` array. Preserve every other key in the file. Maintain valid JSON formatting.

Do not use the Write tool: it overwrites the entire file and risks losing user-added entries the model didn't see.

## Step 5: confirm and hand off

Tell the user:

1. Which rules were appended (with patterns).
2. The hook catches them on the next assistant turn.
3. They can remove or edit any rule in `~/.claude/hooks/style_check_config.json` directly.
4. If the diff included tone or structural changes you flagged but did not encode, remind the user that those belong in `user_writing_style.md` and offer to update it.

## Rerun behavior

The skill is stateless. Each invocation handles one correction. Run it again for the next one.

## Do not

- Do not write rules without explicit confirmation.
- Do not infer tone, voice, or structural rules; only banned phrases and replacements.
- Do not deduplicate silently. If a similar rule already exists, surface it.
- Do not modify any file other than `~/.claude/hooks/style_check_config.json` (and `user_writing_style.md` if the user explicitly asks).
- Do not run `git`, `gh`, or any network command.

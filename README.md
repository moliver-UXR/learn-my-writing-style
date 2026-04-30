# learn-my-writing-style

A Claude Code skill that interviews you and teaches Claude your writing voice.

It captures who you are, the tone you write in, and the AI tells you want banned. Then it wires a Stop hook that blocks responses that violate your guide before you ever see them.

## What you get

After running `/learn-my-writing-style` once:

- A profile, voice guide, and (optional) org file under `~/.claude/projects/<your-project>/memory/`
- `~/.claude/hooks/style_check_config.json` with the banned patterns you chose
- A Stop hook entry in `~/.claude/settings.json` that runs `style_check.py` after every assistant turn

If a response contains an em dash or any banned pattern (`delve`, `utilize`, `Certainly!`, etc.), the hook blocks the turn and tells the model to revise.

## Install

```bash
git clone https://github.com/moliver-UXR/learn-my-writing-style.git
cd learn-my-writing-style

mkdir -p ~/.claude/skills ~/.claude/hooks
cp -R skills/learn-my-writing-style ~/.claude/skills/
cp hooks/style_check.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/style_check.py
```

Then in any Claude Code session, run:

```
/learn-my-writing-style
```

It asks twelve quick questions, summarizes what it captured, and writes everything once you say `yes`.

## Customizing later

`~/.claude/hooks/style_check_config.json` is plain JSON. Add or remove banned regexes any time without touching the Python.

To rerun the interview, invoke `/learn-my-writing-style` again. By default it skips files that already exist, so deleting a single memory file lets you refresh just that one.

## How the hook works

`style_check.py` reads the transcript JSONL, finds the last assistant message, and scans its text for em dashes (Unicode `U+2014`) and each entry in `banned_regexes`. On a match it returns `{"decision": "block"}` with the list of violations, and the model gets that feedback to revise before ending the turn. No matches: exits 0 silently. Fails open if the config is missing or malformed, so a broken hook never bricks a session.

## Requirements

- Claude Code
- Python 3 in `$PATH`

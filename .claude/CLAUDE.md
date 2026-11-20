# standing-orders

A Claude Code plugin: one file per project of the user's orders in their own words, injected by a hook when the project
comes up and after compaction. Read `intent.md` before changing behaviour.

## Commands

```bash
python3 tests/test_orders.py          # all checks; no dependencies, uses temp folders only
claude plugin validate . --strict     # manifest, hooks and skill layout
claude --plugin-dir . plugin list     # load the working tree as a session-only plugin
```

## Layout

- `skills/standing-orders/orders.py` is the whole tool: `hook`, `new`, `list`, `reach`, `scan`, `mark`, `check`.
- `skills/standing-orders/SKILL.md` tells Claude how to use the injected block and how to build an orders file.
- `hooks/hooks.json` wires `orders.py hook` to UserPromptSubmit and to SessionStart (`compact`, `clear`).
- `.claude-plugin/` holds the plugin manifest and the one-plugin marketplace.
- `tests/test_orders.py` runs the script as a subprocess against fixture transcripts.
- `examples/webshop.md` is a finished orders file.

## Rules for changes

- Test first. Every behaviour in `orders.py` has a check in `tests/test_orders.py`; add the failing check before the fix.
- Standard library only. The hook runs on every prompt, so it stays one small file with no imports to install.
- The hook must never block or break a prompt: it exits 0 on any error and logs to `~/.cache/standing-orders/errors.log`.
- This file lives in `.claude/` because `claude plugin validate --strict` warns about a `CLAUDE.md` at a plugin root.
- Fixtures and examples are invented. Never commit real prompts, orders files or transcripts.
- Bump `__version__` in `orders.py` and `version` in `.claude-plugin/plugin.json` together.

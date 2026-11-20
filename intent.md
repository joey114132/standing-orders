# Intent

## Why this exists

People who work with Claude Code across many sessions keep repeating decisions they already made. The decision was
given in another session, or before a context compaction, so it is not in context when the next plan is written. Adding
more always-loaded rule text does not fix this: it grows the context for every unrelated task and still does not survive
compaction reliably. This plugin keeps project decisions in a short per-project file and loads it only when that project
is in play.

## Success and failure

- Success: after a compaction or in a new session, the first plan for a project is written with that project's orders
  in context, without the user restating them.
- Success: a new user can build a first orders file from their own transcripts in one sitting.
- Failure: the hook delays, blocks or breaks a prompt.
- Failure: an orders file is injected into sessions that have nothing to do with the project.
- Failure: `scan` or `reach` prints a secret, or `mark` skips past a prompt that was never shown.

## Out of scope

- Enforcing obedience. The hook makes orders present; it cannot verify that a plan honours them.
- General memory, preferences and behaviour rules. Those belong in `CLAUDE.md` or the user's memory.
- Deciding what counts as an order. `scan` lists candidates; a person or the assistant curates, quoting exactly.
- Syncing, cloud storage, team sharing. Files are local markdown the user can put under version control themselves.

## Must not break

- The hook exits 0 and prints nothing on any failure (`orders.py` `main`, hook branch). A non-zero exit on
  UserPromptSubmit can block the user's prompt.
- State is saved after the injection is printed, so an unwritable cache means repeated injection, never none.
- `scan` pages never split records that share a timestamp, because `mark` works on timestamps.
- Long transcript lines are skipped only when they are tool results; prompts typed with a pasted image are long too.
- One hook message stays under 10,000 characters, the size Claude Code passes through whole (`HOOK_LIMIT`). A longer
  orders file is cut with a visible note; projects that do not fit together go out on consecutive prompts.
- Only regular files up to `MAX_FILE` bytes in the orders folder are read, so a pipe or a stray large file cannot stall
  or flood a prompt.
- `ORDERS_SKIP` is compiled only by the transcript commands; a bad value must not break the hook.
- No network access and no dependencies beyond the Python standard library.

## Decisions

- Keyword and folder matching instead of a model call: it runs in about 30 ms, costs nothing and is predictable. The
  cost is that keywords must be chosen with care, which is what `reach` is for.
- One file per project instead of one global file, so unrelated sessions pay no tokens.
- Interpretations are written after `Reading:` so the user's words and the assistant's inference stay separable.
- Re-injection is keyed on a hash of the file body, not its modification time, so `mark` does not cause a re-injection.

## Open questions

- Sessions that work on a project without naming it and from another folder get nothing. Is there a cheap, reliable
  signal for "this session is about project X"? Check by logging misses, not by guessing.
- The transcript format is internal to Claude Code. How often does it change, and should `scan` report when it sees
  records it does not understand?
- Windows: `python3` is often not on PATH there and no test runs on it yet.

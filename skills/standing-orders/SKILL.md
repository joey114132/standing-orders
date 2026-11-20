---
name: standing-orders
description: "Start, review or update a project's standing orders: one file per project of the user's orders and decisions in their own words, so they survive new sessions and context compaction. Use when the user says you forgot or ignored something they already told you (\"I told you\", \"I already said\", \"how many times\", 했잖아, 말했잖아), when a STANDING ORDERS block was injected for the project in play, before writing a plan, a subagent brief, a design or a schedule for a project that has an orders file, or when the user asks to collect what they have decided for a project."
allowed-tools:
  - Read
  - Grep
  - Glob
---

# standing-orders

An order the user gave in another session, or before a compaction, is no longer in context when the plan is written.
Nobody opens the record, the plan follows the assistant's defaults, and the user has to say it again. This skill keeps
each project's orders in one short file and puts that file back in context at the moments it is needed.

It covers what the user decided **about a project**: targets, scope, limits, bans, delegations, and which real-world
actions need their go-ahead. General behaviour belongs in `CLAUDE.md`; facts about the world belong in memory.

## Parts

- `~/.claude/orders/<project>.md` holds the orders. One file per project, under about 9,000 characters: Claude Code
  passes a hook message whole only up to 10,000, and the hook cuts a longer file and says so.
- `${CLAUDE_SKILL_DIR}/orders.py` is the tool. Its `hook` mode is wired by the plugin; the other commands are run by hand.
- The hook injects a project's file once per session when the prompt contains one of its keywords or the working
  directory is under one of its paths. It injects again when the file changed, after every compaction, and after `/clear`.

## When a STANDING ORDERS block is in context

Before a plan, a brief to a subagent or another model, a design, a schedule, or a statement about what is allowed,
write one line for each order the work touches: `order N: how this satisfies it`. Quote the touched orders verbatim in
any brief, because a subagent that starts with a fresh context does not receive the block. An order that cannot be satisfied is told to the user before
the work starts. Preferring something simpler or more cautious is not a reason to deviate. When two orders conflict the
newest wins; if that is unclear, say so and ask once.

An order marked OPEN is work the user asked for that does not exist yet. Mention every OPEN order when reporting on the
project, so a partial result is never presented as the whole answer.

For a plan file or a brief that goes to someone else, make the ledger checkable:

```bash
python3 "${CLAUDE_SKILL_DIR}/orders.py" check <project> /path/to/PLAN.md
```

It exits 1 and names each order with no `order N:` line. Write `order N: n/a, <why>` for orders the work does not touch.

## When the user gives a new order or decision

Add it to the project's file in the same turn: a short bold title, their words in quotes, the date. If the words allow
more than one reading, add your reading after `Reading:` and tell the user what you assumed. Delete or rewrite the order
it replaces. An option picked in a question dialog is a decision and is recorded the same way, with the question.

## When the user says "I already told you"

1. Find the record before answering: the orders file first, then `orders.py scan <project>`, then other notes.
2. Say which order was missed and fix the work in the same turn.
3. If the order was not in the file, add it. If it was there and still missed, say so plainly; do not add a second copy.

## Starting a project file, or catching up

1. `orders.py new <project> --keywords "word, another" --paths /abs/project/dir`. Keywords are the words the user
   actually types for this project, and each must be rare outside it.
2. `orders.py reach <project>` lists every past prompt the keywords match. Read every hit; remove or lengthen a keyword
   that matches other work.
3. `orders.py scan <project>` prints what the user typed or answered since the last mark, in the twelve prompts after
   each mention of the project, oldest first, times in UTC. `=` marks text already quoted in the file, `*` marks text
   that reads like an order. A short reply is shown with the end of the message it answered.
4. Curate. Keep targets, scope, limits, bans, delegations and choices; drop status questions and chat. Quote exactly and
   never write an order the transcript does not support. Anything past the quote goes after `Reading:` or cites the
   record it comes from. For anything marked done or OPEN, check the repository first and date the state line.
5. `orders.py mark <project> <timestamp>` with the timestamp scan printed, so the next scan starts there.

See `examples/webshop.md` in the repository for a finished file.

## Gotchas

- **A partial result looks finished.** The OPEN orders are where the missing half shows. Read them before reporting.
- **Caution reads like an order.** "Needs approval every time" feels safe to write and may contradict what the user
  decided. A limit the user never stated is a reading and is labelled as one.
- **A short reply is an order only next to its question.** "B", "yes" and "do it" are recorded with what they answered.
- **The hook makes orders present, not obeyed.** `check` proves each order has a line, not that the line is true.
- **Fresh subagents do not receive the block.** The brief must quote the orders it touches.
- **State lines rot.** "No code yet" was true on the day it was written. Re-check and re-date before repeating it.
- **A broad keyword injects the file into unrelated sessions.** A product name is fine; `plan` or `api` is not.
- **Scan misses orders given where the project was never named.** When the user says an order exists and scan does not
  show it, ask which session it was said in, or add the word they used there as a keyword and scan again.
- **An orders file is an instruction and is printed as it is.** Never copy a credential into one, and never point the
  orders folder at a file the user did not write or review.

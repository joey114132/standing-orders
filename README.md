# standing-orders

A Claude Code plugin that stops you from having to say the same thing twice.

[한국어](README.ko.md)

You tell Claude "deploy to staging only" on Monday. On Thursday, in a new session or after the conversation was
compacted, Claude plans a production deploy, and you type "I already told you". By the time the plan was written, the
instruction had dropped out of the context.

standing-orders keeps what you decided about a project in one short file, in your own words, and a hook puts that file
back in front of Claude whenever the project comes up and again after every compaction.

## What you get

When you mention a project, Claude receives a block like this before it reads your prompt (shortened here):

```text
## STANDING ORDERS: webshop (5 orders, the user's words; newest wins)
File: ~/.claude/orders/webshop.md. Before a plan, a brief to a worker, a design, a schedule or a claim about
what is allowed in this project, write one line per order the work touches: "order N: how this satisfies it". ...

1. **Staging only.** "you can deploy to staging yourself, never to production" (2026-03-02).
   Reading: a production deploy is prepared and handed over, not run.
2. **Tests first.** "no fix without a failing test first" (2026-03-02).
3. **Money stays in integer cents.** "we got burned by floats once, cents everywhere" (2026-03-05).
4. **Guest checkout must keep working.** "don't make people sign up to pay" (2026-03-09).
   State 2026-03-20: the address-book change still requires an account. OPEN.
```

The plugin has three parts. The hook does the injection. The skill tells Claude how to use the block: answer each order
with a line before planning, record a new decision the moment you make it, and report every order still marked OPEN.
The `orders.py` tool builds the file in the first place by reading your past conversations and listing what you
actually typed about the project, so you do not have to remember your own decisions to write them down.

## Install

In Claude Code:

```text
/plugin marketplace add joey114132/standing-orders
/plugin install standing-orders@standing-orders
```

Or from a shell:

```bash
claude plugin marketplace add joey114132/standing-orders
claude plugin install standing-orders@standing-orders
```

Restart Claude Code or run `/reload-plugins` afterwards. The plugin needs `python3` (3.9 or newer) on the PATH that
Claude Code sees and has no other dependencies. It was written and tested on Linux with Claude Code 2.1.328 and 2.1.329,
and the test suite also runs on macOS and Windows in CI. On Windows the hooks need Git Bash, which Claude Code uses for
hook commands when it is installed, and a real Python: if `python3` is only the Microsoft Store placeholder, install
Python or turn that alias off. The hook wiring itself has not been tried on a real Windows install.

<details>
<summary>Install without the plugin system</summary>

Copy `skills/standing-orders` into `~/.claude/skills/` and add the hooks to `~/.claude/settings.json`. If that file
already has a `hooks` section, add these entries to its existing arrays instead of replacing them:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "timeout": 5,
          "command": "python3 \"$HOME/.claude/skills/standing-orders/orders.py\" hook || true" } ] }
    ],
    "SessionStart": [
      { "matcher": "compact", "hooks": [ { "type": "command", "timeout": 5,
          "command": "python3 \"$HOME/.claude/skills/standing-orders/orders.py\" hook --after-compact || true" } ] },
      { "matcher": "clear", "hooks": [ { "type": "command", "timeout": 5,
          "command": "python3 \"$HOME/.claude/skills/standing-orders/orders.py\" hook --reset || true" } ] }
    ]
  }
}
```

</details>

## Try it in two minutes

1. In any session, tell Claude a decision and ask it to keep it:

   > For the webshop project: deploy to staging only, never to production. Save that as a standing order with the keywords "webshop" and "checkout".

   Claude creates `~/.claude/orders/webshop.md` with your sentence quoted and dated, and may ask your permission to
   run the tool and write the file. If it does not pick the skill up by itself, start the message with
   `/standing-orders:standing-orders`.
2. Open a new session and ask "for the checkout work, which standing orders do you have?" The word "checkout" makes
   the hook inject the file before Claude reads the question, so the answer comes from context that a new session
   would otherwise not have.

## Start a project file from your history

You have probably given most of your orders already. To collect them, ask Claude:

> Start a standing-orders file for this project. Scan my past sessions for what I decided and show me the list before you save it.

Claude runs the steps below and curates the result. You can also run them yourself from a clone of this repository:

```bash
alias orders='python3 /path/to/standing-orders/skills/standing-orders/orders.py'

orders new webshop --keywords "webshop, checkout, payments" --paths ~/code/webshop
orders reach webshop     # every past prompt those keywords match; drop a keyword that hits other work
orders scan webshop      # what you typed or answered about the project, oldest first
$EDITOR ~/.claude/orders/webshop.md
orders mark webshop 2026-03-20T09:41:07   # the timestamp scan printed; the next scan starts there
```

`scan` reads only sessions that mention the project. In each one it keeps every prompt that mentions it and the twelve
prompts that follow, then prints 150 candidates at a time (a few more when several share a timestamp), oldest first;
`mark` moves the starting point. `=` means the
text already appears inside a quote in the file, which is a substring test and only a hint. `*` reads like an order. A
short reply such as "yes" or "B" is printed with the end of the assistant message before it, because on its own it means
nothing. Answers you picked in a question dialog are included with their question. `reach` lists each distinct prompt of
up to 600 characters once and shows its first 200 characters.

A finished file looks like [examples/webshop.md](examples/webshop.md). Each order is a short bold title, your words in
quotes, and the date. Anything the assistant infers beyond the quote goes after `Reading:`, so you can always tell your
decision from its interpretation. Mark work you asked for that does not exist yet as `OPEN`.

## Commands

| Command | What it does |
| --- | --- |
| `orders.py new <project> --keywords a,b [--paths /dir]` | Creates `~/.claude/orders/<project>.md` with its header |
| `orders.py list` | Projects, order counts, keywords and paths |
| `orders.py reach <project>` | Past prompts the keywords would have matched |
| `orders.py scan <project> [--limit N]` | Candidates since the last mark, from sessions that mention the project |
| `orders.py mark <project> <timestamp>` | Records how far the transcripts were read (UTC, as `scan` prints it) |
| `orders.py check <project> <file>` | Exits 1 unless the file has an `order N:` line for every order. It checks that the line exists, not what it says |
| `orders.py hook [--after-compact \| --reset]` | The hook entry points; they read the event on stdin |

`check` is for plans and briefs that leave the session. A subagent that starts with a fresh context does not receive the
injected block, so the brief has to carry the orders, and `check` shows which one was skipped.

## How injection is decided

A project's file is injected when the prompt contains one of its keywords, compared in lowercase as plain substrings, or
when the session's working directory is at or under one of its paths. That happens once per session. Once a project is
active in a session, its file is injected again when the content changes and after each compaction; `/clear` forgets
the session's projects until the next match. A session that never mentions the project and runs elsewhere gets nothing,
so other work does not pay for these tokens.

Claude Code passes a hook message whole only up to 10,000 characters, so keep an orders file under about 9,000. A
longer file is cut at a line boundary with a note telling Claude to read the rest. When two projects match at once and
do not fit together, the second one arrives on the next prompt.

Because the match is a substring, choose keywords that are rare outside the project. A product name works. `plan`,
`api` or a two-letter abbreviation will put the file into unrelated sessions, and `reach` shows you that before it happens.

The hook puts the orders in the context; it cannot make the model obey them. The skill narrows that gap by asking for
a visible line per order, and `check` makes a missing line detectable, but a line can still be wrong. When an order is
missed anyway, you have a numbered line to point at.

## Privacy and trust

The plugin makes no network calls and has no telemetry. Orders files live in `~/.claude/orders` and per-session state
in `~/.cache/standing-orders`.

An orders file is injected into Claude's context, so its text reaches the model provider with the rest of your
conversation, exactly like `CLAUDE.md`. The same holds for `scan` and `reach` output when you ask Claude to run them.
Keep credentials out of orders files: the hook prints them as they are, `list` prints their header and `check`
prints the start of any order a plan skipped.

An orders file is also an instruction to Claude. Put only files you wrote or reviewed in the orders folder, and do not
link it to a file someone else controls.

`scan` and `reach` read Claude Code's transcripts under `~/.claude/projects` and print what you typed. They redact
passwords, key and token assignments, bearer and basic headers, credentials in URLs, JWTs, PEM blocks and long
token-like strings on a best-effort basis. A regex cannot promise secrecy, so read the output before you paste it
somewhere. To keep some transcripts out of both commands, set `ORDERS_SKIP` to a regular expression matched against the
transcript path. Claude Code names each transcript folder after the working directory with slashes turned into dashes,
so `ORDERS_SKIP='-(clients|personal)(-|[/\\])'` skips sessions started in or under a `clients` or `personal` folder. Headless runs
(`claude -p` and other SDK entry points) are ignored by `scan`, `reach` and, unless `ORDERS_HEADLESS=1` is set, the hook.

The transcript format is internal to Claude Code and can change. If it does, `scan` and `reach` find less; the hook does
not read transcripts and keeps working.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `ORDERS_DIR` | `~/.claude/orders` | Where orders files live |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Moves both defaults when the two variables around it are unset |
| `ORDERS_PROJECTS` | `~/.claude/projects` | Where Claude Code keeps transcripts |
| `ORDERS_SKIP` | unset | Regex; transcripts whose path matches are never read |
| `ORDERS_HEADLESS` | unset | Set to `1` to inject in headless `claude -p` runs too |
| `XDG_CACHE_HOME` | `~/.cache` | Parent of the per-session state folder |

## Development

```bash
python3 tests/test_orders.py        # 75 checks, no dependencies
claude plugin validate . --strict
```

Bug reports are most useful with the output of `orders.py --version`, your Claude Code version, and the smallest orders
file that shows the problem. A hook run that fails stays silent so it cannot block your prompt, and tries to leave a
trace in `~/.cache/standing-orders/errors.log`.

## License

MIT

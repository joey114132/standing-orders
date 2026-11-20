#!/usr/bin/env python3
# standing-orders: keeps each project's user orders in one file, injects it when the project comes up (hook), harvests candidates from transcripts (scan), and checks a plan against it (check)
"""usage:
  orders.py new <project> --keywords a,b [--paths /dir,/dir2]   start an orders file
  orders.py list                                                projects, order counts, keywords
  orders.py reach <project>             past prompts the keywords would have matched; read them before trusting the keywords
  orders.py scan <project> [--limit N]  what the user typed or answered since scanned_until, in sessions about the project
  orders.py mark <project> <ISO>        set scanned_until after the candidates were curated
  orders.py check <project> <file>      exit 1 unless <file> has an "order N: ..." line for every order
  orders.py hook [--after-compact | --reset]   Claude Code hook; reads the event on stdin (wired by hooks/hooks.json)
  orders.py --version

An orders file is markdown with a small header, in ~/.claude/orders/<project>.md:
  ---
  project: webshop
  keywords: checkout, payments        (lowercase substrings of a prompt)
  paths: /home/me/webshop             (session working directory at or under one of these)
  scanned_until: 2026-11-18T01:05:00  (UTC, written by mark)
  ---
  1. **Short title.** "the user's words" (date) ...

Environment: ORDERS_DIR (default ~/.claude/orders), ORDERS_PROJECTS (default ~/.claude/projects, where Claude Code
keeps transcripts), CLAUDE_CONFIG_DIR (moves both defaults), ORDERS_SKIP (regex; transcripts whose path matches are
never read), XDG_CACHE_HOME.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

HOME = Path.home()
CONFIG = Path(os.environ.get("CLAUDE_CONFIG_DIR") or HOME / ".claude")
ORDERS_DIR = Path(os.environ.get("ORDERS_DIR") or CONFIG / "orders")
PROJECTS = Path(os.environ.get("ORDERS_PROJECTS") or CONFIG / "projects")
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or HOME / ".cache") / "standing-orders"
HOOK_LIMIT = 9500       # Claude Code passes a hook string whole only up to 10,000 characters; longer ones become a file and a preview
MAX_FILE = 200_000      # bytes; anything bigger in the orders folder is not an orders file and is never read
MAX_RECORD = 20000      # typed prompts are short; longer transcript lines are tool output
MAX_SHOWN = 2000        # scan prints a prompt whole up to this many characters and says so when it cuts
WINDOW = 12             # scan keeps this many prompts after each mention of the project
NOT_USER = ("Stop hook feedback", "Another Claude session sent a message", "<", "[SYSTEM NOTIFICATION", "[Request interrupted",
            "Skill /", "(Re-invocation of", "Base directory for this skill")      # harness text posed as a user turn
STATE_DAYS = 30         # per-session state older than this is pruned
__version__ = "0.1.0"
ORDER_LIKE = re.compile(r"must|always|never|don'?t|do not|\bonly\b|from now|\brule|해야|하지 ?마|말고|금지|무조건|항상|절대|맡길|로 해|만 해|빼지|넣지", re.I)
USER_REC = re.compile(r'"type":\s*"user"')
ORDER_LINE = re.compile(r"^(\d+)\.\s+(.+)$", re.M)
INSTRUCTION = (
    'Before a plan, a brief to a worker, a design, a schedule or a claim about what is allowed in this project, write one '
    'line per order the work touches: "order N: how this satisfies it". An order you cannot satisfy is told to the user '
    "before the work starts, not found by the user afterwards. When the user gives a new order or decision for this project, "
    "add it to the file in the same turn with their words and the date, and delete what it replaces.")


def load(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = {}, text
    if text.startswith("---\n"):
        head, _, body = text[4:].partition("\n---\n")
        for line in head.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                meta[key.strip()] = value.strip()

    def items(key: str) -> list[str]:
        return [x.strip() for x in meta.get(key, "").split(",") if x.strip()]

    body = body.strip()
    return {"name": meta.get("project", path.stem), "path": path, "body": body, "since": meta.get("scanned_until", ""),
            "keywords": [k.lower() for k in items("keywords")], "paths": [p.rstrip("/") for p in items("paths")],
            "orders": [(int(n), t) for n, t in ORDER_LINE.findall(body)],
            "digest": hashlib.sha1(body.encode()).hexdigest()[:12]}


def all_orders() -> list[dict]:
    out = []
    if ORDERS_DIR.is_dir():
        for p in sorted(ORDERS_DIR.glob("*.md")):
            try:
                # is_file() is False for a pipe or a device, so nothing here can block or flood a prompt
                if p.is_file() and p.stat().st_size <= MAX_FILE:
                    out.append(load(p))
            except OSError:
                continue
    return out


def find(name: str) -> dict:
    for o in all_orders():
        if o["name"] == name or o["path"].stem == name:
            return o
    sys.exit(f"no orders file for '{name}' in {ORDERS_DIR} (have: {', '.join(o['name'] for o in all_orders()) or 'none'})")


def skip_pattern():
    """The ORDERS_SKIP regex, or None. Only the transcript commands call this, so a bad value cannot break the hook."""
    raw = os.environ.get("ORDERS_SKIP")
    if not raw:
        return None
    try:
        return re.compile(raw)
    except re.error as e:
        sys.exit(f"ORDERS_SKIP is not a valid regular expression: {e}")


def under(cwd: str, paths: list[str]) -> bool:
    return any(cwd == d or cwd.startswith(d + "/") for d in paths)


def render(o: dict, room: int = HOOK_LIMIT) -> str:
    head = (f"## STANDING ORDERS: {o['name']} ({len(o['orders'])} orders, the user's words; newest wins)\n"
            f"File: {o['path']}. {INSTRUCTION}\n\n")
    body = o["body"]
    if len(head) + len(body) > room:                # never cut silently: say how much is missing and where it is
        keep = body[:max(0, room - len(head) - 160)]
        keep = keep[:keep.rfind("\n")] if "\n" in keep else keep
        body = f"{keep}\n[{len(body) - len(keep)} characters not shown: this file is too long for one hook message. Read it, then trim it.]"
    return head + body


def prune_state() -> None:
    cutoff = time.time() - STATE_DAYS * 86400
    for f in CACHE.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass                                    # another session removed it first


def hook(after_compact: bool, reset: bool = False) -> int:
    # headless `claude -p` runs are not the user talking
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT", "").startswith("sdk"):
        return 0
    try:
        ev = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(ev, dict):
        return 0
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(ev.get("session_id", "")))[:64] or "none"
    state_path = CACHE / f"{sid}.json"
    if reset:                                       # /clear emptied the context: forget what this session was given
        state_path.unlink(missing_ok=True)
        return 0
    try:
        state = json.loads(state_path.read_text())
    except (OSError, ValueError):
        state = {}                                  # first prompt of the session, or an unreadable state file: inject again
    if not isinstance(state, dict):
        state = {}
    cwd = str(ev.get("cwd", ""))
    if after_compact:
        due = [o for o in all_orders() if o["name"] in state or under(cwd, o["paths"])]
    else:
        prompt = ev.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or prompt.lstrip().startswith(NOT_USER):
            return 0
        low = prompt.lower()
        # a project already active in this session is refreshed on any prompt once its file changed
        due = [o for o in all_orders() if state.get(o["name"]) != o["digest"]
               and (o["name"] in state or any(k in low for k in o["keywords"]) or under(cwd, o["paths"]))]
    if not due:
        return 0
    parts, used = [], 0
    for o in due:
        if parts and len(render(o)) + 2 > HOOK_LIMIT - used:
            state[o["name"]] = ""                   # does not fit beside the others: it stays due and goes out on the next prompt
            continue
        parts.append(render(o, HOOK_LIMIT - used))
        used += len(parts[-1]) + 2
        state[o["name"]] = o["digest"]
    event = "SessionStart" if after_compact else "UserPromptSubmit"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": "\n\n".join(parts)}}, ensure_ascii=False))
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state))
        prune_state()
    except OSError:
        pass                                        # state not saved: the orders are injected again next time, which is the safe side
    return 0


SECRET_KEY = r"pwd|password|passwd|비밀번호|비번|api[_-]?key|api[_-]?secret|secret[_-]?key|secret|token|authorization"


def mask(text: str) -> str:
    """Best-effort redaction for text that is about to be printed. A regex cannot promise secrecy."""
    text = re.sub(r"-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----", "[redacted key]", text, flags=re.S)
    text = re.sub(r"(://[^\s/:@]+:)[^\s/@]+@", r"\1[redacted]@", text)                       # user:password@host
    text = re.sub(r"(?i)\b(basic|bearer)\s+[A-Za-z0-9+/=._~-]{6,}", r"\1 [redacted]", text)
    text = re.sub(r"(?i)([\"']?(?:" + SECRET_KEY + r")[\"']?\s*[:=]\s*)([\"'])[^\"']*\2", r"\1\2[redacted]\2", text)   # "key": "value"
    text = re.sub(r"(?i)\b(pwd|password|passwd|비밀번호|비번)(\s*[:=]?\s*)(?![\"'\[])\S+", r"\1\2[redacted]", text)
    text = re.sub(r"(?i)\b(api[_-]?key|api[_-]?secret|secret[_-]?key|secret|token|authorization)(\s*[:=]\s*|\s+(?=\S*\d))(?![\"'\[])\S+",
                  r"\1\2[redacted]", text)
    text = re.sub(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}", "[redacted]", text)        # JWT
    text = re.sub(r"\b(?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]{24,}\b", "[redacted]", text)
    return re.sub(r"\b[A-Za-z0-9]{32,}\b", "[redacted]", text)


def typed(rec: dict) -> str:
    """What the user typed in this transcript record, or ''."""
    if rec.get("isMeta") or rec.get("isCompactSummary") or rec.get("isSidechain"):
        return ""
    msg = rec.get("message")
    c = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(c, list):
        c = " ".join(str(x.get("text", "")) for x in c if isinstance(x, dict) and x.get("type") == "text")
    c = " ".join(c.split()) if isinstance(c, str) else ""
    return "" if c.startswith(NOT_USER) else c


def assistant_tail(raw: str) -> str:
    try:
        obj = json.loads(raw)
    except ValueError:
        return ""
    msg = obj.get("message") if isinstance(obj, dict) else None
    c = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(c, list):
        c = " ".join(str(x.get("text", "")) for x in c if isinstance(x, dict) and x.get("type") == "text")
    # mask before clipping: a secret cut in half by the clip would no longer look like one
    return mask(" ".join(c.split()))[-160:] if isinstance(c, str) else ""


def session_records(path: Path) -> list[dict]:
    """Every typed prompt and AskUserQuestion answer of one transcript: {ts, cwd, text, re}."""
    out, last_assistant = [], ""
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            # long lines are tool output, except question answers and prompts typed with a pasted image
            if len(line) > MAX_RECORD and (not USER_REC.search(line) or ('"tool_use_id"' in line and '"answers"' not in line)):
                continue
            if '"assistant"' in line and '"text"' in line and not USER_REC.search(line):
                last_assistant = line               # parsed only if a short reply follows
                continue
            if not USER_REC.search(line):
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("type") != "user" or str(rec.get("entrypoint", "")).startswith("sdk"):
                continue                            # headless runs (summarizers, scheduled jobs) are not the user talking
            base = {"ts": str(rec.get("timestamp", ""))[:19], "cwd": str(rec.get("cwd", "")), "re": ""}
            result = rec.get("toolUseResult")
            if isinstance(result, dict) and isinstance(result.get("answers"), dict):
                for q, a in result["answers"].items():
                    out.append({**base, "answer": True, "text": f"Q: {' '.join(str(q).split())} -> A: {a}"})
                continue
            text = typed(rec)
            if text:
                # a short reply ("yes", "do it") only means something next to what it answered
                out.append({**base, "text": text, "re": assistant_tail(last_assistant) if len(text) < 80 else ""})
    return out


def scan(name: str, limit: int) -> int:
    if limit < 1:
        sys.exit("--limit must be 1 or more")
    o = find(name)
    since = o["since"][:19]
    floor = dt.datetime.fromisoformat(since).replace(tzinfo=dt.timezone.utc).timestamp() if since else 0.0
    quotes = re.findall(r'"([^"]{6,})"', o["body"])
    rows, skip = [], skip_pattern()
    for path in PROJECTS.glob("*/*.jsonl"):
        if (skip and skip.search(str(path))) or path.stat().st_mtime < floor:
            continue
        left = 0                                    # long mixed sessions: only what follows a mention of the project
        for r in session_records(path):
            if under(r["cwd"], o["paths"]) or any(k in r["text"].lower() for k in o["keywords"]):
                left = WINDOW + 1
            if left > 0 and r["ts"] > since:
                rows.append({**r, "sid": path.stem[:8]})
            left -= 1
    rows.sort(key=lambda r: r["ts"])
    if not rows:
        print(f"no new candidates for {o['name']} since {since or 'the beginning'}")
        return 0
    cut = rows[min(limit, len(rows)) - 1]["ts"]     # records that share a timestamp stay on one page, or mark would skip them
    shown = [r for r in rows if r["ts"] <= cut]
    for r in shown:
        known = r["text"] in o["body"] or any(q in r["text"] for q in quotes)
        flag = "=" if known else "*" if ORDER_LIKE.search(r["text"]) else " "
        context = f"  <- re: ...{r['re']}" if r["re"] else ""
        text = mask(r["text"])
        if len(text) > MAX_SHOWN:                   # never cut silently: the order is often the last sentence
            text = f"{text[:MAX_SHOWN]} [+{len(text) - MAX_SHOWN} chars, read the transcript before marking]"
        print(f"{flag} {r['ts'][:16]} {r['sid']} {text}{context}")
    more = f"{len(rows) - len(shown)} more after this; " if len(rows) > len(shown) else ""
    print(f"\n{len(shown)} shown ('=' already in the file, '*' reads like an order). {more}"
          f"after curating: orders.py mark {o['name']} {shown[-1]['ts']}")
    return 0


def mark(name: str, stamp: str) -> int:
    try:
        ok = bool(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", stamp)) and dt.datetime.fromisoformat(stamp)
    except ValueError:
        ok = False
    if not ok:
        sys.exit("timestamp must be a real UTC time like 2026-11-18T01:05:00, as scan prints it")
    o = find(name)
    text = o["path"].read_text(encoding="utf-8")
    if not (text.startswith("---\n") and "\n---\n" in text[4:]):
        sys.exit(f"{o['path']} has no closed header (--- ... ---) to hold scanned_until")
    line = f"scanned_until: {stamp}"
    if re.search(r"(?m)^scanned_until:.*$", text):
        text = re.sub(r"(?m)^scanned_until:.*$", line, text, count=1)
    else:
        text = text.replace("\n---\n", f"\n{line}\n---\n", 1)
    tmp = o["path"].with_name(o["path"].name + ".tmp")          # write beside it, then swap: a crash never leaves half a file
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, o["path"])
    print(f"{o['name']}: {line}")
    return 0


def check(name: str, file: str) -> int:
    o = find(name)
    have = {int(n) for n in re.findall(r"(?im)^\W*order\s+(\d+)\s*:", Path(file).read_text(encoding="utf-8"))}
    missing = [(n, t) for n, t in o["orders"] if n not in have]
    for n, t in missing:
        print(f"missing order {n}: {t[:120]}")
    print(f"{o['name']}: {len(o['orders']) - len(missing)} of {len(o['orders'])} orders have a line in {file}")
    return 1 if missing else 0


def reach(name: str) -> int:
    o = find(name)
    seen, hits, skip = set(), [], skip_pattern()
    for path in PROJECTS.glob("*/*.jsonl"):
        if skip and skip.search(str(path)):
            continue
        for r in session_records(path):
            text = r["text"]
            if r.get("answer") or len(text) > 600 or text in seen:
                continue
            seen.add(text)
            keys = [k for k in o["keywords"] if k in text.lower()]
            if keys:
                hits.append(f"[{', '.join(keys)}] {mask(text)[:200]}")
    print("\n".join(hits))
    print(f"\n{len(hits)} of {len(seen)} past prompts match {o['name']}; a keyword that hits other work is removed or made longer")
    return 0


def new(name: str, keywords: str, paths: str) -> int:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        sys.exit("project name: letters, digits, dot, dash and underscore only")
    keys = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    if not keys and not paths.strip():
        sys.exit("give --keywords and/or --paths, or the file can never be injected")
    target = ORDERS_DIR / f"{name}.md"
    ORDERS_DIR.mkdir(parents=True, exist_ok=True)
    folders = ", ".join(p.strip() for p in paths.split(",") if p.strip())
    try:
        with open(target, "x", encoding="utf-8") as f:           # "x": fails if anything is already there, a dangling link included
            f.write(f"---\nproject: {name}\nkeywords: {', '.join(keys)}\npaths: {folders}\n---\n"
                    f"# {name} standing orders (the user's words; newest wins)\n\n")
    except FileExistsError:
        sys.exit(f"{target} already exists")
    print(f"created {target}\nnext: orders.py reach {name}   (check the keywords), then orders.py scan {name}")
    return 0


def option(args: list[str], flag: str, default: str = "") -> str:
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else default


def main() -> int:
    args = sys.argv[1:]
    if args[:1] in (["--version"], ["version"]):
        print(__version__)
        return 0
    if args[:1] == ["hook"]:
        try:
            return hook("--after-compact" in args, "--reset" in args)
        except Exception:                           # a hook that raises would break every prompt; leave a trace and stay quiet
            try:
                CACHE.mkdir(parents=True, exist_ok=True)
                with open(CACHE / "errors.log", "a") as f:
                    f.write(f"{dt.datetime.now().isoformat(timespec='seconds')}\n{traceback.format_exc()}\n")
            except OSError:
                pass
            return 0
    if args[:1] == ["list"]:
        for o in all_orders():
            print(f"{o['name']}: {len(o['orders'])} orders, scanned until {o['since'] or 'never'}, "
                  f"keywords [{', '.join(o['keywords'])}], paths [{', '.join(o['paths'])}]")
        return 0
    if args[:1] == ["new"] and len(args) >= 2:
        return new(args[1], option(args, "--keywords"), option(args, "--paths"))
    if args[:1] == ["scan"] and len(args) >= 2:
        limit = option(args, "--limit", "150")
        if not limit.isdigit():
            sys.exit("--limit must be a whole number")
        return scan(args[1], int(limit))
    if args[:1] == ["mark"] and len(args) == 3:
        return mark(args[1], args[2])
    if args[:1] == ["check"] and len(args) == 3:
        return check(args[1], args[2])
    if args[:1] == ["reach"] and len(args) == 2:
        return reach(args[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())

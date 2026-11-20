# Tests for orders.py: the orders file is injected only at the right moments, scan keeps only what the user typed, check finds a missing order
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parent.parent / "skills/standing-orders/orders.py")

ORDERS = """---
project: webshop
keywords: checkout, 결제, payments
paths: /work/webshop
scanned_until: 2026-11-01T00:00:00
---
# webshop standing orders

1. **Staging only.** "배포는 스테이징까지만 맡길게" (11-18)
2. **No push.** "push 는 내가 말할 때만" (10-21)
"""


def rec(kind, text, ts, cwd="/home/u", **extra):
    return json.dumps({"type": kind, "timestamp": ts, "cwd": cwd, "message": {"content": text}, **extra}, ensure_ascii=False)


def setup():
    root = Path(tempfile.mkdtemp())
    (root / "orders").mkdir()
    (root / "orders/webshop.md").write_text(ORDERS, encoding="utf-8")
    proj = root / "projects/-home-u"
    proj.mkdir(parents=True)
    (proj / "aaaa1111.jsonl").write_text("\n".join([
        rec("user", "old checkout note, do not scan", "2026-10-01T01:00:00.000Z"),
        rec("user", "checkout 왜 깨졌어?", "2026-11-18T01:00:00.000Z"),
        rec("user", "checkout api_key=PKABCDEFGHIJKLMNOPQR 로 바꿨어", "2026-11-18T01:00:20.000Z"),
        rec("user", "checkout 호출은 Authorization: Bearer abc.def.ghi99 로 해", "2026-11-18T01:00:30.000Z"),
        json.dumps({"type": "user", "timestamp": "2026-11-18T01:00:31.000Z", "message": None}),
        json.dumps(["type", "user"]),
        rec("user", 'checkout config {"api_key": "QUOTEDKEYVALUE", "db": "postgres://admin:URLPASSWORD@db.example/shop"}',
            "2026-11-18T01:00:32.000Z"),
        rec("user", "checkout uses Authorization: Basic QkFTSUNBVVRIVkFMVUU= and jwt eyJhbGciOi.eyJzdWIiOiJKV1RCT0RZ.c2lnbmF0dXJlSldU",
            "2026-11-18T01:00:33.000Z"),
        rec("user", "checkout key -----BEGIN PRIVATE KEY----- PEMBODYVALUE -----END PRIVATE KEY----- and "
                    "token LETTERSONLYTOKENLETTERSONLYTOKENLETTERS", "2026-11-18T01:00:34.000Z"),
        rec("user", 'checkout cfg {"password": "abc\'QUOTEMIXVALUE", "token": "ab\\"ESCAPEDTAILVALUE"} and https://USERINFOONLYTOKEN@host/x',
            "2026-11-18T01:00:34.500Z"),
        rec("user", "checkout should offer passwordless login and a password reset page", "2026-11-18T01:00:34.700Z"),
        rec("assistant", [{"type": "text", "text": "the password: CLIPPEDSECRET " + "y" * 150}], "2026-11-18T01:00:35.000Z"),
        rec("user", "checkout ok", "2026-11-18T01:00:36.000Z"),
        rec("user", "checkout " + "context " * 40 + "never change live settings", "2026-11-18T01:00:40.000Z"),
        rec("assistant", [{"type": "text", "text": "스테이징에 배포하는 계획을 쓸까요?"}], "2026-11-18T01:01:00.000Z"),
        rec("user", "yeah 배포는 스테이징까지만 맡길게", "2026-11-18T01:02:00.000Z"),
        rec("user", "Stop hook feedback: review missing", "2026-11-18T01:03:00.000Z", isMeta=True),
        rec("user", "This session is being continued from a previous conversation", "2026-11-18T01:04:00.000Z", isCompactSummary=True),
        rec("user", [{"type": "tool_result", "content": "ok"}], "2026-11-18T01:05:00.000Z",
            toolUseResult={"questions": [{"question": "다음 방향은?"}], "answers": {"다음 방향은?": "스테이징 먼저", "배포 주기는?": "하루 한 번"}}),
        rec("user", "<system-reminder>injected</system-reminder>", "2026-11-18T01:06:00.000Z"),
        rec("user", "Below is a log about checkout. Create a summary", "2026-11-18T01:07:00.000Z", entrypoint="sdk-cli"),
        # a prompt typed with a pasted image is one very long line (hundreds of thousands of characters)
        rec("user", [{"type": "image", "source": {"data": "A" * 30000}}, {"type": "text", "text": "이 화면처럼 금요일 배포는 하지 마"}],
            "2026-11-18T01:08:00.000Z", promptSource="user"),
        # an assistant text that mentions a record type is still the context of the short reply after it
        rec("assistant", [{"type": "text", "text": 'grep \'"type":"user"\' 로 셌습니다. 타이머를 켤까요?'}], "2026-11-18T01:09:00.000Z"),
        rec("user", "ㅇㅇ 켜", "2026-11-18T01:10:00.000Z"),
    ]) + "\n", encoding="utf-8")
    # a long mixed session: only the 12 prompts after a project mention are candidates
    (proj / "cccc3333.jsonl").write_text("\n".join(
        [rec("user", "결제 모듈 상태 봐줘", "2026-11-17T01:00:00.000Z")]
        + [rec("user", f"딴 얘기 {i}번", f"2026-11-17T02:{i:02d}:00.000Z") for i in range(1, 15)]) + "\n", encoding="utf-8")
    (proj / "bbbb2222.jsonl").write_text(rec("user", "README 오타 고쳐줘", "2026-11-18T02:00:00.000Z") + "\n", encoding="utf-8")
    return root


def run(root, *args, stdin=None, env=None):
    e = {**os.environ, "ORDERS_DIR": str(root / "orders"), "ORDERS_PROJECTS": str(root / "projects"),
         "XDG_CACHE_HOME": str(root / "cache"), "CLAUDE_CODE_ENTRYPOINT": "cli", **(env or {})}
    return subprocess.run([sys.executable, SCRIPT, *args], input=stdin, capture_output=True, text=True, encoding="utf-8", env=e, timeout=30)


def hook(root, prompt, session="s1", cwd="/home/u", args=(), env=None):
    ev = {"session_id": session, "cwd": cwd, "prompt": prompt}
    out = run(root, "hook", *args, stdin=json.dumps(ev), env=env).stdout
    return json.loads(out or "{}").get("hookSpecificOutput", {}).get("additionalContext", "")


def main():
    root, fails = setup(), []

    def check(name, ok):
        print(("ok   " if ok else "FAIL ") + name)
        if not ok:
            fails.append(name)

    # hook: only on a prompt with a project keyword, once per session
    first = hook(root, "checkout 어떻게 됐어")
    check("keyword prompt injects the orders", "Staging only" in first and "webshop" in first)
    check("injection tells where to add a new order", str(root / "orders/webshop.md") in first)
    check("same session, second prompt is silent", hook(root, "checkout 다시 봐줘") == "")
    check("unrelated prompt is silent", hook(root, "회의록 정리해줘", session="s2") == "")
    check("keyword match ignores case", "Staging only" in hook(root, "check CHECKOUT", session="s3"))
    check("cwd under a project path injects without a keyword",
          "Staging only" in hook(root, "계속 해", session="s4", cwd="/work/webshop/intra"))
    check("a sibling path does not match", hook(root, "계속 해", session="s5", cwd="/work/webshop2") == "")
    check("harness text posed as a prompt is ignored", hook(root, "Stop hook feedback: checkout", session="s6") == "")
    check("headless sdk runs are ignored", hook(root, "checkout", session="s7", env={"CLAUDE_CODE_ENTRYPOINT": "sdk-cli"}) == "")

    # hook: after compaction the projects active in the session come back
    again = hook(root, "", session="s1", args=("--after-compact",))
    check("after compaction the session's projects come back", "Staging only" in again)
    check("after compaction a session with no project is silent", hook(root, "", session="s2", args=("--after-compact",)) == "")

    # hook: an edited orders file is injected again in the same session
    p = root / "orders/webshop.md"
    p.write_text(ORDERS + '3. **Keys stay out of chat.** "키는 붙이지 마" (11-18)\n', encoding="utf-8")
    os.utime(p, (0, 0))                              # an old mtime must not hide the change: the content decides
    check("an edited orders file is injected again", "Keys stay out" in hook(root, "checkout 상태"))

    p.write_text(p.read_text(encoding="utf-8") + '4. **Tests first.** "테스트 먼저 쓰고" (11-18)\n', encoding="utf-8")
    check("an active project is refreshed on a prompt without a keyword", "Tests first" in hook(root, "계속 해"))
    check("after compaction a session inside the project folder gets the orders even with no state",
          "Staging only" in hook(root, "", session="s9", cwd="/work/webshop", args=("--after-compact",)))
    (root / "cache/standing-orders/s10.json").write_text("[]")
    check("a damaged state file does not stop injection", "Staging only" in hook(root, "checkout", session="s10"))

    # hook: one injection never exceeds what Claude Code passes through whole (10,000 characters per hook string)
    big = "---\nproject: bigone\nkeywords: bigone\n---\n" + "".join(f"{i}. **Order {i}.** " + "x" * 600 + "\n" for i in range(1, 31))
    (root / "orders/bigone.md").write_text(big, encoding="utf-8")
    out_big = hook(root, "bigone 봐줘", session="b1")
    check("an oversized orders file is cut under the hook limit and says so", 0 < len(out_big) <= 10000 and "not shown" in out_big)
    two = "---\nproject: {n}\nkeywords: twin\n---\n" + "".join(f"{i}. **Order {i}.** " + "y" * 590 + "\n" for i in range(1, 11))
    (root / "orders/twin-a.md").write_text(two.format(n="twin-a"), encoding="utf-8")
    (root / "orders/twin-b.md").write_text(two.format(n="twin-b"), encoding="utf-8")
    first_two, second_two = hook(root, "twin 작업", session="b2"), hook(root, "twin 계속", session="b2")
    check("projects that do not fit together arrive on consecutive prompts",
          len(first_two) <= 10000 and first_two.count("## STANDING ORDERS: twin-") == 1
          and second_two.count("## STANDING ORDERS: twin-") == 1 and first_two[:40] != second_two[:40])
    check("the prompt that defers a project says so", "twin-" in first_two.split("did not fit")[-1] and "did not fit" in first_two)
    sent_first = "twin-a" if "## STANDING ORDERS: twin-a" in first_two else "twin-b"
    held = "twin-b" if sent_first == "twin-a" else "twin-a"
    (root / f"orders/{sent_first}.md").write_text(two.format(n=sent_first) + "11. **Changed.** \"z\" (today)\n", encoding="utf-8")
    (root / f"orders/{held}.md").write_text(two.format(n=held) + "11. **Also changed.** \"z\" (today)\n", encoding="utf-8")
    third = hook(root, "twin 다시", session="b5")          # fresh session: one goes out, the other is deferred
    fourth_first = "twin-a" if "## STANDING ORDERS: twin-a" in third else "twin-b"
    other = "twin-b" if fourth_first == "twin-a" else "twin-a"
    (root / f"orders/{fourth_first}.md").write_text(two.format(n=fourth_first) + "12. **Again.** \"z\" (today)\n", encoding="utf-8")
    check("a deferred project goes first even when the other one changed again",
          f"## STANDING ORDERS: {other}" in hook(root, "twin 또", session="b5"))
    for name in ("bigone", "twin-a", "twin-b"):
        (root / f"orders/{name}.md").unlink()
    (root / "orders/longname.md").write_text("---\nproject: " + "n" * 12000 + "\nkeywords: longname\n---\n1. **One.** \"x\" (today)\n", encoding="utf-8")
    check("an absurd project name cannot push a message over the limit", 0 < len(hook(root, "longname", session="b6")) <= 10000)
    (root / "orders/longname.md").unlink()
    (root / "orders/oneline.md").write_text("---\nproject: oneline\nkeywords: oneline\n---\n1. **One.** " + "w" * 12000 + "\n", encoding="utf-8")
    one = hook(root, "oneline", session="b7")
    check("a single enormous line is not sent in pieces", 0 < len(one) <= 10000 and "not shown" in one and "wwwww" not in one)
    (root / "orders/oneline.md").unlink()
    for stem in ("dup-1", "dup-2"):
        (root / f"orders/{stem}.md").write_text(f"---\nproject: dup\nkeywords: dupword\n---\n1. **From {stem}.** \"x\" (today)\n", encoding="utf-8")
    both = hook(root, "dupword", session="b8")
    check("two files that claim the same project name are both injected", "From dup-1" in both and "From dup-2" in both)
    check("and neither comes back on the next prompt", hook(root, "dupword", session="b8") == "")
    for stem in ("dup-1", "dup-2"):
        (root / f"orders/{stem}.md").unlink()

    # hook: a pipe or a huge file in the orders folder cannot stall or bloat a prompt
    if hasattr(os, "mkfifo"):                        # not on Windows
        os.mkfifo(root / "orders/pipe.md")
    (root / "orders/huge.md").write_text("---\nproject: huge\nkeywords: checkout\n---\n" + "z" * 400000, encoding="utf-8")
    quick = hook(root, "checkout", session="b3")
    check("a pipe and an oversized file in the orders folder are skipped", "Staging only" in quick and "huge" not in quick)
    (root / "orders/pipe.md").unlink(missing_ok=True)
    (root / "orders/huge.md").unlink()

    # hook: a bad ORDERS_SKIP must not take the hook down, and the transcript commands must say what is wrong
    check("the hook ignores an invalid ORDERS_SKIP", "Staging only" in hook(root, "checkout", session="b4", env={"ORDERS_SKIP": "("}))
    bad = run(root, "scan", "webshop", env={"ORDERS_SKIP": "("})
    check("scan reports an invalid ORDERS_SKIP", bad.returncode != 0 and "ORDERS_SKIP" in bad.stderr)

    # hook: headless runs are skipped unless the user opts in
    check("ORDERS_HEADLESS=1 lets a headless run receive the orders", "Staging only" in hook(
        root, "checkout", session="h1", env={"CLAUDE_CODE_ENTRYPOINT": "sdk-cli", "ORDERS_HEADLESS": "1"}))

    # hook: non-ASCII orders survive a console that is not UTF-8 (Windows code pages, a C locale)
    check("Korean text is written as UTF-8 whatever the console encoding",
          "맡길게" in hook(root, "checkout", session="h2", env={"PYTHONIOENCODING": "ascii"}))

    # hook: Windows working directories match the paths in the header, whichever slash either side uses
    (root / "orders/winproj.md").write_text("---\nproject: winproj\npaths: C:\\work\\shop, D:/code/site\n---\n1. **One.** \"x\" (today)\n",
                                            encoding="utf-8")
    check("a backslash cwd is under a backslash path", "winproj" in hook(root, "go on", session="w1", cwd="C:\\work\\shop\\api"))
    check("a backslash cwd is under a forward-slash path", "winproj" in hook(root, "go on", session="w2", cwd="D:\\code\\site"))
    check("a sibling Windows folder does not match", hook(root, "go on", session="w3", cwd="C:\\work\\shop2") == "")
    (root / "orders/winproj.md").unlink()
    (root / "orders/posix.md").write_text("---\nproject: posix\npaths: /srv/a/b\n---\n1. **One.** \"x\" (today)\n", encoding="utf-8")
    if os.name != "nt":                              # on Windows a backslash is a separator, so this is a subfolder there
        check("a POSIX folder whose name contains a backslash is not confused with a subfolder",
              hook(root, "go on", session="w4", cwd="/srv/a\\b") == "")
    check("a cwd with .. in it is resolved before matching", "posix" in hook(root, "go on", session="w5", cwd="/srv/a/c/../b/src"))
    (root / "orders/posix.md").unlink()

    # hook: inject even when the state cannot be saved (injecting every time beats never injecting)
    blocked = root / "not-a-dir"
    blocked.write_text("x")
    check("an unwritable state folder still injects", "Staging only" in hook(root, "checkout", session="s8", env={"XDG_CACHE_HOME": str(blocked)}))

    # hook: bad input never crashes it
    r = run(root, "hook", stdin="not json")
    check("bad stdin exits 0 with no output", r.returncode == 0 and r.stdout == "")

    check("no hook run left an error trace", not (root / "cache/standing-orders/errors.log").exists())

    # scan: only what the user typed or answered, only after scanned_until, only sessions about the project
    out = run(root, "scan", "webshop").stdout
    check("scan shows a typed prompt", "맡길게" in out)
    check("scan shows the question a short reply answered", "계획을 쓸까요" in out)
    check("scan shows AskUserQuestion answers", "스테이징 먼저" in out and "다음 방향은" in out)
    check("scan skips hook feedback, summaries and injected tags",
          "Stop hook" not in out and "being continued" not in out and "system-reminder" not in out)
    check("scan skips headless sdk prompts", "Create a summary" not in out)
    check("scan keeps a prompt typed with a pasted image", "금요일 배포는 하지 마" in out)
    check("scan pairs a short reply with an assistant text that mentions a record type",
          any("ㅇㅇ 켜" in l and "타이머를 켤까요" in l for l in out.splitlines()))
    check("scan skips prompts before scanned_until", "do not scan" not in out)
    check("scan skips sessions that never touch the project", "오타" not in out)
    check("scan keeps the 12 prompts after a project mention and drops later ones", "딴 얘기 12번" in out and "딴 얘기 13번" not in out)
    check("scan shows the end of a long prompt", "never change live settings" in out)
    check("scan hides a key value", "PKABCDEFGHIJKLMNOPQR" not in out and "api_key" in out and "abc.def.ghi99" not in out)
    leaked = [x for x in ("QUOTEDKEYVALUE", "URLPASSWORD", "QkFTSUNBVVRIVkFMVUU", "eyJzdWIiOiJKV1RCT0RZ", "PEMBODYVALUE",
                          "LETTERSONLYTOKEN", "CLIPPEDSECRET", "QUOTEMIXVALUE", "ESCAPEDTAILVALUE", "USERINFOONLYTOKEN") if x in out]
    check("scan hides quoted, URL, Basic, JWT, PEM, letters-only and clipped secrets" + (f" (leaked: {leaked})" if leaked else ""),
          not leaked)
    check("ordinary words that contain a secret keyword are left alone",
          "passwordless login and a password reset page" in out)
    check("scan survives records with a null message or a non-object line", run(root, "scan", "webshop").returncode == 0)
    lines = out.splitlines()
    first_answer = next(i for i, l in enumerate(lines) if "스테이징 먼저" in l)
    page = run(root, "scan", "webshop", "--limit", str(first_answer + 1)).stdout
    check("a page never splits records that share a timestamp", "하루 한 번" in page and "2026-11-18T01:05:00" in page.splitlines()[-1])
    check("scan refuses a limit below 1", run(root, "scan", "webshop", "--limit", "0").returncode != 0)
    r = run(root, "reach", "webshop")
    check("reach lists matching past prompts with keys hidden",
          "past prompts match webshop" in r.stdout and "[checkout]" in r.stdout and "PKABCDEFGHIJKLMNOPQR" not in r.stdout)
    check("scan marks text already quoted in the orders file", any(l.startswith("=") and "맡길게" in l for l in out.splitlines()))
    check("scan prints the newest timestamp for mark", "2026-11-18T01:10:00" in (out.splitlines() or [""])[-1])

    # mark: the next scan starts after it
    tricky = root / "orders/tricky.md"
    tricky.write_text("---\nproject: tricky\nkeywords: tricky\n---\n1. **One.** \"x\" (today)\nscanned_until: this body line is the user's text\n", encoding="utf-8")
    run(root, "mark", "tricky", "2026-11-18T01:10:00")
    marked = tricky.read_text(encoding="utf-8")
    check("mark never rewrites a body line", "scanned_until: this body line is the user's text" in marked
          and "scanned_until: 2026-11-18T01:10:00\n---" in marked)
    tricky.unlink()
    if hasattr(os, "symlink"):
        real = root / "elsewhere-linked.md"
        real.write_text("---\nproject: linked\nkeywords: linked\n---\n1. **One.** \"x\" (today)\n", encoding="utf-8")
        try:
            os.symlink(real, root / "orders/linked.md")
            run(root, "mark", "linked", "2026-11-18T01:10:00")
            check("mark updates the target of a linked orders file and keeps the link",
                  (root / "orders/linked.md").is_symlink() and "scanned_until: 2026-11-18T01:10:00" in real.read_text(encoding="utf-8"))
            (root / "orders/linked.md").unlink()
        except OSError:
            pass                                     # Windows without the symlink privilege
    check("mark refuses a date that does not exist", run(root, "mark", "webshop", "2026-13-45T00:00:00").returncode != 0)
    run(root, "mark", "webshop", "2026-11-18T01:10:00")
    check("mark stores scanned_until", "scanned_until: 2026-11-18T01:10:00" in p.read_text(encoding="utf-8"))
    r = run(root, "scan", "webshop")
    check("scan after mark says there are no candidates", r.returncode == 0 and "no new candidates" in r.stdout)

    # check: a plan or brief has one line per order
    brief = root / "brief.md"
    brief.write_text("order 1: 스테이징에만 배포한다\norder 3: 키는 파일에서만 읽는다\n", encoding="utf-8")
    r = run(root, "check", "webshop", str(brief))
    check("check fails and names the missing order", r.returncode == 1 and "2" in r.stdout and "No push" in r.stdout)
    brief.write_text("order 1: a\norder 2: n/a, push 없음\norder 3: b\n- order 4: 테스트 포함\n", encoding="utf-8")
    check("check passes when every order has a line", run(root, "check", "webshop", str(brief)).returncode == 0)

    # reset: /clear wipes the context, so the session must be able to get its orders again
    check("before a reset the session is silent", hook(root, "checkout", session="s1") == "")
    run(root, "hook", "--reset", stdin=json.dumps({"session_id": "s1"}))
    check("after a reset the orders are injected again", "Staging only" in hook(root, "checkout", session="s1"))

    # prune: state files of sessions long gone are removed when new state is written
    old = root / "cache/standing-orders/ancient.json"
    old.write_text("{}")
    os.utime(old, (0, 0))
    hook(root, "checkout", session="s11")
    check("stale session state is pruned", not old.exists() and (root / "cache/standing-orders/s11.json").exists())

    # ORDERS_SKIP: transcripts whose path matches are never read
    skipped = run(root, "reach", "webshop", env={"ORDERS_SKIP": "home-u"}).stdout
    check("ORDERS_SKIP keeps matching transcripts out of reach", "0 of 0" in skipped)
    check("ORDERS_SKIP keeps matching transcripts out of scan",
          "no new candidates" in run(root, "scan", "webshop", env={"ORDERS_SKIP": "home-u"}).stdout)

    # CLAUDE_CONFIG_DIR moves the default folders
    cfg = root / "cfg/orders"
    cfg.mkdir(parents=True)
    (cfg / "elsewhere.md").write_text("---\nproject: elsewhere\nkeywords: elsewhere\n---\n1. **One.** \"x\" (today)\n", encoding="utf-8")
    check("CLAUDE_CONFIG_DIR is honoured when ORDERS_DIR is not set",
          "elsewhere: 1 orders" in run(root, "list", env={"ORDERS_DIR": "", "CLAUDE_CONFIG_DIR": str(root / "cfg")}).stdout)

    # new: start an orders file without writing the header by hand
    r = run(root, "new", "docs-site", "--keywords", "docs site, 문서 사이트", "--paths", "/work/docs")
    made = root / "orders/docs-site.md"
    check("new creates an orders file with the header", r.returncode == 0 and made.exists()
          and "keywords: docs site, 문서 사이트" in made.read_text(encoding="utf-8"))
    check("new refuses to overwrite", run(root, "new", "docs-site", "--keywords", "x").returncode != 0)
    check("a new file is injected on its keyword", "docs-site" in hook(root, "문서 사이트 고쳐줘", session="s12"))
    check("new refuses a name that is not a plain file name", run(root, "new", "../evil", "--keywords", "x").returncode != 0)
    check("version prints a number", re.match(r"\d+\.\d+\.\d+", run(root, "--version").stdout or ""))

    # list
    check("list shows the project and its order count", "webshop: 4 orders" in run(root, "list").stdout)

    print(f"\n{len(fails)} failed" if fails else "\nall passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

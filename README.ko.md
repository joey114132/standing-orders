# standing-orders

같은 말을 두 번 하지 않게 해 주는 Claude Code plugin 이다.

[English](README.md)

월요일에 Claude 에게 "배포는 staging 까지만"이라고 말했다. 목요일에 새 세션을 열거나 대화가 압축된 뒤, Claude 는
production 배포 계획을 쓰고 사용자는 "아까 말했잖아"를 친다. 계획을 쓰는 순간에 그 지시가 문맥에서 빠져 있었기
때문이다.

standing-orders 는 프로젝트에 대해 정한 것을 사용자가 한 말 그대로 짧은 파일 하나에 모아 둔다. 그리고 그
프로젝트 이야기가 나올 때와 대화가 압축된 직후에 hook 이 그 파일을 Claude 앞에 다시 놓는다.

## 무엇이 달라지나

프로젝트를 언급하면 Claude 는 프롬프트를 읽기 전에 아래와 같은 블록을 받는다(여기서는 줄여서 보였다).

```text
## STANDING ORDERS: webshop (5 orders, the user's words; newest wins)
File: ~/.claude/orders/webshop.md. Before a plan, a brief to a worker, a design, a schedule or a claim about
what is allowed in this project, write one line per order the work touches: "order N: how this satisfies it". ...

1. **Staging only.** "you can deploy to staging yourself, never to production" (2026-03-02).
   Reading: a production deploy is prepared and handed over, not run.
2. **Tests first.** "no fix without a failing test first" (2026-03-02).
4. **Guest checkout must keep working.** "don't make people sign up to pay" (2026-03-09).
   State 2026-03-20: the address-book change still requires an account. OPEN.
```

구성은 세 가지다.

- **hook** 은 위 블록을 넣는다.
- **skill** 은 Claude 가 블록을 쓰는 방법을 정한다. 계획 전에 지시마다 한 줄로 답하고 새 결정은 그 자리에서 파일에
  적으며, `OPEN` 으로 남은 지시는 보고할 때마다 알린다.
- **`orders.py`** 는 파일을 처음 만들 때 쓴다. 지난 대화 기록에서 사용자가 그 프로젝트에 대해 실제로 친 말을
  뽑아 준다. 자기가 무엇을 정했는지 기억해 내지 않아도 된다.

## 설치

Claude Code 안에서 설치한다.

```text
/plugin marketplace add joey114132/standing-orders
/plugin install standing-orders@standing-orders
```

셸에서 설치할 수도 있다.

```bash
claude plugin marketplace add joey114132/standing-orders
claude plugin install standing-orders@standing-orders
```

설치한 뒤 Claude Code 를 다시 시작하거나 `/reload-plugins` 를 실행한다. Claude Code 가 보는 PATH 에 `python3`(3.9
이상)가 있어야 하고 다른 의존성은 없다. Linux 와 Claude Code 2.1.328, 2.1.329 에서 만들고 시험했다. 테스트는 CI 에서
macOS 와 Windows 로도 돌린다. Windows 에서는 hook 이 Git Bash 로 돈다. Git Bash 가 깔려 있으면 Claude Code 가 hook
명령에 그것을 쓴다. 다만 실제 Windows 설치본에서 hook 배선까지 돌려 보지는 못했다. plugin 없이 설치하는 방법은
[영문 README](README.md#install) 에 있다.

## 2분 만에 써 보기

1. 아무 세션에서 Claude 에게 결정을 말하고 저장하라고 한다.

   > webshop 프로젝트는 staging 까지만 배포하고 production 에는 절대 배포하지 마. 이걸 standing order 로 저장해. 낱말은 "webshop", "checkout".

   Claude 가 사용자의 문장을 날짜와 함께 인용해서 `~/.claude/orders/webshop.md` 를 만든다.
   `/standing-orders:standing-orders` 로 skill 을 직접 부를 수도 있다.
2. 새 세션을 열고 낱말이 들어간 프롬프트를 친다. 예를 들면 "checkout 합계가 1센트 틀려"이다.
3. "이 프로젝트의 standing order 가 뭐야?"라고 묻는다. Claude 는 파일을 열지 않고 주입된 블록을 보고 답한다.

## 지난 대화에서 프로젝트 파일 만들기

지시의 대부분은 이미 예전 대화에서 내렸을 것이다. 그것을 모으려면 Claude 에게 시킨다.

> 이 프로젝트의 standing-orders 파일을 만들어 줘. 지난 세션에서 내가 정한 것을 찾아서, 저장하기 전에 목록을 보여 줘.

직접 하려면 이 저장소를 clone 한 뒤 아래 순서로 한다.

```bash
alias orders='python3 /path/to/standing-orders/skills/standing-orders/orders.py'

orders new webshop --keywords "webshop, checkout, 결제" --paths ~/code/webshop
orders reach webshop     # 이 낱말에 걸리는 지난 프롬프트 전부. 다른 일에 걸리는 낱말은 뺀다
orders scan webshop      # 이 프로젝트에 대해 치거나 고른 말. 오래된 것부터
$EDITOR ~/.claude/orders/webshop.md
orders mark webshop 2026-03-20T09:41:07   # scan 이 찍어 준 시각. 다음 scan 은 그 뒤부터 본다
```

`scan` 은 프로젝트를 언급한 세션만 읽는다. 그 안에서 프로젝트를 언급한 프롬프트와 그 뒤 12개를 남기고, 오래된
것부터 150개씩 보여 준다. 어디까지 봤는지는 `mark` 로 옮긴다. `=` 는 그 말이 이미 파일의 인용문 안에 있다는
표시인데, 부분 문자열로 비교한 것이라 참고만 한다. `*` 는 지시처럼 읽히는 말이다. "응", "B" 같은 짧은 답은 바로
앞 assistant 메시지의 끝부분과 함께 나온다. 질문 창에서 고른 답도 질문과 함께 나온다. `reach` 는 600자 이하의
프롬프트를 중복 없이 한 번씩 보여 준다.

완성된 파일은 [examples/webshop.md](examples/webshop.md) 처럼 생겼다. 지시 하나는 굵게 쓴 짧은 제목, 따옴표 안의
사용자 말, 날짜로 이루어진다. 인용을 넘어서는 해석은 `Reading:` 뒤에 적는다. 그래야 사용자의 결정과 Claude 의
해석이 구분된다. 시켰는데 아직 없는 일은 `OPEN` 으로 표시한다.

## 명령

| 명령 | 하는 일 |
| --- | --- |
| `orders.py new <project> --keywords a,b [--paths /dir]` | `~/.claude/orders/<project>.md` 를 머리말과 함께 만든다 |
| `orders.py list` | 프로젝트, 지시 수, 낱말, 경로를 보여 준다 |
| `orders.py reach <project>` | 낱말에 걸리는 지난 프롬프트를 보여 준다 |
| `orders.py scan <project> [--limit N]` | 마지막 mark 뒤의 후보를 보여 준다 |
| `orders.py mark <project> <timestamp>` | 대화 기록을 어디까지 읽었는지 적는다(UTC) |
| `orders.py check <project> <file>` | 파일에 지시마다 `order N:` 줄이 없으면 exit 1 로 끝난다. 줄이 있는지만 보고 내용은 보지 않는다 |
| `orders.py hook [--after-compact \| --reset]` | hook 진입점이다. 이벤트를 stdin 으로 받는다 |

`check` 는 세션 밖으로 나가는 계획과 작업 지시에 쓴다. 새 문맥으로 시작하는 subagent 는 주입된 블록을 받지
못하므로 작업 지시에 지시를 직접 실어야 한다. 빠진 지시는 `check` 가 찾는다.

## 언제 주입되나

프롬프트에 프로젝트 낱말이 들어 있거나 세션의 작업 폴더가 프로젝트 경로 아래에 있으면 그 파일을 넣는다. 낱말은
소문자로 바꿔 부분 문자열로 비교한다. 주입은 세션당 한 번이다. 한 번 들어간 프로젝트는 파일 내용이 바뀌었을
때와 압축이 끝났을 때 다시 넣는다. `/clear` 를 하면 그 세션의 프로젝트를 잊고 다음에 걸릴 때 다시 넣는다.
프로젝트를 언급하지 않는 다른 세션에는 넣지 않으므로 무관한 작업에서 토큰이 들지 않는다.

Claude Code 는 hook 메시지를 10,000자까지만 통째로 넘긴다. 그래서 지시 파일은 9,000자 안쪽으로 둔다. 더 긴 파일은
줄 경계에서 자르고 나머지를 읽으라는 안내를 붙인다. 두 프로젝트가 한꺼번에 걸렸는데 같이 들어가지 않으면 두
번째는 다음 프롬프트에 넣는다.

부분 문자열로 비교하므로 낱말은 그 프로젝트 밖에서 드문 것으로 고른다. 제품 이름은 잘 맞는다. `plan`, `api`, 두
글자 약어는 무관한 세션에도 파일을 넣게 된다. `reach` 로 미리 확인할 수 있다.

hook 은 지시를 문맥에 넣을 뿐이고 모델이 따르도록 강제하지는 못한다. skill 은 지시마다 눈에 보이는 한 줄을 쓰게
해서 그 틈을 줄이고 `check` 는 빠진 줄을 잡아낸다. 다만 적힌 줄이 틀릴 수는 있다.

## 개인정보와 신뢰

이 plugin 은 네트워크를 쓰지 않고 사용 기록도 보내지 않는다. 지시 파일은 `~/.claude/orders` 에, 세션별 상태는
`~/.cache/standing-orders` 에 있다.

지시 파일은 Claude 의 문맥에 들어가므로 그 글은 대화의 나머지와 함께 모델 제공자에게 간다. `CLAUDE.md` 와 같다.
Claude 에게 `scan` 이나 `reach` 를 시켰을 때 나오는 출력도 마찬가지다. 지시 파일에는 비밀값을 넣지 않는다. `list`,
`check`, hook 은 파일 내용을 그대로 출력한다.

지시 파일은 Claude 에게 주는 지시이기도 하다. 직접 썼거나 검토한 파일만 지시 폴더에 두고, 남이 고칠 수 있는
파일로 링크하지 않는다.

`scan` 과 `reach` 는 `~/.claude/projects` 아래의 Claude Code 대화 기록을 읽어 사용자가 친 말을 출력한다. 비밀번호,
키와 token 대입문, bearer 와 basic 헤더, URL 안의 계정 정보, JWT, PEM 블록, 긴 token 모양 문자열은 가린다. 다만
정규식으로 완전히 막을 수는 없으니 출력을 다른 곳에 붙이기 전에 한 번 읽어 본다. 일부 대화 기록을 아예 읽지
않게 하려면 `ORDERS_SKIP` 에 정규식을 넣는다. 이 정규식은 대화 기록의 경로와 비교한다. Claude Code 는 작업 폴더
경로의 `/` 를 `-` 로 바꿔 대화 기록 폴더 이름을 짓는다. 그래서 `ORDERS_SKIP='-clients-|-personal'` 은 `clients` 나
`personal` 폴더 아래에서 시작한 세션을 건너뛴다. headless 실행(`claude -p` 와 다른 SDK 진입점)은 `scan` 과 `reach` 가 읽지 않는다.
hook 도 `ORDERS_HEADLESS=1` 이 아니면 건너뛴다.

대화 기록 형식은 Claude Code 내부 형식이라 바뀔 수 있다. 바뀌면 `scan` 과 `reach` 가 찾는 양이 줄어든다. hook 은
대화 기록을 읽지 않으므로 그대로 동작한다.

## 설정

| 변수 | 기본값 | 뜻 |
| --- | --- | --- |
| `ORDERS_DIR` | `~/.claude/orders` | 지시 파일 위치 |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | 위아래 두 변수가 없을 때 두 기본값을 함께 옮긴다 |
| `ORDERS_PROJECTS` | `~/.claude/projects` | Claude Code 대화 기록 위치 |
| `ORDERS_SKIP` | 없음 | 경로가 이 정규식에 걸리는 대화 기록은 읽지 않는다 |
| `ORDERS_HEADLESS` | 없음 | `1` 로 두면 headless `claude -p` 실행에도 주입한다 |
| `XDG_CACHE_HOME` | `~/.cache` | 세션별 상태 폴더의 상위 폴더 |

## 개발

```bash
python3 tests/test_orders.py        # 검사 64개, 의존성 없음
claude plugin validate . --strict
```

버그를 알릴 때는 `orders.py --version` 출력과 Claude Code 버전, 문제가 드러나는 가장 작은 지시 파일을 같이 보내
주면 좋다. hook 실행이 실패하면 프롬프트를 막지 않도록 조용히 넘어가고 `~/.cache/standing-orders/errors.log` 에
기록을 남기려고 시도한다.

## 라이선스

MIT

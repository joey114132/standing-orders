---
project: webshop
keywords: webshop, checkout, payments
paths: /home/me/code/webshop
---
# webshop standing orders (the user's words; newest wins)

Text after "Reading:" is the assistant's interpretation, not the user's words. State lines are dated; check the repo before repeating them.

1. **Staging only.** "you can deploy to staging yourself, never to production" (2026-03-02). Reading: a production deploy is prepared and handed over, not run.
2. **Tests first.** "no fix without a failing test first" (2026-03-02).
3. **Money stays in integer cents.** "we got burned by floats once, cents everywhere" (2026-03-05). Reading: this covers new columns, API fields and fixtures.
4. **Guest checkout must keep working.** "don't make people sign up to pay" (2026-03-09). State 2026-03-20: the address-book change still requires an account. OPEN.
5. **Routine choices are yours.** "just pick, don't ask me about naming" (2026-03-11). Still asked: anything that touches production, pricing or user data.

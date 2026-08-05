# Reflection

Fifteen days, one AI-assisted lending marketplace, 169 backend tests and 16 frontend ones.
This document is built from the correction entries in [`prompts.md`](../prompts.md) rather
than from recollection, because the entries were written at the time and recollection is
generous.

The argument, in one line: **every failure below needed a different kind of verification to
catch it, and the kinds get progressively harder to run.** Reading output caught the first.
Counting runs caught the second. Deleting a line of code caught the third. Only changing the
environment caught the fourth. That escalation is the finding — not the individual bugs.

---

## What AI did well

Briefly, because this is the part that is easy to claim and hard to make interesting.

- **Scaffolding speed.** Django apps, DRF viewsets, serializers, routers and the React shell
  came up in hours rather than days. Nothing here is novel code, and none of it was worth
  hand-typing.
- **Test generation volume.** 169 backend tests exist because generating the twentieth
  variation of a permission assertion costs nothing. Left to hand-writing, the suite would
  have stopped at the interesting cases and skipped the boring ones — which is precisely
  backwards, since the boring ones are what regress.
- **Explaining unfamiliar surfaces.** MCP's in-memory transport, `TransactionTestCase`
  versus `TestCase` for thread-dispatched tools, and DRF's permission ordering were all
  faster to learn by asking than by reading.
- **The 65× test-suite speedup** ([entry 58](../prompts.md)) came from a model noticing that
  `make_user` was paying 1,200,000 PBKDF2 iterations per fixture. 647 seconds to 10, from
  four lines. I had assumed the slowness was accumulated volume and would not have looked.

The pattern: AI was strongest where the work was **voluminous and well-specified**, and
weakest — as below — where the specification itself was the defect.

---

## Where it failed, in four escalating cases

### 1. Resale pricing — the prompt was wrong, not the parser

All three first-run extractions were wrong in the same direction: **$25 for a blender, $45
for a lamp, $18 for a grinder.** Those are resale values. This is a *lending* marketplace.

The cause was one phrase in the prompt's own first line — *"a **second-hand item**"* — with
`suggested_price: a number in USD`. Nothing anywhere said the price meant a daily rate. The
model priced the object, because that is what it had been asked to do.

Three lines rewritten (the framing, the price field, the description scope). Same model,
same images:

| Item | Before | After |
|---|---|---|
| Magic Bullet blender | $25.00 | $3.00 |
| Desk lamp | $45.00 | $5.00 |
| Angle grinder | $18.00 | $5.00 |

`category` and `condition` came back identical across both runs — the edit moved the field
it targeted and left the rest stable.

**Why this one is first:** it was catchable by reading three outputs. Wrong the same way
three times out of three is systematic, not noise. No tooling required, only the discipline
to look at values instead of status codes.

### 2. Ranker padding — fluent, specific, and wrong

Asked for something to *"cut through some metal pipes"*, with nothing in the candidate set
that cuts metal, the ranker returned a drill first (*"likely usable for cutting"*) and an
**extension cord** second at score 0.5, justified as *"not ideal for cutting metal but is a
tool-like item, cheap and nearby."*

The danger is the register. Vague praise reads as weak and invites scrutiny; a confident,
concrete, false rationale reads as competent until somebody checks.

The prompt already said *"Leave out listings that clearly don't fit rather than padding the
list."* It padded anyway. The fix was not a stronger prohibition but a change of status:

> Returning an empty matches array is the **CORRECT** answer when nothing genuinely does the
> job.

Permitted was not enough. It had to be named as *right*.

**The extension cord appeared in 1 of 1 runs before, and 0 of 4 runs after.**

**Why this escalates:** reading one output could not have caught it, because the same prompt
padded on the metal-pipes query and correctly returned nothing on the barbecue query. **An
instruction being followed sometimes looks like an instruction that works.** Catching it
needed repeated runs of the *same* input — and the corollary bit me immediately, in
[entry 50](../prompts.md), where I called a regression off a single run and was wrong.

### 3. The call-site finding — my process, not the model's output

Eleven tests covered `notify_listings_matched`: guards, cap, collapse window, payload shape,
query count. All green.

**Every one of them passed with the call deleted from `rank_candidates`.**

A perfect, fully-tested, completely unreachable service. The tests called the function
directly, so they proved the function worked and said nothing about whether anything used
it. **Coverage measures reach, never dependence.** It answers "was this line executed",
which is not the question "does anything rely on this line being here".

The fix is a test that exercises the *call site* rather than the function: run a real
ranking, assert a notification appeared. Deleting that one line now produces exactly one
failure out of 62, with the service suite entirely green — the clearest possible statement
that code works and is never reached.

A later audit removed seven seams one at a time to check the rest. It found nothing, which
was the point of running it.

**Why this is the strongest:** the first two are the model's output being wrong. This one is
my own testing discipline being wrong, and no amount of green would ever have told me. It
needed an act — deliberately deleting a line and re-running — that nothing prompts you to
perform.

### 4. The dependency file — only a different environment could see it

`docker compose up` on a clean image found four things that 169 passing tests and a working
dev server had been hiding. The sharpest: **`anthropic` and `openai` were installed in the
local virtualenv and had never been added to `requirements.txt`.** The README claimed this
was deliberate — keeping a stub-only clone dependency-free. It read as a decision. It was an
omission that had been rationalised into one.

Nothing caught it because both imports are **lazy**, sitting inside the provider's
`__init__`. On `stub` — the default, and what the entire suite runs on — neither line ever
executes. The app boots, every test passes, and the failure waits for the exact moment
someone sets `EXTRACTION_PROVIDER=anthropic` to demonstrate a live LLM call.

The same afternoon also produced: `DEBUG=False` silently unmounting the media route so every
photo renders broken while nothing errors; a seed that was *idempotent and wrong*, producing
1 listing instead of 48 across three identical runs; `pywin32` hard-failing `pip install` on
Linux; and a Django 5.2 shell banner corrupting the "is the database empty" check so the
seed would never run at all.

**The counterpart, and the honest half of the supply-chain lesson.** A separate review
flagged four more pins — `httpcore2`, `httpx2`, `mcp-types`, `python-discovery` — as
suspicious, sitting alongside the ordinary `httpcore` / `httpx` / `mcp`. The `2` suffixes
read exactly like typosquats. **They are legitimate.** `pipdeptree --reverse` and
`pip show mcp` both confirm it from opposite directions: `mcp 2.0.0` requires `httpx2` and
`mcp-types` directly, and `virtualenv 21.7` requires `python-discovery`.

That outcome is the lesson, not a footnote to it. **An unexplained pin costs the next
reader ten minutes whether or not it turns out to be malicious**, and a dependency file
nobody can read is a supply-chain problem before anything hostile is involved. All four now
carry an inline comment. The check was worth running precisely because it could have gone
either way, and "verified legitimate" is a different state from "never looked".

**Why this escalates furthest:** the container was the first environment that had not
inherited six weeks of accumulated local state — different Python, different paths, no
virtualenv, no stray `.env`, `DEBUG` genuinely off. Every assumption the project had
quietly absorbed had to be declared or discovered. It behaves like a test suite for the
things test suites cannot see, and nothing short of a new environment would have run it.

---

## Where I corrected myself

Three entries where the log records its own errors. They are here because a reflection
document that only reports its author's successes is not evidence of anything.

**The coverage omissions I could have defended.** I excluded three hand-run scripts from
`.coveragerc` — developer tooling with no importable behaviour that would sit at 0% forever.
Every clause of that reasoning is true. I put them back anyway, at a cost of **eleven
points** (75% → 64%), because the reasoning *needed making*. "We omitted migrations,
settings, entrypoints, tests and the venv" is a sentence that ends; anything past it invites
the question of what else was excluded. Buying eleven points with an argument you have to
make is a bad trade when anyone can open the file and read the list.

**Entry 59 asserted tests that were never committed.** It claimed `mergeMessages` had twelve
assertions run under plain `node`. I had run them in a scratch file and committed nothing.
That claim sat in the documentation for two days describing tests that did not exist. There
are now sixteen frontend tests via `node:test`, including the one that matters most —
*someone else saying the same thing must not confirm my pending message*.

**Week 1's three component tests were never in this repo at all.** Not lost to refactoring,
as I half-expected: nothing test-shaped appears anywhere in the git history. The honest
position is that frontend testing was scoped to pure logic in favour of API coverage, which
is defensible. Silence about it would not have been.

The generalisation is uncomfortable and worth stating plainly. **Every other claim in this
project has something that fails when it goes wrong** — a broken import fails a test, a
wrong status code fails the permission sweep, a missing `lender_id` fails the journey test.
A stale document fails nothing, ever, so it rots at exactly the rate nobody is looking. Two
documentation defects turned up in two days, both found by reading rather than running.

---

## Lessons

- **Tests written alongside stay written; tests deferred stay deferred.** `messaging/views.py`
  and `notifications/views.py` hit 100% because they got HTTP tests when they were built;
  `matching/views.py` sat at 23% — the AI feature the whole demo rests on — because its
  tests were always going to happen later.
- **A constant that can be wrong is worse than a rule that cannot.** The hardcoded seed
  image path pointed at a file nothing ever wrote, and rendered 43 broken thumbnails on
  every clone; generating the image at seed time removed the class of bug, not the instance.
- **When two failure modes are not symmetric, fail toward the quiet one.** A bell that says
  "You have a new notification" for an unknown enum value beats a bell that 500s because
  someone added one.
- **Coverage is reach, not dependence.** It answers whether a line ran, never whether
  anything depends on it running — so the test that matters exercises the call site, and
  fails for exactly one reason.
- **An instruction followed sometimes is indistinguishable from one that works.** Single
  runs establish nothing about non-deterministic systems, in either direction.

---

## Known limitations

Named here because naming them is worth more than any of them costs.

- **Two dead fields.** `MatchQuery.keywords` and `MatchQuery.notes` are produced by the
  model, serialised into the rank prompt, and read by no code anywhere. They reach the
  ranker as JSON text and nothing branches on them. The two models also tokenise differently
  — `['cordless', 'drill']` versus `['cordless drill']` — which is harmless only for as long
  as `keywords` stays unread. The moment it drives filtering, it becomes a bug that
  reproduces on one provider and not the other.
- **An unreachable enum branch.** `Notification.Type.BOOKMARK_UPDATE` is declared and
  rendered by the serializer, but no code path ever writes a row with it. `NEW_MATCH` was in
  the same state until the second notification trigger was built; this one still is.
- **`DEFAULT_PERMISSION_CLASSES` is unset.** DRF therefore defaults to `AllowAny`, and every
  endpoint's protection depends on its own view declaring it. The mitigation is a
  cross-app permission sweep — `test_every_protected_endpoint_rejects_an_anonymous_caller`
  — which lists every protected route in one place and fails if any of them stops refusing
  anonymous callers. That is a backstop, not a default, and the setting is the better fix.
- **No frontend component tests.** Sixteen tests cover pure logic (`mergeMessages`,
  `notificationKinds`) under `node:test` with no framework. Rendering, routing and
  interaction are covered only by the API tests beneath them and by manual walkthrough.
  Deliberate, in favour of API coverage — but it is a gap, not a design.
- **The cache read and write are diagnostically indistinguishable.** Removing either
  produces identical failures — the same two tests, the same messages. Both are caught, so
  it is not a coverage gap; it is a *diagnostic* one, and it makes the case for table-driven
  tests better than an argument could. The trust rules name the broken rule through
  `subTest` labels; the cache makes you bisect.
- **SQLite, single writer, one gunicorn worker.** The notification collapse filter depends
  on SQLite's `json_extract()` semantics, and the collapse rule is an `exists()` followed by
  a `create()` — simultaneous writes could both slip through. The real fix is a partial
  unique index, which Postgres has and SQLite does not. At one writer it cannot happen.
  Naming the concurrency assumption is what turns a shortcut into a scoped decision.

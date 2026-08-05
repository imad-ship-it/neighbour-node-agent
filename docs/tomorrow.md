# Tomorrow — bug fixes only

Written at the end of the containerisation day. Everything here was noticed
while doing something else and deliberately not fixed, so that the morning is
a short list rather than an exploration.

Ordered by what a person watching the demo would notice first.

---

## ~~1. Most seeded listings show a broken thumbnail~~ — DONE

Fixed the same day. `seed_data` used to set every image to the hardcoded path
`listings/2026/07/drill.jpg`, which nothing ever wrote — 43 of 51 rows rendered
as broken thumbnails on every clone and in every container.

`apps/core/services/listing_images.py` now draws a card per listing with Pillow
(item name, category, category colour) and saves it through the `ImageField`, so
real bytes land on the media volume wherever the seed runs. No binary in git, no
network call, works offline on a fresh `docker compose up`.

Verified from a clean volume: 48 listings, 47 with images, **0 broken** — every
one fetched through nginx off the media volume and checked for a 200. The single
row without an image is deliberate: the "Folding Camping Table" fixture exists so
the `no_photo` trust rule has something to fire on.

**Upgrade path if you want real photos later.** Drop `<noun>.jpg` into
`backend/seed_images/` — `drill.jpg`, `kayak.jpg`, `bike.jpg` — and it is used in
place of the drawn card automatically. No code change. Use CC0 sources
(Unsplash, Pexels) if the repo stays public.

---

## 2. Confirm the two scroll fixes in the production build  ← needs a browser

**What.** Yesterday's two scroll fixes — long threads landing at the newest
message on open, and the related scroll behaviour — have **not** been verified
against the containerised build. Every check run today was HTTP-level.

**Why it can't be ticked off from the API.** Minification, a real static server,
and different asset timing can all change when layout settles relative to when a
scroll effect fires. That class of bug does not appear in a status code.

**How.** `docker compose up -d`, open <http://localhost:8080>, log in as
`demo-borrower` / `demo-pass-1234`, open the thread seeded by the check script,
and confirm it lands at the newest message on open and after a reload. Ten
minutes, but it does need eyes on a screen.

---

## 3. `CACHE_TTL` is 24h and the demo window may be wider

**What.** `apps/listings/services.py:16` — `CACHE_TTL = 60 * 60 * 24`.

**Why it matters.** Redis persistence means a warmed cache survives restarts,
which is the property that was wanted. It does not survive the TTL. A cache
warmed Thursday afternoon is cold by Friday afternoon, and the warming would
have to be redone on the morning.

**Fix.** Make it configurable — `CACHE_TTL = config("CACHE_TTL", default=86400,
cast=int)` — and set it to 72h in compose for the demo period. Two lines.

---

## 4. Pre-existing lint error in `AuthContext.jsx`

```
src/context/AuthContext.jsx
  84:17  error  Fast refresh only works when a file only exports components
         react-refresh/only-export-components
```

`npm run lint` exits non-zero because of it. Pre-existing — confirmed unrelated
to any change made today. It is a dev-experience rule, not a correctness one, so
it breaks nothing at runtime, but it means lint cannot be used as a gate until
it is resolved. Fix by moving the non-component export into its own module.

---

## ~~5. Suspicious pins in `requirements.txt`~~ — CHECKED, they are real

`httpcore2`, `httpx2`, `mcp-types`, `python-discovery` looked like they arrived
from a bad resolve, sitting alongside the normal `httpcore` / `httpx` / `mcp`.
They are not. `pipdeptree --reverse` in the container:

```
httpcore2==2.9.1
└── httpx2==2.9.1 [requires: httpcore2==2.9.1]
    └── mcp==2.0.0 [requires: httpx2>=2.5.0]
mcp-types==2.0.0
└── mcp==2.0.0 [requires: mcp-types==2.0.0]
python-discovery==1.5.0
└── virtualenv==21.7.0 [requires: python-discovery>=1.4.2]
    └── pre_commit==4.6.0 [requires: virtualenv>=20.10.0]
```

`pip show mcp` confirms it from the other direction — `httpx2` and `mcp-types`
are in its own `Requires:` list. The `2` suffixes read like typosquats and are
not: `httpx2` is what `mcp` 2.0.0 actually depends on.

Dropping the four lines would not have failed the build — pip would reinstall
them transitively — but it would have lost the pins in a file that pins
everything else. They now carry an inline comment each, so the next person
doesn't spend the same ten minutes.

---

## Not bugs — deliberate, already written up

Listed so they don't get "fixed" by accident:

- **SQLite in production, one gunicorn worker.** Reasoning in
  `docs/decisions.md`. Redis removed the cache objection to multiple workers;
  the worker count stayed at one for the SQLite write path.
- **The open `react-router` advisory.** GHSA-qwww-vcr4-c8h2 describes an
  RSC-mode issue in a mode this SPA does not run. Four independent checks in
  `docs/decisions.md`. `npm audit fix --force` would *downgrade* to 7.11.0 to
  escape a bug that cannot be reached — do not run it.
- **`schema.yml` is gitignored.** A committed copy is a second description of
  the API that nothing keeps honest.

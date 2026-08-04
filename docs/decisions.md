# Decisions taken under deadline

Judgement calls where the reasoning matters more than the outcome, written when
they were made rather than reconstructed afterwards.

---

## SQLite in production, deliberately

**The decision.** The deployed container runs SQLite, not Postgres. Single
node, database on a mounted volume, WAL enabled, one worker process.

**Why, honestly.** Postgres was planned and cancelled under time pressure. That
is the real reason, and it is worth stating plainly rather than dressed up —
but it is also a defensible outcome for what this actually is: a single-node
deployment with one writer, a few dozen listings, and no concurrent write load
worth the name. SQLite with WAL handles that comfortably. The cost of the
migration was a day; the benefit at this scale was close to zero.

What makes it a judgement call rather than a shortcut is knowing exactly what
would have to change, and having checked rather than assumed.

**The migration path, and the two things that would break.**

1. **The notification collapse filter.** `notify_new_message` suppresses a
   duplicate bell entry by filtering on `payload__conversation_id`, a JSONField
   key lookup. On SQLite that compiles to `json_extract()`; on Postgres to
   `jsonb` operators. The semantics are close but not identical, and the rule
   depends on them exactly — matching too loosely silences unrelated threads,
   matching too strictly lights the bell on every message.

   Verified on SQLite: `42` and `"42"` do **not** cross-match, and a row missing
   the key is not matched. The service always writes an integer, which is what
   makes the lookup safe today. This is the first thing to re-test on Postgres.

2. **The cache backend under multiple workers.** Extraction results are cached
   by SHA-256 of the image bytes plus description, in Django's default
   `LocMemCache` — which is **per-process**. One worker makes that a real cache.
   Two workers make it two half-caches with a 50% miss rate, each miss costing a
   paid vision call. Moving to more than one worker requires Redis or
   `DatabaseCache` first; this is not optional, and it fails as a bill rather
   than as an error.

   The same per-process behaviour is why the test suite clears the cache between
   cases — see `ExtractionCacheTests`.

   **Resolved when the app was containerised.** Redis is now a service in
   `docker-compose.yml` and `CACHES` points at it whenever `REDIS_URL` is set,
   falling back to `LocMemCache` when it isn't so a bare `runserver` still works
   with nothing installed. This constraint no longer blocks a second worker —
   though the worker count stayed at one for a different reason, below.

**A third, smaller one.** The notification collapse rule is an `exists()`
followed by a `create()`, so two genuinely simultaneous messages could both pass
it and produce duplicate bell entries. The proper fix is a partial unique index
— `(user, type, conversation_id) WHERE NOT is_read` — which **Postgres supports
and SQLite does not**. At one writer this cannot happen; it becomes real the
moment concurrency does.

**What was written to protect the move.** Two portability tests were planned.
One pinning the JSON lookup was written and then **deleted**: the behaviour
underneath it is already asserted by eleven notifier tests, and once the
migration was cancelled it was duplicate coverage justified by an event that is
no longer happening. The other — numeric precision on `distance_km` and the
daily rate — was kept, and rewritten to assert through the API response, because
it was never really about Postgres. Those are numbers a person reads off a match
card.

**If asked "why not Postgres?"** — because the workload is one writer on one
node, the migration is a day, and the two things that would have to change are
identified and written down. Not because it didn't occur to us.

---

## One gunicorn worker, with threads for concurrency

**The decision.** `GUNICORN_WORKERS=1`, `--threads 4`. Set in
`docker-compose.yml` and defaulted in `backend/entrypoint.sh`.

**Why one.** With a single process there is exactly one writer to the SQLite
file, so the write path is uncontended by construction rather than by timing.
WAL plus a 5s `busy_timeout` is configured regardless — see the `OPTIONS` block
in `settings.py` — but with one worker neither is ever load-bearing. That is the
property worth having in a live demo: the failure mode isn't made unlikely, it's
made unreachable.

Threads rather than a second process because the concurrency that actually
matters here is waiting, not computing. A request sitting on a vision API call
holds a thread and releases the GIL; four threads let the UI stay responsive
during a slow extraction without introducing a second writer.

**Why this is a choice and not a limitation.** Redis went in with the
containerisation, so the per-process cache problem described above is fixed —
`--workers 4` would now be *correct*, not a silent 4x on the LLM bill. The
constraint that used to make multiple workers wrong is gone. Staying at one is
about the SQLite write path only, and it is one environment variable to revisit:
raise `GUNICORN_WORKERS` and the shared cache is already there to support it.

**What would change the answer.** Real concurrent write load, or more than one
node — at which point the Postgres migration above becomes the actual blocker,
not the worker count.

---

## Redis with a volume, so the cache outlives the container

**The decision.** Redis is a compose service with a named volume and
`--appendonly yes`. `CACHES` points at it whenever `REDIS_URL` is set, and falls
back to `LocMemCache` when it isn't.

**The obvious reason.** `LocMemCache` is per-process, so it cannot be shared
between workers. That is the constraint written up above.

**The reason that actually drove it.** The extraction cache is keyed on the
SHA-256 of the image bytes plus the description, with a 24-hour TTL. Every miss
is a paid vision call over the network. In a room with unreliable wifi, the
difference between a demo that works and one that stalls on a spinner is whether
that call has to happen *at all*.

`LocMemCache` dies with the process — so does an in-container Redis with no
volume, and so does a Redis with only the default snapshot cadence if it is
killed between saves. The combination that actually holds is all three together:
a Redis service, a volume behind `/data`, and append-only persistence so a write
is durable within a second rather than within an hour.

**Verified, not assumed.** Two extraction cache entries were written, then the
whole stack was taken down with `docker compose down` (containers destroyed,
volumes kept) and brought back up. Both keys were present afterwards, byte-identical
in name, alongside 17 users, 51 listings and 3 uploaded photos. The TTL continues
from where it left off — Redis persists expiry times, so this buys a *restart*,
not a fresh 24 hours.

**The practical consequence.** Warming the cache before a demo is worth doing,
and stays worth doing across a restart, a rebuild of the backend image, or a
laptop that had to be closed. What it does **not** survive is 24 hours — the TTL
is real, and a cache warmed on Thursday afternoon is cold by Friday afternoon.
If the demo window is further out than that, raise `CACHE_TTL` rather than
trusting the warming.

---

## The react-router advisory: not applicable, and here is the check

**The advisory.** [GHSA-qwww-vcr4-c8h2] — "React Router: RSC Mode CSRF Bypass
Allows Action Execution Before 400 Response". High severity. Affects
`react-router` 7.12.0 – 8.2.0.

**Our version.** `react-router-dom@7.18.1`, which pulls `react-router@7.18.1`.
In range. `npm audit` reports it, and will keep reporting it.

**The decision.** Not upgrading, not downgrading. The advisory describes a
vulnerability in a mode of React Router this application does not and cannot
run. `npm audit fix --force` would install `react-router-dom@7.11.0` — a
downgrade, flagged as breaking, to escape a bug we are not exposed to.

**Why it does not apply — four independent reasons, each checked.**

1. **RSC mode requires packages we do not have.** React Server Components mode
   needs a server runtime — `@react-router/rsc` and friends. `npm ls` for the
   whole `@react-router/*` family and `react-server-dom-webpack` returns empty.
   The mode cannot be entered.

2. **We are not even in framework mode.** No `react-router.config.js` / `.ts`
   exists. This is a Vite SPA that happens to use React Router as a library.

3. **We use only the declarative API.** Every import of `react-router-dom`
   across `frontend/src` is one of: `BrowserRouter`, `Routes`, `Route`, `Link`,
   `NavLink`, `useNavigate`, `useParams`. A grep for the data-router surface —
   `createBrowserRouter`, `RouterProvider`, `useFetcher`, `useSubmit`, `<Form`,
   `defer(`, `unstable_` — returns nothing. **The advisory is about router
   *actions* running before a CSRF rejection is returned. We define no actions.
   There is no code path for it to affect.**

4. **There is no CSRF surface on the API regardless.** Authentication is a JWT
   sent as an explicit `Authorization: Bearer` header, read from `sessionStorage`
   by an axios request interceptor (`src/api/tokenStore.js`,
   `src/api/client.js`). CSRF works by the browser *automatically* attaching
   ambient credentials — cookies — to a cross-site request. A header the client
   has to set itself is never attached automatically, and `sessionStorage` is
   not readable across origins. So the class of attack does not reach the API
   even in principle.

   Note this is a statement about CSRF specifically, not about token storage
   being risk-free: a JS-readable token is exposed to XSS, which `tokenStore.js`
   says plainly. Different attack, tracked separately, not what this advisory is
   about.

Point 4 is the one that matters most: 1–3 say the vulnerable code is not
reachable, and 4 says that even if it were, the mechanism it abuses is absent.

**What was fixed instead.** The same audit flagged two others, both genuinely
applicable and both fixed non-breaking with `npm audit fix`:

- `brace-expansion` (high) — DoS via unbounded expansion. Transitive, dev-only.
- `postcss` (moderate) — arbitrary `.map` read via attacker-controlled
  `sourceMappingURL`. Build-time only, via Vite.

`npm audit` now reports exactly one finding, and this section is its
explanation. That is the intended end state: not a clean scan, but a scan with
no *unexplained* entries.

**When to revisit.** If this app ever adopts React Router's data or framework
mode — loaders, actions, `createBrowserRouter` — reasons 1–3 evaporate and the
version must be re-examined that day. Reason 4 holds only while auth stays
header-based; moving the JWT into a cookie would reintroduce CSRF as a real
concern across the whole API, not just here.

[GHSA-qwww-vcr4-c8h2]: https://github.com/advisories/GHSA-qwww-vcr4-c8h2

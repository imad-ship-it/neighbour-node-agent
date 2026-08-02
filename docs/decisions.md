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

# prompts.md — Neighbour Node Agent

AI-interaction log for the Arbisoft AI-Focused Internship 2026 project.

**Coding environment:** Claude Code (agentic AI coding tool), used from day one.
**Working style:** small, verifiable steps — one model → one migration → one commit,
each verified in the Django shell or over HTTP before moving on. Every task below was
given as a prompt; the AI guided, I applied the edits and ran the commands myself.

**How to read this log:** each entry records the *prompt* (the task), the *result*
(what was produced), and — where the AI output was wrong or an assumption broke — the
*correction* I applied and why. The corrections are the important part.

---

## Phase 1 setup

### 1. Repo + environment
**Prompt:** Initialise git, create `backend/` + `frontend/`, set up a venv inside
`backend/`, install Django + DRF, write a `.gitignore` (venv, `__pycache__`,
`node_modules`, `.env`) that does **not** ignore migrations, and add a pre-commit
config running black + isort + ruff, then install the hook.

**Result:** Repo connected to the existing GitHub remote (pulled the README first to
avoid diverging histories), folders + venv created, Django/DRF installed, `.gitignore`
and `.pre-commit-config.yaml` written, hook installed. First commit made.

**Corrections applied:**
- **Stray `.venv` at the workspace root.** A VSCode "create virtual environment"
  popup created a second env at `D:\iccode\.venv` instead of using `backend/venv`.
  Deleted it and pinned the VSCode interpreter to `backend/venv` so future installs
  land in the right place.
- **isort/black fought each other** (surfaced later, in Task 13). The original
  pre-commit config didn't set isort's black profile, so every commit ping-ponged:
  isort reformatted imports one way, black reformatted them back. Fix: added
  `args: ["--profile", "black"]` to the isort hook. Root-caused it to a gap in the
  original config, not a per-file problem.

### 2. Django project + apps skeleton
**Prompt:** Start a `config` project inside `backend/`, create seven apps
(users, listings, matching, messaging, notifications, bookmarks, core), move them
under an `apps/` package, fix each app's config `name` to the dotted path, register
all seven in `INSTALLED_APPS`.

**Result:** Project + apps scaffolded directly into `apps/<name>` via
`startapp <name> apps\<name>`, `apps/__init__.py` added, all seven registered.

**Corrections applied:**
- **`apps.py` `name` field got mangled** by an over-eager bulk replace
  (`"apps.users" = 'users'` — invalid Python, assigning to a string literal). Rewrote
  the targeted line to `name = "apps.users"` for each app.
- **ruff F401** flagged the auto-generated but unused imports in every app's
  `admin.py`/`models.py`/`views.py`/`tests.py`. Since the apps had no code yet,
  deleted the dead imports rather than suppressing the warning.

### 3. Custom User model (before first migration)
**Prompt:** Create a `User(AbstractUser)` in `apps/users/models.py`, set
`AUTH_USER_MODEL` **before** running any migration, then makemigrations + migrate.

**Result:** Minimal `User(AbstractUser)`, `AUTH_USER_MODEL = "users.User"`, first
migration generated (`Create model User`, depending on `auth`) and applied clean.

**Correction / thing learned:** `AUTH_USER_MODEL` uses `app_label.ModelName`
(`"users.User"`), **not** the Python import path (`"apps.users.User"`). Django derives
the app_label from the last segment of the dotted `name`. Getting this wrong throws
`ImproperlyConfigured` on the next manage.py command. Verified by reading the generated
migration's operations before migrating.

### 4. Core models, one at a time
**Prompt:** Build `Listing`, `Bookmark`, `Conversation`, `Message`, `Notification`
from the proposal's field lists — deliberate field types (price as `DecimalField`,
conscious `on_delete` per FK, `__str__` on each) — one model → one migration → one
commit.

**Result:** Five models, five separate migrations, five commits. `DecimalField` for
money, `TextChoices` enums for `category`/`condition`/notification `type`, `on_delete`
chosen per relationship (mostly `CASCADE`, reasoned each time), `__str__` on each.

**Decisions I had to make (flagged by the AI, not assumed):**
- **Conversation participants:** stored `listing` + `initiator` FKs and derive the
  second participant via `listing.lender`, rather than duplicating an owner FK.
- **No separate `Location` model.** The AI caught that a `Location` model would drift
  from the proposal's "plain lat/long on Listing, no GIS stack" decision — kept
  `latitude`/`longitude` as `FloatField` directly on `Listing`.
- Installed **Pillow** for `Listing.image` (ImageField won't pass checks without it).

### 5. JWT authentication
**Prompt:** Install `djangorestframework-simplejwt`, wire login/refresh, write a
custom registration endpoint (hash the password via `create_user`, never save raw),
test register → login → protected endpoint → 401-without-token, commit once the whole
flow works.

**Result:** `RegisterSerializer` using `User.objects.create_user(**data)` (PBKDF2
hashing, password `write_only`), `RegisterView` + simplejwt's `TokenObtainPairView` /
`TokenRefreshView`, a `MeView` protected endpoint. Full flow verified with
`Invoke-RestMethod`.

**Corrections applied:**
- **`rest_framework` was never added to `INSTALLED_APPS`** back in Task 1 (installed
  but not registered). Added it here alongside the DRF JWT auth config.
- **Access token expired mid-test** (`Token is expired`) — this is correct simplejwt
  behaviour (short-lived access tokens), not a bug. Re-logged in / exercised the
  refresh endpoint to continue.

### 6. Frontend scaffold
**Prompt:** Scaffold Vite React, install react-router-dom, TanStack Query, axios; wrap
in `QueryClientProvider`, stub an `AuthContext`, add placeholder `Icon` + `Button`
components. A few small commits.

**Result:** Vite React app, router + query + auth-context provider tree, in-memory
token store (not localStorage, per the proposal), placeholder components with a fixed
icon-size scale.

**Corrections applied (found later, in Task 11):**
- **Blank page.** Several Task-6 commits had silently not landed — `main.jsx` was still
  the untouched Vite default (no `BrowserRouter`/providers), and `Button.jsx`/`Icon.jsx`
  didn't exist on disk. React Router throws on `<Routes>` with no `<Router>`, blanking
  the page. Fix: created the missing components and wired the full provider tree into
  `main.jsx`. Lesson: verify `git log` after each commit — a message that doesn't match
  the file list is the tell that a commit got skipped.

### 7. Register models in Django admin
**Prompt:** Add all five models to their app's `admin.py`, create a superuser, confirm
seeded listings render with the right fields.

**Result:** `list_display` (not bare registration) for each model so the admin list
view shows title/category/condition/price side by side; filters + search on Listing.
The `django.contrib.admin` import (stripped in Task 2) came back for real.

### 8. Listing serializer + viewset + router (CRUD)
**Prompt:** One `ModelSerializer`, one `ViewSet` through a DRF router; reads open to
anyone, writes require auth, `lender` set from `request.user` — never from the body.

**Result:** `ListingViewSet(ModelViewSet)` with `IsAuthenticatedOrReadOnly` +
`perform_create(serializer.save(lender=self.request.user))`, `lender` in
`read_only_fields`. Verified `$created.lender` came back as my user id even though the
POST body never included it.

**Correction:** Added `blank=True` to `Listing.image` — a plain JSON create (no file)
was rejected because `ModelSerializer` derived `required=True` from `blank=False`.
Fresh migration for the field change.

### 9. Bookmark toggle endpoint
**Prompt:** One endpoint that creates the Bookmark if absent, deletes it if present,
returns the new state; lean on the model's `unique_together`, don't re-check duplicates
in the view.

**Result:** `@action(detail=True, methods=["post"])` on `ListingViewSet` using
`get_or_create` (which relies on the DB `unique_together`, race-safe). Verified it
flips `True`/`False` on consecutive calls and 401s without a token.

### 10. Haversine distance
**Prompt:** Standalone great-circle distance in `matching/services.py`; test by hand in
the shell against two known coordinates before wiring it anywhere.

**Result:** `haversine_distance()` (radians → sin/cos/atan2, R=6371km) +
`listings_within_radius()` returning `(listing, distance)` tuples, filtered and sorted
in Python (SQLite has no trig). Verified NYC→LA returned **3935.7 km** (real value
~3936 km) and the radius filter returned only listings ≤ 500 km, ascending.

### 11. Wire Login/Signup to JWT + real listings page
**Prompt:** Call the JWT endpoints, store the access token in AuthContext, attach it as
an Authorization header on later requests; build a listings page fetched through a
React Query hook and rendered with `ListingCard`. Build the error path too.

**Result:** axios client with a request interceptor reading an in-memory token store,
real `AuthContext` with `login`/`register`/`logout` (register chains into login since
the backend register returns no tokens), Login/Signup pages, `useListings()` query hook.
Listings rendered live from `/api/listings/`.

**Corrections applied:**
- Fixed the blank-page issues from Task 6 (see above).
- **Signup "could not sign up" was misleading** — the real backend error was
  `username already exists`, but the catch block showed a hardcoded generic message.
  Noted as a real UX gap to fix in a later polish pass (the message happened to be
  right by coincidence, but a weak-password failure would show the same wrong text).

### 12. Bookmark toggle on ListingCard
**Prompt:** Hook the bookmark icon to the toggle endpoint with a React Query mutation +
cache invalidation, so the icon flips without a page reload.

**Result:** `useMutation` firing the POST, `invalidateQueries(['listings'])` on success
to refetch. Added an `is_bookmarked` `SerializerMethodField` to `ListingSerializer` so
the card knows the current user's state on load.

**Correction / bug caught:** without `is_bookmarked`, the icon would always render
"not bookmarked" on load, and clicking an already-bookmarked listing would silently
*remove* the bookmark while the UI showed it turning on. Real correctness bug, fixed by
computing `is_bookmarked` server-side per current user.

### 13. .env, config, LLM_PROVIDER flag, media serving
**Prompt:** Move secrets to `.env` loaded via python-decouple, keep `.env` gitignored,
wire `MEDIA_ROOT`/`MEDIA_URL` + dev media serving, add an `LLM_PROVIDER` flag defaulting
to `stub` so restarts don't accidentally spend money.

**Result:** `SECRET_KEY`/`DEBUG`/`LLM_PROVIDER`/`ANTHROPIC_API_KEY` moved to `backend/.env`,
loaded with `config(...)` (`DEBUG` with `cast=bool` since env values are strings and
`"False"` is truthy), media serving wired into `urls.py` behind `if settings.DEBUG`,
`.env` confirmed gitignored via `git check-ignore` **before** committing.

**Corrections applied:**
- **`ModuleNotFoundError: decouple`** — the terminal was running *global* Python, not
  `backend/venv` (no `(venv)` prefix; traceback paths pointed at global site-packages).
  Recurring lesson: every new terminal needs `venv\Scripts\Activate.ps1`. Package was
  installed in the venv correctly.
- **Empty `.env`** — the file existed but was blank, so `config("SECRET_KEY")` would
  have crashed. Order matters: fill `.env` first, *then* switch settings to read from
  it. Verified with `manage.py check`.
- **CORS** (added around here): installed `django-cors-headers`, added
  `CorsMiddleware` **above** `CommonMiddleware` (placement matters or headers go
  missing), allowed `http://localhost:5173`. Verified with a preflight OPTIONS request.

---

## Phase 2 / Phase 3 — Agentic AI feature (photo → listing extraction)

### 14. Pydantic extraction schema
**Prompt:** A Pydantic schema for the extraction (title, description, category,
condition, suggested price). Critical: `category`/`condition` must use the exact same
values as the model's `TextChoices` — define once, import in both places.

**Result:** `ListingExtraction(BaseModel)` in `apps/listings/schemas.py`, importing
`Listing.Category`/`Listing.Condition` directly as field types (Django `TextChoices`
*are* Python str enums). Single source of truth — the schema validates against the
exact same enum the DB validates against, so a divergent value is structurally
impossible. Verified in the shell: a valid extraction parses; `category="gadgets"`
raises `ValidationError` (that failure *is* the success condition).

### 15. LLM client layer
**Prompt:** Two providers behind one interface — a stub returning a hardcoded valid
extraction and an anthropic provider making the real call — plus a factory reading
`LLM_PROVIDER`. Timeouts + API error handling live here, once. Build the stub, leave
the real one a skeleton.

**Result:** `core/services/llm/` with `base.py` (abstract interface), `stub.py`,
`anthropic_provider.py` (skeleton), and a factory in `__init__.py`. The anthropic import
is lazy (inside the provider) so the stub path never requires the `anthropic` package.
Model pinned to `claude-opus-4-8`, client-level timeout, `messages.parse` sketched in
comments. Verified the factory returns `StubLLMProvider` by default.

### 16. Extraction service
**Prompt:** The real logic in `listings/services.py`, all testable against the stub:
resize/cap the image, base64 it, build a prompt listing the allowed category/condition
values, demand JSON, strip markdown fences, validate through Pydantic, retry once
feeding the error back, cache on image hash.

**Result:** `extract_listing_from_image()` — Pillow resize/cap to 1568px long edge,
JPEG re-encode, base64, prompt with the allowed enum values injected from
`Listing.Category.values`/`Condition.values`, fence-stripper, `json.loads` → Pydantic,
one retry (`range(2)`) that appends the validation error to the next prompt, 24h cache
keyed on the image (later + description) SHA-256.

**Architecture decision (flagged, not assumed):** Task 15 had built the provider to
return a *validated* `ListingExtraction` via `messages.parse` (structured outputs),
which conflicts with this task's assumption that the service parses raw text and does
its own fence-stripping/retry. The AI surfaced the collision and asked which layer owns
JSON handling. **I chose the raw-text provider** (follow the task literally): refactored
the provider interface from `extract_listing → ListingExtraction` to a generic
`generate → str`, moved parsing/validation/retry into the service. The stub now returns
raw JSON *wrapped in a markdown fence* so the fence-stripper is exercised on every run.
Verified the full pipeline against the stub in the shell.

### 17. Tracing layer
**Prompt:** A tracing layer in `core/services/tracing.py` — agent name, arguments, raw
response, timestamp, per call. A log file or small `TraceLog` model is enough.

**Result:** A `TraceLog` model (agent_name, arguments JSON, raw_response Text,
created_at) + a one-function `trace_call()` service + admin registration
(readonly — traces are a record, not editable). Wired `trace_call` into the extraction
loop **before** the parse block, so a call that fails validation and retries still gets
both raw responses logged. Cache hits are intentionally not traced (no model call made).

**Correction:** first shell test showed `TraceLog.objects.count() == 0` even though
extraction returned fine. Cause: the `manage.py shell` was open *before* I saved the
edit, so Python served the **cached old module** (no `trace_call`). Fix: restart the
shell after editing a `.py` file — the running shell is stale even if the file on disk
is correct. (`runserver` auto-reloads; the shell does not.)

### 18. Async extraction endpoint
**Prompt:** `POST /api/listings/extract/` taking image + description, as an **async**
view (a vision request is seconds of pure I/O wait). Async views can't hit the ORM
synchronously — wrap DB access. Return the extracted draft **without** saving, so the
lender reviews before it becomes a real Listing via the existing create endpoint.

**Result:** `ListingExtractView(APIView)` with `async def post`, wrapping both the file
read and `extract_listing_from_image` in `sync_to_async` (the service writes a TraceLog
and hits the cache — sync ORM work an async view can't call directly; the thread also
frees the event loop during the vision wait). Returns the unsaved draft JSON. URL
registered **before** the router so `extract` isn't parsed as a listing id. Extended the
service to accept `description` (folded into the prompt and the cache key).
`manage.py check` clean.

### 19. Frontend CreateListingForm
**Prompt:** Photo picker + description → submit → honest loading state → returned fields
render as a prefilled editable form → confirm posts to the normal create endpoint.
Build the error path too. Works against the stub.

**Result:** Two-phase form — phase 1 posts multipart to `/listings/extract/` with an
honest "Reading the photo… this can take a few seconds" loading state; phase 2
pre-fills an editable form from the extraction and posts JSON to `/listings/`. Separate
`extractError`/`createError` states for both failure paths.

**Integration realities the endpoints forced (documented so the mapping is explicit):**
- The extraction produces title/description/category/condition/**suggested_price**, but
  the create endpoint requires **latitude/longitude** (non-null on the model) — so the
  review form adds lat/long inputs the lender fills before confirming.
- `suggested_price` (schema) is mapped to `price` (model field) on the way in.

---

## Phase 3 — Match & Ranking agent (Day 4)

Contracts-first, then the agent one step at a time, all runnable against the stub. Reuses
the multi-agent refactor infra (role-based `get_provider`, shared `generate_and_validate`,
run-scoped `TraceLog`, geo-search as a plain callable).

### 20. Define the match-agent contracts first
**Prompt:** Before any logic, three Pydantic models: `MatchQuery` (structured intent —
keywords, category guess, max price, max distance, condition floor, notes), `RankedMatch`
(listing id, score, rank, Markdown explanation, matched factors, concerns), and
`MatchResponse` (the list + candidate count + run id + a `degraded` flag). Everything else
today is written against these, and they're what the retry loop repairs toward.

**Result:** `apps/matching/schemas.py` with the three models, mirroring `ListingExtraction`.
`MatchQuery.category_guess`/`condition_floor` reuse `Listing.Category`/`Listing.Condition`
(same single-source-of-truth trick), everything except `keywords` optional/nullable.
`RankedMatch.score` bounded `ge=0, le=1`, `rank` `ge=1`; `MatchResponse.degraded` defaults
`False`. Verified in the shell: a valid `MatchQuery` parses and coerces (`max_price="45"` →
`Decimal('45')`), and `RankedMatch(score=1.5)` raises `ValidationError` on the bound — proof
the contract actually constrains, which is the point, since the retry loop repairs LLM
output *toward* it.

**Decisions I made (flagged, not assumed):**
- **`category_guess`, not `category`** — it's the LLM's guess, a soft signal ranking can
  override, so it's nullable. Same for `condition_floor`. This deliberately keeps them
  *out* of the hard-filter path (pays off in task 22).
- **`score` (0–1) and `rank` both stored** — score is raw strength, rank is position after
  sorting; keeping both means the frontend never recomputes.
- **`matched_factors`/`concerns` as lists, `explanation` as Markdown** — machine-readable
  factors for badges/filters, prose for the human.

### 21. Match agent step 1 — query understanding (LLM call #1)
**Prompt:** Free text in, `MatchQuery` out. Keep the token budget tiny — it's a parsing
job. Design the prompt to accept an optional *prior query* as context now, even though
session memory doesn't ship until Day 5, so "actually, something cheaper" becomes a
refinement instead of a fresh search. Building the parameter today makes Day 5 plumbing
rather than a redesign.

**Result:** `understand_query(text, prior_query=None, *, run_id, step_index, override)` in
`matching/services.py`, reusing `get_provider("matching")`, a traced per-attempt closure,
and `generate_and_validate(..., MatchQuery, max_retries=1)`. `_build_query_prompt` injects
the allowed category/condition values and, when `prior_query` is present, tells the model
to *carry over unchanged fields and only override what the new message implies*. Verified
against the stub: returns a valid `MatchQuery`, writes one trace row at step 0, and the
refinement path threads the prior query into the prompt without error.

**Corrections applied:**
- **The stub only knew the extraction call.** `StubLLMProvider.generate` returned the drill
  JSON regardless, so validating against `MatchQuery` would fail every time. Taught the stub
  to be prompt-aware — a branch on `"keywords" in prompt` returns MatchQuery-shaped JSON,
  else the extraction default. Keyed on a field name that's always in the prompt, so it's a
  stable marker, not a fragile phrase match. Keeps the "runs with no keys" promise true for
  the match agent too.
- **`run_id`/`step_index` are parameters, not generated inside.** Extraction generated its
  own `run_id` (single call); the match agent is a graph, so the orchestrator owns one
  `run_id` and passes it down (query=0, retrieve=1, rank=2) — otherwise the steps wouldn't
  group together in the trace.
- **Enum serialization note:** `model_dump()` shows `Listing.Category.TOOLS` (the enum
  member); `model_dump(mode="json")` gives the plain string for the API — same trick the
  extraction service already uses.

### 22. Match agent step 2 — candidate retrieval (no LLM)
**Prompt:** Turn the `MatchQuery`'s hard filters into a DB query via the geo-search
callable. Rule: the model never does arithmetic filtering — price ceilings, radius, and
availability are SQL/Python. Cap the candidate set at ~20–25 sorted by distance; beyond
that you pay tokens for listings that will never rank.

**Result:** `retrieve_candidates(query, lat, lng, *, run_id, step_index, limit=25)` — builds
`is_available=True` + `price__lte` filters, radius from `max_distance_km` (default 25),
calls `search_listings_by_distance` (already nearest-first), caps to `limit`, and traces the
step as a `geo_search` tool call (this is why `TraceLog` grew a `tool_name`). Verified from
~Philadelphia against the 43-row seed: 43 pruned to **2** candidates.

**The key design decision (flagged, not assumed):** the task names exactly three hard
filters — price, radius, availability — and stops there. `category_guess` and
`condition_floor` are **not** filtered; they're soft signals the ranker weighs next. The
verification proved this pays off: the two survivors were the "Beat-up Nearby Drill" (poor
condition) and "Cheap Local Camera" (wrong category) — near, cheap, and *deliberately not
dropped*, so the ranker has a real trade-off to reason about. The far-away "Pristine
Cordless Drill" was correctly killed by the radius (a hard filter working). If retrieval had
over-filtered, there'd be nothing interesting to rank.

**Correction:** with `Listing` now imported at module top, the old lazy
`from apps.listings.models import Listing` inside `search_listings_by_distance` was
redundant — removed the dead re-import.

---

## Recurring lessons (things I kept correcting)

- **Activate the venv in every new terminal.** Most "module not found" / wrong-Python-
  version errors traced back to a terminal running global Python. The tell: no `(venv)`
  prefix and traceback paths under the global site-packages.
- **Restart the `manage.py shell` after editing code.** Python caches imported modules
  per process, so a shell opened before an edit serves the stale version.
- **Check `git log` after every commit.** A commit message that doesn't match the files
  git prints means an earlier commit was skipped (bit me twice).
- **pre-commit auto-fix "fails" the first run on purpose.** When black/isort reformat a
  file they report failure and abort so you can review — re-`git add` and commit again.
- **Flag drift instead of silently reconciling it.** Several times the AI caught a task
  assuming a different architecture than what was already built (Location model,
  structured-outputs vs raw-text) and surfaced the decision rather than guessing.
- **Stub-first means the stub has to answer every call type.** When the match agent added a
  second kind of LLM call, the extraction-only stub silently failed validation. The fix is a
  prompt-aware stub that returns the right shape per call — otherwise "runs with no keys"
  quietly stops being true for the new feature.

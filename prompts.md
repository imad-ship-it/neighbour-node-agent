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

## Phase 3 — Hardening pass (Day 5)

### 23. Frontend shell — navigation and styling

**Prompt:** The frontend renders seeded data but nothing is clickable and it looks wrong.
Audit and fix.

**Result:** Three separate problems, none of them CSS tweaks. (1) There was **no navigation
anywhere in the app** — not one `<Link>`; `/create`, `/login` and `/signup` were reachable
only by typing the URL. (2) `App.css` was untouched Vite boilerplate (`.hero`, `#next-steps`)
and **was never imported**, so `.listing-card` and `.btn` had no rules at all. (3) `Icon`
rendered an empty `<span>` with no SVG, and `public/icons.svg` only held the starter's
github/discord symbols — so the bookmark button was an invisible box.

Added `components/Layout.jsx` (sticky header, nav, live auth state), rewrote `App.css` as a
real stylesheet, gave `Icon` inline bookmark SVGs using `currentColor`, and dropped the
starter's `text-align: center` / fixed `1126px` on `#root`.

**Correction:** the bookmark button was firing a silent 401 when logged out. Now it only
renders when a user is present, rather than failing invisibly.

---

### 24. Auth interceptor — stale token on public endpoints

**Prompt:** Signup always fails with "try a different username" even for unused names.

**Result:** Two bugs stacked. The axios request interceptor attached the bearer token to
**every** request including `/auth/register/` — and because **DRF authenticates before it
checks permissions**, an expired token makes the authenticator raise 401 on an `AllowAny`
view; permissions never run. Login was immune only because SimpleJWT's `TokenObtainPairView`
sets `authentication_classes = []`.

Added a `PUBLIC_PATHS` skip-list in `client.js` and an `apiError()` helper that pulls the
real message out of a DRF error body.

**Correction:** the catch block reported *every* failure as a duplicate username — including
a successful register followed by a failed login, which created accounts while telling the
user they hadn't been created. Login, signup and both create-flow handlers now surface the
actual server message.

---

### 25. JWT access-token lifetime

**Prompt:** Users are being logged out a few minutes after logging in.

**Result:** `SIMPLE_JWT` was never configured, so the access token used SimpleJWT's default
**5-minute** lifetime while the frontend holds it in memory with no refresh flow. Set
`ACCESS_TOKEN_LIFETIME` to 8 hours and `REFRESH_TOKEN_LIFETIME` to 1 day.

---

### 26. Extraction endpoint — async handler removed

**Prompt:** `POST /api/listings/extract/` returns 500 on every request. Diagnose.

**Result:** `SynchronousOnlyOperation`, raised inside SimpleJWT's `get_user()`. Django decides
a view is async by inspecting its handlers, so `async def post` made it run the whole view on
the event loop — but **DRF's `dispatch` is synchronous**, so DRF's authentication executed
inside that loop and its ORM query blew up. It failed during authentication, before the
handler was ever reached.

DRF 3.17.1 has no async support at all (not one `async def` in its `views.py`), so the
endpoint is now a plain sync view with a docstring explaining why. The two internal
`sync_to_async` wrappers went with it — they were protecting code that never ran.

**Correction:** this endpoint had never worked since the commit that introduced it. Under
ASGI, Django already runs sync views in a threadpool, so nothing is lost.

---

### 27. Undecodable uploads return 400, not 500

**Prompt:** Uploading a non-image (a PDF, a truncated JPEG) returns a 500 with a traceback.

**Result:** `_prepare_image` was called **outside** every try block, so `PIL.UnidentifiedImageError`
escaped the view's `except ExtractionError` and became an unhandled 500. Added a distinct
`InvalidImageError`, raised from `_prepare_image` and mapped to **400** in the view — kept
separate from `ExtractionError` (502) so bad client input and a failing pipeline don't share
a status code.

Guarded the whole decode block, not just `Image.open`: `convert()`/`thumbnail()` fail on
truncated files and `DecompressionBombError` isn't an `OSError` subclass, so it needs listing
explicitly.

---

### 28. Object-level permissions on Listing

**Prompt:** Check whether the listing API enforces ownership on writes.

**Result:** It did not. `IsAuthenticatedOrReadOnly` only asks *"are you logged in?"* — DRF
runs an object-level check only if a permission class implements `has_object_permission`, and
that one doesn't. Verified by having one account PATCH (200) and then DELETE (204) another
user's listing. Added `listings/permissions.py` with `IsOwnerOrReadOnly` — safe methods pass,
writes require `obj.lender == request.user` or `is_staff`.

**Correction (the part worth recording):** adding it naively **breaks bookmarking**. Bookmark
is a `POST` against a listing you deliberately *don't* own, and because the action calls
`get_object()`, DRF runs the object check and every bookmark would 403. Fixed with a
`get_permissions()` override dropping that one action to plain `IsAuthenticated`.

---

### 29. Save the uploaded photo with the listing

**Prompt:** The photo drives extraction but the created listing has no image.

**Result:** The create request was a JSON body of seven fields with the file never attached —
so every uploaded photo was used for extraction and then discarded (0 of 44 listings had an
image; `media/` didn't exist). Switched the create to `FormData` with the file appended, and
added `backend/media/` to `.gitignore`.

**Correction:** this introduced a regression I only caught when the UI showed a new listing as
"on loan". On a **multipart** request DRF's `BooleanField.get_value()` reads an *absent* field
as `False` — it assumes an unchecked HTML checkbox — so `is_available` stopped falling back to
the model default. Same endpoint, same data, only the content type changed. Fixed by setting
`is_available=True` explicitly in `perform_create` so it holds for any client, not just this
form. My first verification of this change checked the image and latitude but not the boolean.

---

### 30. Register the custom User in the admin

**Prompt:** `User` doesn't appear in the Django admin.

**Result:** Swapping `AUTH_USER_MODEL` unregisters Django's built-in auth admin. Registered
`User` explicitly, subclassing `BaseUserAdmin` — a plain `ModelAdmin` renders the password as
an **editable hash field**, which silently corrupts credentials.

---

### 31. Provider error messages and dead env var

**Prompt:** The Anthropic provider's `NotImplementedError` names `LLM_PROVIDER`, which no
longer exists.

**Result:** Left over from the role-registry refactor; the real settings are
`EXTRACTION_PROVIDER` / `MATCHING_PROVIDER`. Fixed both provider messages. Grepping for the
old name also turned up `LLM_PROVIDER=stub` still sitting in `.env` — a dead line, with
neither real setting present. It only worked because both default to `"stub"` in settings.
Replaced it with the two actual variables.

---

## Phase 3 — Scaffold docs, agent wiring & memory (Day 6)

### 32. README: architecture diagram, tech choices, model selection rationale

**Prompt:** Week 5 deliverable — the README needs an architecture diagram, tech choices with
reasoning, and a model selection rationale. Use Mermaid so GitHub renders it natively with no
image files to maintain.

**Result:** Added an `## Architecture` section with one Mermaid flowchart (React → DRF →
service layer → provider registry → the two models), with `geo_search` on a dashed edge so it
reads as a tool rather than a pipeline stage. Added a "Why" column to the tech-stack table and
a `## Model selection rationale` section. Added `backend/.env.example` and changed the setup
step from pasting a block to `cp .env.example .env`.

**Correction:** the env table listed `anthropic` / `deepseek` as valid provider values without
saying they raise `NotImplementedError` and need client libraries deliberately kept out of
`requirements.txt`. Documented both, so the table stops promising something that doesn't work.

---

### 33. Model selection: Opus vs Haiku for vision extraction

**Prompt:** Which model should extraction use, and what does a call actually cost?

**Result:** Costed it from what the pipeline sends: image capped at 1568px → ~1,600 image
tokens, ~200 prompt, ~100 output. About $0.012/call on Opus 4.8 against $0.0023 on Haiku 4.5.
Chose Opus: four of the five extracted fields are trivial (short strings, validated enums), but
`suggested_price` needs the model to identify the item and judge wear from the photo. Left
extended thinking off and kept the 1568px cap — both multiply cost with no gain on a five-field
extraction.

**Correction:** the code was internally inconsistent. `MODEL` said `claude-opus-4-8` while
`MAX_IMAGE_DIM = 1568` is the cap for the older vision tier, so it was paying Opus rates for
lower-tier image fidelity. The commented call skeleton also paired `thinking={"type":
"adaptive"}` with `max_tokens=1024`, where thinking and response share that budget and would
have truncated the JSON. Dropped the thinking line and recorded the choice as a class comment
so the code and the README agree.

---

### 34. Ranking step and the `/api/match/` endpoint

**Prompt:** `understand_query()` and `retrieve_candidates()` work, but there's no third step
and no HTTP route — the agent can only be run from the shell.

**Result:** Added `rank_candidates()` (LLM call #2) and a `RankingResult` schema carrying only
the model's output, since `run_id` / `candidate_count` / `degraded` are filled server-side.
Wired `MatchView` and `matching/urls.py`. One `run_id` threads all three steps, so a whole
agent run pulls out of `TraceLog` as a single ordered trace.

**Correction:** two guards that earned their place. The model can return a `listing_id` that
was never retrieved, so the service filters results against the ids it passed in. And a ranking
failure degrades to distance-only ordering instead of 502-ing the search — a worse ranking is
more useful than an error page, and the `degraded` flag was already in the schema for exactly
this.

---

### 35. The prompt-aware stub had to echo real candidate ids

**Prompt:** The match endpoint returns `candidate_count: 3` but `matches: []`.

**Result:** Not a bug. The stub hardcoded `listing_id: 1`, and the hallucination filter
correctly dropped it because seeded listings have ids in the 280s — correct behaviour that
reads as broken. Changed the stub to parse ids out of the rank prompt (`id=(\d+)`) and rank
the real candidates, so the no-key demo produces a plausible result.

**Correction:** branch ordering in the stub is load-bearing. The rank prompt embeds
`query.model_dump_json()`, and a serialised `MatchQuery` contains the key `"keywords"` — so a
ranking call also matches the query-understanding branch. The `matched_factors` check has to
come first, or ranking calls get `MatchQuery` JSON back and fail validation.

---

### 36. Per-user session memory for query refinement

**Prompt:** Week 6 goal — memory layer. `understand_query()` already accepts `prior_query` and
builds a refinement prompt from it; nothing ever passes one.

**Result:** `MatchSession` model (one row per user via `OneToOneField`) holding the last
structured query, run id and turn count. `load_prior_query()` / `remember_query()` / `forget()`
in the service layer, wired into the view behind a `fresh` flag to start over, and registered
in the admin so stored memory is inspectable during a demo. Verified: turn 2 said only
"actually only within 5km" and the agent carried `['cordless', 'drill']` and `$50` forward,
with `has_prior: True` recorded in the step-0 trace.

**Correction:** memory needs an expiry. Without the 30-minute TTL a search from yesterday would
silently constrain today's — a constraint the user can't see, didn't ask for and can't explain.
Stale memory is worse than no memory.

---

### 37. Seed fixtures had to be built before the rules that read them

**Prompt:** Day 5's overdue MCP block needs a `trust_check` tool, and the brief says the
three seeded awkward cases are its test fixtures.

**Result:** Checked the fixtures against the planned rules before writing any of them. The
three awkward cases break *ranking* dimensions (far away, poor condition, wrong category for
the search), not *internal consistency*, which is what a trust rule can see from one row. Added
four trust fixtures — one broken rule each, everything else deliberately normal — so a flag
identifies its own rule with no ambiguity.

**Correction:** two rules were unusable as seeded. `no_photo` would have fired on **all 43**
rows, because `bulk_create` never set `image` — a flag that fires on everything carries no
information. And the random rows drew `title` and `category` independently, so ~80% of them had
a title noun disagreeing with their category; `title_category_mismatch` would have returned ~30
rows of pure seed artifact and buried the one real fixture. Fixed by giving 90% of rows a photo
and deriving category (and price band) from the item noun. Result: 10 of 47 flagged, every one
deliberate.

---

### 38. Keyword rules need an escape for legitimately ambiguous titles

**Prompt:** Write the four trust rules.

**Result:** `price_out_of_range` (per-category band, `high` past 5×), `title_category_mismatch`,
`thin_description`, `no_photo`. Flags carry a stable `code`, a `severity` and the `evidence`
that fired them — structured, so a client can branch on the code and a model can weigh the
severity, rather than parsing a sentence.

**Correction:** the first title rule flagged "Folding Camping Table" (filed under
sporting_goods) because *table* is a furniture keyword — breaking a fixture that was supposed to
test only `no_photo`. Fixed by collecting **all** categories a title hints at and staying silent
when the row's own category is among them. A title can carry more than one signal, and a rule
that takes the first match manufactures disagreements that aren't there.

**Correction:** wrote the price bands independently of the seeder's ranges rather than importing
them. Sharing the constant would make the rule circular — able to catch only what the seeder
happens not to generate, and silently useless on real data.

---

### 39. Extracting a traced wrapper dropped a guard that looked like formatting

**Prompt:** MCP tools and the agent must write identical `TraceLog` rows, so the tracing has
to live in the service layer, not in the MCP adapter.

**Result:** `check_listings()` traces the batch (not `check_listing`, which would write a row
per candidate), and a new `geo_search()` wrapper traces around
`search_listings_by_distance()`. `agent_name` distinguishes the callers: the agent leaves the
default, the MCP server passes `"mcp"`. The error path traces too — a tool call that failed is
still a tool call.

**Correction:** the extraction broke `/api/match/` outright. The old inline trace passed
`str(query.max_price)` into `arguments`, which reads as incidental formatting but is load-
bearing: `TraceLog.arguments` is a `JSONField` and `Decimal` isn't JSON-serialisable. The new
wrapper passed `filters` through raw and every priced search raised `TypeError`. Restored as
`_json_safe()`. Moving code past a guard you don't recognise silently deletes it.

**Correction:** `retrieve_candidates` had to *stop* tracing once `geo_search` traced, or every
retrieval wrote two `geo_search` rows into the same run.

---

### 40. Trust-check belongs before compaction, not after ranking

**Prompt:** Wire the tool into the agent so flags reach the model, not the response.

**Result:** `retrieve_candidates` now returns `(listing, distance, trust_report)` triples and
runs the check between retrieval and prompt building — so a flagged listing reaches the ranker
as `| flags: thin_description(medium)` on its candidate line, with an instruction to downrank
high-severity flags. Clean listings add no text and cost no tokens. Trust-checking happens after
the candidate cap, so nothing is checked that was already discarded.

**Correction:** the shape change had four call sites — the prompt builder, the `valid_ids` set,
the degraded fallback, and the view's step numbering — and the degraded path is the one no normal
run exercises. Forced it with a patched provider before believing it. Also made the degraded
fallback carry flag codes into `concerns`: the ranker is gone in that path, but the rules are
deterministic and still worth showing.

---

### 41. A stdio server that "drops the connection" may just be EOF

**Prompt:** Expose the tools over MCP and prove a client can drive them.

**Result:** `geo_search`, `trust_check` and a `listing://{id}` resource, all thin adapters over
the service layer. Argument validation names the offending argument
(`lat must be between -90 and 90, got 400`) and the category error lists the valid values
generated from `Listing.Category.values`, so it can't drift from the model. Claude Code chained
`geo_search` → 3× `trust_check` unprompted, ranked the results by the severity field, and
repeated the tool's own "consistency, not honesty" caveat to the user. Given a bad category it
read the error and retried with a valid one on its own.

**Correction:** the first smoke test piped requests and let stdin hit EOF immediately. The two
validation-only calls answered; every call that touched the database vanished and the next got
`Connection closed`. Nothing was broken — the server began shutting down on EOF while the
slower calls were still on a worker thread. That failure mode is indistinguishable from a
crashed server, and cost more time than the feature did.

**Correction:** mcp 2.0 renamed `FastMCP` to `MCPServer`, so the Week 5 import didn't apply. It
also dispatches sync tools through `anyio.to_thread.run_sync`, which means ORM calls land in a
real thread and `DJANGO_ALLOW_ASYNC_UNSAFE` — which I'd assumed was required — is not needed.
Checking the installed package beat carrying an assumption forward from a different version.

---

### 42. One provider fixture, patched where the name is used

**Prompt:** Block 2 — service tests. Build one reusable stub-provider fixture first, then
test extraction and matching against it.

**Result:** `apps/core/testing.py` (deliberately not a `tests.py`, so both apps can import
it without depending on another app's test module). `ScriptedProvider` returns queued
responses in order and records `calls`, `prompts` and `images`; `scripted_provider()` is a
context manager that patches `get_provider` and yields the instance. Recording prompts is
what makes the retry testable — otherwise you can prove a second call happened but not that
it was told anything.

**Correction:** patching `apps.core.services.llm.get_provider` does nothing. Both services
do `from apps.core.services.llm import get_provider`, which binds the function into their
own module namespace at import time, so the patch has to target
`apps.listings.services.get_provider` and `apps.matching.services.get_provider`. Patch where
a name is used, not where it is defined.

**Correction:** running out of scripted responses raises `ScriptedProviderExhausted`, a
subclass of `AssertionError` rather than a plain exception. An over-call is a wrong test (or
a regressed retry cap), and it should read as a failed assertion, not a provider outage.

---

### 43. The brief asked for a test of a feature that didn't exist

**Prompt:** Test the matching agent: three steps under one run_id, radius widening on zero
candidates, hallucinated id rejected, degraded fallback.

**Result:** Checked each against the code before writing any of it. There was no radius
widening — `retrieve_candidates` did `radius = query.max_distance_km or DEFAULT_RADIUS_KM`
and stopped there. Implemented it: one widened pass at 100km when the requested radius
returns nothing, only when that would actually help, so a 200km request is never narrowed.
Added `widened` to `MatchResponse` for the same reason `degraded` is there — a constraint
the user didn't ask for shouldn't be invisible. Also noted the brief said "three steps"; it
has been four since trust-check landed at step 2.

**Correction:** widening changed `retrieve_candidates` to return `(candidates, widened)`,
which the view had to unpack — the third signature change through that function in two days.
Followed the existing `result.refined = ...` pattern rather than inventing a new one.

**Correction:** the first verification was weak. Searching from the middle of the Atlantic
set `widened=True` but still found nothing, which proves the flag flips, not that widening
does anything. Re-ran it from 55km north of the seeded cluster: `15.0 -> 0 within radius`,
then `100 -> 4 within radius`. Test the case where the fallback actually rescues something.

---

### 44. Cache tests that would have passed for the wrong reason

**Prompt:** Test the cache carefully — a broken cache costs real money once live keys land.

**Result:** Four tests, each mapped to a way the cache costs money: same image hits (or you
pay every time), different description misses (or a lender gets someone else's listing),
different image misses (key collision), and the cached value round-trips. Pinned to a
dedicated `LocMemCache` LOCATION via `override_settings` so a stale entry from `runserver`
can't leak in.

**Correction:** `TestCase` does not clear the cache between tests, and `LocMemCache` is
per-process. The first two extraction tests use the same 10x10 PNG and the same empty
description, so they hash to the *same key* — without `cache.clear()` in `setUp`, the second
test would have been served the first one's cached result and passed with the provider never
called at all. A green test that never ran the code under test.

**Correction:** verified the round-trip test wasn't vacuous by inspecting what actually sits
in the cache. `model_dump(mode="json")` stores `suggested_price` as the **string** `'35.00'`;
it comes back as `Decimal('35.00')` only because pydantic re-coerces it on the way out. Write
and read are separate code paths and nothing had ever proved they agreed.

---

### 45. Duplicated test methods pass silently

**Prompt:** Add the remaining three matching tests.

**Result:** Degraded fallback, radius widening, and a test asserting trust flags reach the
ranking prompt. That last one is the guard on the annotator seam: move the trust check to
after ranking and every other test still passes, but that one fails. Confirmed it
discriminates — `thin_description` appears in the prompt only when a flag actually renders,
never in the instruction text.

**Correction:** the three tests ended up in the file twice. Python silently lets a later
`def` replace an earlier one, so the suite reported 14 tests, everything passed, and nothing
looked wrong — the duplicates had quietly shadowed the originals. Only ruff's `F811` caught
it. If the two copies had drifted, I'd have been running the version I wasn't reading.

**Correction:** the degraded test needs *two* `scripted_provider` blocks. `raises=` makes
every call fail, so a single block breaks `understand_query` too and the test ends up
asserting `MatchError` instead of the degrade path it claims to cover.

---

### 46. Going live on Claude, and the three things a stub cannot tell you

**Prompt:** Take extraction live on the cheapest vision-capable tier with capped
`max_tokens`, run three real photos, and check what the stub structurally cannot simulate:
whether responses actually arrive fenced, whether validation passes first try or triggers
the retry, and whether extracted values are plausible.

**Result:** Switched `AnthropicLLMProvider` from `claude-opus-4-8` to `claude-haiku-4-5`
(~$0.0023/call against ~$0.012) and filled in the real `messages.create` call — image block
before text, `max_tokens=512` as a ceiling rather than a target, no retry loop of its own
because the SDK already retries 429/5xx and `generate_and_validate` owns the validation
retry. Three photos chosen to isolate different failure modes: a battered angle grinder
(wear judgement, partial crop), a desk lamp (category ambiguity), and a Magic Bullet blender
(legible branding).

Three answers, six live calls, about $0.014:

- **Fenced: 6 of 6.** The prompt says "Do not wrap the JSON in markdown code fences" and
  Haiku wrapped it every single time. `strip_code_fences` is not defensive dead code, it is
  the only reason the pipeline parses at all. The stub happened to return fenced output too
  — that was luck, and now it's evidence.
- **Retry: never fired.** One call per photo, validation passed first try each time. Even
  the ambiguity test didn't fail: the closed enum means the model cannot return an *invalid*
  category, only a debatable one (it picked `furniture` for the lamp). So the live retry path
  is still only covered by unit tests. Logging that as a real gap rather than a pass.
- **Brand reading works on the cheap tier.** It returned "Magic Bullet Blender" from the
  logo. That is precisely the capability the README's model-selection rationale claims
  justifies Opus. Condition also varied for the right reasons — `fair` on the grinder with
  "visible signs of wear", `like_new` on the other two — so that field is real judgement, not
  a default.

**Correction:** switching to Haiku also fixed the inconsistency logged in entry 33.
`MAX_IMAGE_DIM = 1568` is the cap for the older vision tier; Opus 4.7+ reads up to 2576px, so
the old pairing paid frontier rates for lower-tier image fidelity. The code is now internally
consistent — but the README still argues for Opus, so the docs and the code now disagree in
the opposite direction. Entry 33's lesson, arriving a second time.

**Correction:** two Haiku-specific API constraints that would have been 400s — `effort` is
rejected on Haiku 4.5, and Haiku predates adaptive thinking so the `thinking` parameter must
be omitted entirely rather than set to `disabled`. Checked the installed SDK's current
contract instead of carrying over the Opus-era call shape.

---

### 47. The price was wrong because the prompt never said what the price meant

**Prompt:** Read the extracted values critically — a wildly wrong `suggested_price` is a
prompt problem, not a parsing one.

**Result:** All three first-run prices were wrong in the same direction: $25 for the blender,
$45 for the lamp, $18 for the grinder. Those are **resale values**, not lending rates — a
Magic Bullet retails around $30. Wrong the same way three times out of three is systematic,
not noise.

The cause was in the prompt's own first line: *"You are extracting structured data about a
**second-hand item** from its photo"*, with `suggested_price: a number in USD`. This is a
**lending** marketplace, and nothing in the prompt said so. The model priced the object
because that is what it was asked to do.

Rewrote three lines — the framing ("an item a neighbour is offering to LEND OUT"), the price
field ("the DAILY LENDING RATE in USD ... NOT what the item costs to buy"), and the
description ("about the ITEM ITSELF — ignore backgrounds, props and staging", because the
blender description had been narrating the marketing photo's fruit). Same model, same
images, prompt change only:

| Item | Before | After |
|---|---|---|
| Magic Bullet blender | $25.00 | $3.00 |
| Desk lamp | $45.00 | $5.00 |
| Angle grinder | $18.00 | $5.00 |

`category` and `condition` came back identical across both runs — the edit moved the field it
targeted and left everything else stable.

**Correction:** in the same batch, with the same prompt, Haiku returned `"suggested_price":
3.00` as a JSON *number* for one photo and `"5.00"` as a *string* for the other two. The
`Decimal` field coerces both, so it validated either way — a stricter `float` annotation
would have failed two of three. Lenient typing was doing invisible work; now it's a
documented reason not to tighten it.

**Correction:** I was told the extraction cache would return stale results on a re-run and
would need clearing first. Wrong — there is no `CACHES` block in settings, so Django uses
`LocMemCache`, which lives in process memory and dies with the process. Every script run
starts cold. That matters for cost: re-running the same photo in a new process is a fresh
paid call, not a free cache hit. The 24h cache only helps inside one long-lived process such
as `runserver`.

---

### 48. DeepSeek live, and a finding that only exists once two providers are real

**Prompt:** Take matching live. DeepSeek is OpenAI-compatible, so it should be a base-URL
swap in a new provider class. Run three real queries including one awkward case.

**Result:** `DeepSeekLLMProvider.generate()` filled in against the `openai` client with
`base_url="https://api.deepseek.com"` — the entire integration really is a base-URL swap, no
second SDK. `MAX_TOKENS = 1500` rather than extraction's 512, because a ranking response
carries several matches each with a Markdown explanation, matched factors and concerns.
Three queries: one naming the item directly, one naming the *job* instead of the tool ("cut
through some metal pipes"), and one deliberately vague ("hosting a barbecue... sort out the
cooking").

The finding that made this worth doing came from having both providers live at once:

| Model | Responses arriving fenced |
|---|---|
| Claude Haiku 4.5 | **6 / 6** |
| DeepSeek chat | **0 / 3** |

Same instruction, same codebase, opposite behaviour. Entry 46 recorded "the model ignores
the no-fences instruction" — that turns out to be a *Haiku* property, not a general truth.
`strip_code_fences` is load-bearing for one provider and dead code for the other, and there
was no way to know which from a single live model.

Also validated live: the annotator seam from entry 40. A real model read the trust flags out
of the compacted prompt and weighed them — *"the poor condition and `thin_description` flag
lower the score"*, with the flag repeated in `concerns`. Until now only the stub had ever
done that.

**Hallucinated listing ids: 0 of 3 returned.** The `valid_ids` guard never fired. Recording
it as measured rather than assumed, with the caveat that three queries returning three ids is
too small a sample to claim the failure mode doesn't occur — only that it didn't here.

**Correction:** the provider raises on `image_base64` instead of ignoring it. `deepseek-chat`
has no vision, and silently dropping the image would produce a confident description of
nothing — the worst possible failure shape.

---

### 49. The ranker invented fit rather than returning nothing

**Prompt:** Read the Markdown explanations critically. Generic praise means the prompt needs
tightening to demand the concrete deciding factor.

**Result:** The failure was worse than generic praise. Asked for something to *"cut through
some metal pipes"* — with nothing in the candidate set that cuts metal — DeepSeek returned
two matches: a drill ranked first (*"likely usable for cutting"*) and an **extension cord**
ranked second at score **0.5**, explained as *"not ideal for cutting metal but is a tool-like
item, cheap and nearby."*

The explanations weren't vague. They were specific, fluent, and wrong, which is far more
dangerous in a demo — vague praise reads as weak, a confident false rationale reads as
competent until somebody checks. The score scale was unused too: 0.5 for an item with zero fit.

The prompt already said *"Leave out listings that clearly don't fit rather than padding the
list."* It padded anyway. Three replacements:

- *Returning an empty matches array is the **CORRECT** answer when nothing genuinely does the
  job* — permitted was not enough, it had to be named as right.
- *Never claim an item can do something the listing doesn't support. If it cannot do the job,
  exclude it; do not include it with a caveat.*
- *Each explanation must name the concrete reason THIS listing fits THIS request.*

**The extension cord appeared in 1 of 1 runs before, and 0 of 4 runs after.**

**Correction:** the behaviour was inconsistent before the fix, which is what made it easy to
miss. The same prompt padded on the metal-pipes query and correctly returned nothing on the
barbecue query. An instruction being followed *sometimes* looks like a working instruction.

---

### 50. I called a regression off a single run, and was wrong

**Prompt:** (self-inflicted) After tightening the rank prompt, one query that previously
returned a match came back empty. Reported it as a regression caused by the fix.

**Result:** It wasn't. Four post-fix runs of the identical three queries:

| Query | Post-fix results across 4 runs |
|---|---|
| "cordless drill under $50" | `[]`, `[375]`, `[375]`, `[375]` |
| "cut through metal pipes" | `[375]`, `[375]`, `[375]`, `[]` |
| barbecue | `[]`, `[]`, `[]`, `[]` |

The empty result showed up in roughly **one run in four**, on *both* queries, in no
particular pattern. It was run-to-run variance, not the prompt. The real signal was the one
that held across all four runs: the extension cord never came back.

**Correction:** the tell was already in the data and I read past it. The vague query's
`category_guess` flipped between `other` and `appliances` between runs — and I had not
touched the query-understanding prompt at all. Output changing on a prompt I didn't edit is
proof that a single before/after comparison cannot attribute anything.

**Correction:** this also changes a product requirement, not just a methodology one. A
neighbour can run the same search twice and get a result, then nothing. The empty state has
to read as "nothing nearby fits" rather than looking like a failed request — the UI cannot
treat an empty `matches` array as an error. Same reason `degraded` and `widened` are on the
response: a constraint the user can't see needs saying out loud.

---

### 51. Two-model comparison: the architecture finally earned its keep

**Prompt:** Route one match query through both providers using the per-call override. Week 7
graded deliverable, should take about fifteen minutes.

**Result:** It did, because the plumbing was built on Day 4 — `get_provider(role, override)`
took the override argument specifically so the same input could go to two models without
touching settings. The comparison script only had to pass `override=` through
`understand_query` and `rank_candidates`. Three runs per provider, not one, per entry 50.

| | fenced | avg latency | returned the match |
|---|---|---|---|
| `deepseek-chat` | 0 / 6 | 5.76s | 2 / 3 |
| `claude-haiku-4-5` | 6 / 6 | 6.19s | 3 / 3 |

**This settles entry 48's open question: fencing is a model property, not a prompt property.**
Haiku fenced 12 of 12 calls across two unrelated prompts — extraction and ranking — both of
which explicitly forbid it. DeepSeek fenced 0 of 9. One model ignores the instruction
universally, the other complies universally, and no amount of testing against a single
provider could have distinguished "models do this" from "this model does this".

Haiku was also steadier here: identical 0.72 score on all three runs against DeepSeek's
0.7 → 0.55 → empty, and it quantified its reasoning ("well under budget at $20, very close
at 1.4km") where DeepSeek stayed qualitative ("for a weekend project it will work").

**Correction:** that is awkward for the README, which justifies DeepSeek for matching partly
on quality. DeepSeek is still ~4× cheaper per token so the cost half stands, but the quality
half is no longer one-sided. Recorded in the README as an open question with the numbers
attached rather than quietly deleted or overreacted to — three runs of one query is evidence,
not a mandate to re-architect.

**Correction:** the two models tokenise differently — `['cordless', 'drill']` versus
`['cordless drill']`. Harmless today only because `retrieve_candidates` filters on price,
radius and availability and never reads `keywords`. The moment keywords drive filtering it
becomes a bug that reproduces on one provider and not the other, which is the worst kind to
diagnose. Noted while it is still theoretical.

---

### 52. The match UI, and the field no client could have computed

**Prompt:** Build the match UI — search box, results list, `MatchExplanation` rendering the
Markdown, wired to `/api/match/`.

**Result:** The obvious plan was a client-side join: `MatchResponse.matches` carries only
`listing_id`, and the app already holds every listing in a TanStack cache, so joining in the
browser looked free. It isn't possible. **`distance_km` is computed per search by haversine
and is not a field on `Listing`** — no join against `/api/listings/` could ever produce
"1.4 km away", which is the single most important fact in a *neighbourhood* lending app.

So the service resolves it instead: a `ListingSummary` schema, populated in `rank_candidates`
from the candidates it is already holding. `RankedMatch` stays unchanged — the model should
not be echoing back data we already have, and anything it echoed would need verifying against
the database anyway. Two tests, one of them for the degraded path specifically, because that
branch builds its own `matches` list and would otherwise render a blank card at exactly the
moment the ranker is already broken.

Frontend: `useMatch` (a **mutation**, not a query — `useQuery` refetches on window focus,
which would silently re-bill a paid LLM call and mutate the user's `MatchSession` memory
every time they alt-tabbed), `MatchExplanation`, `MatchCard`, and a `Match` page whose real
substance is five response states, not the form.

**Correction:** `react-markdown` over a hand-rolled renderer, and the reason is not
convenience. The explanation is **model output — untrusted input that happens to look like
content**. Every hand-rolled Markdown renderer ends at `dangerouslySetInnerHTML`, which would
be an XSS sink fed directly by an LLM. The component also flattens block elements (a stray
`<h1>` must not restructure a card), drops `href`s while keeping link text (a model-authored
URL in a lending recommendation is a phishing surface the user has every reason to trust),
and renders `<img>` as nothing. Cost: roughly 100KB gzipped, which is a real price and worth
stating rather than discovering later.

**Correction:** entry 50's variance showed up on the very first live search — "Nothing nearby
fits that", then the same query returned a match. That is why the empty state was built to
read as an answer rather than an error, and why it needed building *before* it was seen
rather than after a user reported the app as broken.

**The payoff, in one chip.** A live search for "something to help me move furniture" returned
a folding camping table at 45%, with two amber concerns: *"no photo available – you can't see
the item"* and *"sporting goods category differs from furniture"*. Trace the first back:
a seed fixture with `image=""` → `_check_photo` → `TrustFlag(code="no_photo", severity="low")`
→ `_format_flags` writes `flags: no_photo(low)` into the rank prompt → DeepSeek reads the
machine flag and rewrites it as a sentence a person can act on. Every layer built across the
MCP, testing and live-provider blocks is visible in that one chip.

It also showed the entry-49 fix holding under a harder case: the model offered a stretch and
**labelled it as a stretch in its own concerns**, instead of the pre-fix behaviour of ranking
an extension cord for cutting metal with invented capability. Self-declared padding is a
different failure class from fabricated fit.

---

### 53. The screenshots were never the artifact

**Prompt:** Five MCP screenshots for the demo, *reproducible* — plus a `docs/mcp.md` with the
exact commands, so a grader could re-run the sequence and get the same output.

**Result:** The word doing the work was *reproducible*, and it changes the order of operations.
Capturing first and reconstructing the commands afterwards is how you end up with a shot you
can't explain in Q&A. So: write the command list, run it end to end, *then* capture.

That forced a real piece of work rather than a screenshot session. `backend/mcp_client_demo.py`
is a client that **imports nothing from Django or the service layer** — it only speaks the
protocol. That constraint is the whole point: a client that could reach into `apps.matching`
proves nothing about MCP. It splits into `connect | discover | geo | trust` so each shot is one
screen and one idea, and the numbering in its headings starts at 2 so it lines up with the
screenshot filenames, where shot 1 is the server booting alone.

**The demo inputs were chosen by querying the data, not by picking round numbers.** I ran the
service directly across candidate radii first: at (40.0, -75.0), 2 km returns one listing, 5 km
returns six and stops fitting on a slide, 3.5 km returns exactly three. Same for trust — I
checked all six nearby fixtures and took the one that trips exactly *one* rule (`Basic Claw
Hammer`, $1,450 against a $3–$150 band, `price_out_of_range` at high). An empty or overflowing
result makes a bad slide, and a listing tripping three rules makes an unexplainable one.

Two things that fell out of building it properly:

- **The client resolves `listing_id` from the `geo_search` results by title, not a hardcoded
  primary key.** A reseed shifts every id; hardcoding `378` would have made the demo rot
  silently. It also makes shots 4 and 5 *chain* — the id in the trust call visibly came from
  the search above it, which is a better story than two unrelated calls.
- **mcp 2.0's client API is snake_case throughout** — `server_info`, `protocol_version`,
  `input_schema`, `resource_templates`, `uri_template`, `structured_content`. Every camelCase
  name from the older docs `AttributeError`'d. Entry 41's lesson, second time.

`MCPServer("neighbour-node")` was also reporting `v` — `version` defaults to `""`, and nobody
had looked, because nothing until now displayed it. Set to `1.0.0`.

**The honest bit for Q&A:** under stdio a client *spawns its own server subprocess*. The server
I start by hand in shot 1 is **not** the one shots 2–5 talk to — which is why its banner
reappears at the top of each of those frames. Shot 1 still earns its place, but as proof the
entrypoint boots clean (`django.setup()` runs, imports resolve, nothing writes to stdout), not
as the process being driven. Documented in `docs/mcp.md` rather than hoped past.

**Correction:** the first five captures came back with wrapped lines — the command split as
`conne`/`ct`, and worse, `max_price` broken in half mid-parameter. Cause: font size 18 shrank
the terminal to ~57 columns. I had *asserted* the VS Code terminal would be "wider than 90
columns" instead of giving a check to run. The longest line in the demo output is 88 characters;
`$Host.UI.RawUI.WindowSize.Width` takes two seconds and belonged in the setup steps, before
capture, not in the review afterwards. I decided the wrapping was legible enough to talk over
and kept them — but the failure was mine and it was the avoidable kind: a constraint I knew
numerically, stated as a claim instead of a check.

---

### 54. Bookmarks as a template, and two bugs that don't throw

**Prompt:** Build bookmarks — but treat it as the template messaging and notifications will
copy twice, not as a feature. Decide the conventions consciously and write the checklist down.

**Result:** The framing changes the deliverable. The artifact isn't the feature, it's
`docs/api-conventions.md` — nine rules, each with its reasoning and its messaging analogue,
so tomorrow is a checklist instead of a re-derivation.

Reading the code first changed the plan twice. **An action-style
`POST /listings/{id}/bookmark/` already existed**, so this was a cutover with an ordering
constraint (retire it *after* the frontend moves, or the UI breaks mid-work), not a build.
And **the N+1 the brief warned about was already live** — `ListingSerializer` had a
`SerializerMethodField` running `.exists()` per row, so the unpaginated 47-listing page cost
48 queries. Measured after: 1.

Three decisions, made once and recorded:

- **Resource style over toggle.** A toggle races itself — two quick clicks send two POSTs
  and the second can flip state back before the first lands, with no error anywhere. Create
  and delete are separately idempotent; a toggle isn't idempotent at all.
- **404, not 403, on someone else's row** — via `get_queryset` filtering, so the "permission
  check" is the query. Worth noting this creates a *deliberate* inconsistency with
  `listings`, which 403s: a listing is a public resource whose existence isn't secret, a
  bookmark is a private row. The rule is "public resource → 403, private row → 404", and
  having the one-sentence version ready is the difference between principled and sloppy.
- **Idempotent create**, which paid off somewhere I didn't predict. During the optimistic
  window `bookmark_id` is null, because the real id only exists once the server answers. A
  second click in that window re-POSTs — and returns the same row instead of a 400. Choosing
  "reject duplicates" in the morning would have produced an error toast at 5pm.

**Two bugs that don't throw**, which is what made them worth the day:

1. **A DRF `read_only` field whose attribute is missing doesn't raise — it drops the key from
   the response entirely.** The create endpoint serializes a freshly saved instance that never
   went through `get_queryset`, so without `default=False` the response simply has no
   `is_bookmarked`, the client reads `undefined`, and `undefined` is falsy. The bookmark icon
   would render correctly *by accident*. I only found it by probing the serializer instead of
   assuming it would error like a normal missing attribute.
2. **Annotations don't survive a serializer boundary.** `BookmarkSerializer` nests
   `ListingSerializer`, whose bookmark fields come from `ListingViewSet.get_queryset` — which
   never runs on that path. Left alone, every card on My Bookmarks draws an *empty* bookmark
   icon on a page that exists only to show saved things. Both values are knowable without a
   query, so `to_representation` sets them.

**Correction:** the naive write serializer is the one an IDE writes for you.
`fields = ["id", "listing", "user", "created_at"]` is exactly what a `ModelSerializer` wants
to generate, and it lets any authenticated caller create rows on another account. Rather than
trust the test that guards it, I wrote the naive version and ran the test against it — it
failed with `<User: bob> != <User: alice>`, alice's request creating a bookmark owned by bob.
Did the same for the query-count guard (dropped `select_related`, 3 → 13 queries). Entry 44's
lesson applied deliberately for once, rather than after being burned.

Retiring the action endpoint also deleted a **permissions special-case**: `get_permissions`
existed solely to suppress `IsOwnerOrReadOnly` for bookmarking, because bookmarking is a POST
against someone else's listing. Under resource style the exception disappears — a bookmark is
your own row, so ownership is the normal case. An exception in the permission layer was a
smell about the URL shape, and I'd have read it as "bookmarks are just special".

---

### 55. Narrow but real: the fixture was the hard part, not the assertions

**Prompt:** Two test targets. Listings permissions through the endpoint — anonymous write,
non-owner write, owner, admin. And the four trust rules, each with a fixture that trips
exactly one rule, table-driven.

**Result:** 16 → 49 tests, but the work wasn't in the assertions. It was in making
"trips exactly one rule" *possible*.

Three near-identical listing factories had accumulated — one in each of the matching,
listings and bookmarks suites. The matching one carried a comment saying its defaults were
"deliberately trust-CLEAN — good description, has a photo, sane price — so a test only sees
flags it asked for". That invariant is the entire precondition for isolating a rule, and it
lived in a comment in one file, enforced by nothing. So the first move was pulling
`make_user` / `make_listing` / `CLEAN_LISTING` into `apps/core/testing.py` next to
`scripted_provider`, then collapsing all three copies onto it. Only then does
`make_listing(user, price=Decimal("1450.00"))` reliably produce exactly one flag.

I deliberately did **not** write a `make_actors()` wrapper, despite the brief asking for a
"setUp helper that makes two users and a listing". Roles differ per suite — owner/non-owner
here, sender/recipient in messaging — so three explicit lines copy better than an opaque
helper that has to be read before it can be trusted. The three lines are in the factory's
docstring.

**On testing permissions through the endpoint.** The brief's reasoning was right and worth
restating: the bugs live in routing and auth wiring, not in the permission class. A unit
test of `IsOwnerOrReadOnly.has_object_permission` would have passed throughout the period
when the endpoint was actually wide open, because the class was never attached. I checked
the real status codes by probing the live endpoint first rather than assuming — anonymous
writes are **401 not 403**, and only because `JWTAuthentication` supplies a
`WWW-Authenticate` header; DRF returns 403 when no authenticator does.

Two assertions past the brief's four, both cheap and both covering a hole the four leave:

- **`DELETE` gets its own case.** Object permissions are evaluated per request, so a rule
  proven on `PATCH` is not proven on `DELETE`.
- **A refused write must also have written nothing.** A 403 says what the response was, not
  whether the write landed first, so these `refresh_from_db()` and check.

**Two tests exist because the source documents a promise nothing enforced.** `trust.py` says
"Order is the order flags appear in a report" and calls the multi-hint title case
("Folding Camping Table" hints both furniture and sporting_goods) load-bearing. Both were
comments. Reordering `RULES` now fails exactly one test — the order one, and nothing else,
which is what tells you it's testing what it claims rather than being incidentally coupled.

**Correction to my own habit:** I broke the code deliberately for every guard this time
rather than only when something felt shaky — dropped `select_related`, removed
`IsOwnerOrReadOnly`, reordered `RULES`. Removing the permission class failed four tests and
the `subTest` label named the case: `caller='authenticated non-owner'` got 200 instead of
403. A single combined assertion would have said "403 expected" and left me to work out
which caller. Table-driven isn't just tidier; the failure message is the deliverable.

What this does **not** cover, and the README now says so: the MCP tools. `mcp_client_demo.py`
exercises them by hand, but nothing asserts on them in CI, and a hand-run demo is not a test.

---

### 56. Two read columns, because there is no participant row

**Prompt:** Messaging Block A — a named `UniqueConstraint` on `(listing, initiator)` to stop
duplicate empty threads, plus read-tracking on `Conversation`. Data migration first if
duplicates already exist.

**Result:** The duplicate check came first and took thirty seconds: **zero conversations,
zero messages**. No data migration needed, and the hardest part of the block evaporated. The
plan had budgeted for "keep the oldest row per pair, delete the rest" against a table that
turned out to be empty. Checking the data before writing the migration that assumes it is
the cheapest step in any schema change.

**The asymmetry, which is the part worth defending.** Read tracking is two nullable columns —
`initiator_last_read_at` and `lender_last_read_at` — not one. That follows from the model,
not from preference: `Conversation` stores `listing` and `initiator`, and **the second
participant is derived** (`listing.lender`). There is no participant row to hang a single
`last_read_at` on.

`NULL` means "never opened", which is a real state and genuinely distinct from "opened at
the epoch", so nullable is right rather than defaulting to a timestamp.

The correct model is a `ConversationParticipant` join table: one column, one code path, and
"who else is in this thread" stops being a derived question. It is also a mid-sprint refactor
of a model that two later blocks depend on. So: two columns, deliberately, with the cost
written down rather than discovered — **every unread calculation now branches on "am I the
initiator or the lender?"**, which means Block B's unread count cannot be the single `Exists`
annotation bookmarks used. It needs `Case`/`When` on the requesting user. That is the first
place messaging genuinely diverges from the bookmarks template, and knowing it now is worth
more than the column count.

**A verification that looked like a failure and wasn't.** `PRAGMA index_list` reported the
backing index as `sqlite_autoindex_messaging_conversation_1`, not
`unique_listing_initiator_conversation` — which reads as "the named constraint didn't
apply". It did. SQLite implements a table-level `UNIQUE` constraint inside the table
definition and auto-generates an unnamed index to enforce it; the name is in the DDL, and the
tell in `index_list` is `origin='u'` (from a constraint) versus `'c'` (a plain
`CREATE INDEX`). `PRAGMA index_info` confirmed it covers `listing_id` **and** `initiator_id`
as a pair.

Worth remembering for the Week 7 Postgres switch, where this inverts: Postgres creates a
genuinely named unique index, so a constraint that "appears" after migrating is the same
engine difference read backwards.

---

### 57. Two correct features that were jointly broken

**Prompt:** Messaging Block B — scoping helper, conversation and message endpoints with
per-participant unread counts, an idempotent thread create, a notification service with a
collapse rule, and a mark-read endpoint. Backend only, before any React.

**Result:** 54 → 99 tests. The template from bookmarks carried most of it — resource style,
404-via-scoping, owner from the request, idempotent create, annotate-don't-loop — but three
things genuinely diverged, and one bug only existed *between* two features that were each
individually correct.

**Where the bookmarks template stopped working.** `is_bookmarked` was one `Exists` because
the answer is the same shape for everyone. Unread isn't: which column holds "my last read"
depends on whether I'm the initiator or the derived lender, so it's a `Case`/`When` on the
requesting user, in its own `.annotate()` before the `Count` that consumes it. Two SQL facts
I checked rather than assumed, because both fail silently:

- **`created_at > NULL` is NULL, not true.** Without an explicit `isnull` branch a
  never-opened conversation reports **zero** unread — the exact opposite of the truth, and
  it looks entirely plausible on screen.
- **`Count` joins, `Subquery` doesn't.** Fetching the last message via a join would have
  multiplied rows against the `Count` and inflated every unread number.

**The find of the block: the collapse rule and the read endpoint are one feature.** Each was
correct alone. The collapse rule skips creating a notification when an unread one already
exists for that conversation, so five rapid messages light the bell once. Marking a thread
read stamps a timestamp. Ship both, forget to clear notifications when reading, and the
result is not a stuck badge — it is **permanent silence**: the stale unread entry suppresses
every future notification for that thread, forever. Commenting out one line made
`test_reading_lets_the_thread_notify_again` fail with `1 != 2`, and nothing else in the suite
noticed. Two features, each passing its own tests, broken by their interaction.

**Scoping writes by narrowing the field's queryset.** `MessageSerializer.get_fields` sets the
`conversation` field's queryset to the requester's own threads. A thread you aren't in then
gets rejected with the identical "object does not exist" error as an id that was never real —
non-disclosure for free, rather than a membership check afterwards that has to remember not
to leak which is which.

**A fixture hazard specific to derived participants.** My "someone else's thread" fixture had
the same user owning both listings, which made them the derived participant on both — so the
isolation test couldn't distinguish a leak from correct behaviour, and it failed on correct
code. With derived membership, a fixture meant to be *not mine* has to differ on **every path
that grants access**, not just the obvious one. Fixed with a fourth user and a comment, since
someone will otherwise "simplify" it back.

**Correction:** three bugs this block were paste-position errors, not thinking errors —
`router.register` above `router = DefaultRouter()`, a duplicated `perform_create` where the
second shadowed the first, and the `read` action pasted into the middle of `create`, which
severed `create`'s return statement and would have returned `None` from a 201. All three were
correct code in the wrong place. Two of them ran fine and would only have been caught by
`ruff` at commit time. Paste new methods at the end of a class body, not mid-method.

---

### 58. Ten minutes of tests were one line of settings

**Prompt:** Messaging Block C — write the rule-8 floor tests before the UI, add a
`make_conversation` helper, and verify each guard by breaking the code.

**Result:** All eight checks the brief listed already existed, written during Block B. Saying
so was more useful than re-writing them, and it left a real delta: the helper didn't exist,
and four guards had never actually been proven.

`make_conversation` replaced **14** inline `Conversation.objects.create(...)` sites. Its
docstring carries the thing that catches people out: you *cannot* pass the second
participant, because it's derived from `listing.lender`. The way to control who the other
party is, is to choose whose listing it is — which is exactly why a fixture meant to be
"someone else's thread" needs a different listing OWNER, not just a different initiator.

**The four guards, broken one at a time:**

| Removed | Result |
|---|---|
| the `isnull` branch in `unread_count` | `0 != 2` — a never-opened thread reads as fully read |
| `get_or_create` → `create` | `IntegrityError: UNIQUE constraint failed` |
| the self-thread validation | `201 != 400` — a lender messaging themselves |
| the recipient branch | the sender gets their own bell entry |

The second is the satisfying one: the error names `unique_listing_initiator_conversation`,
the constraint added back in Block A, proving it is load-bearing rather than decorative and
that a double-tap without `get_or_create` is a 500, not a duplicate row.

**The find of the day was not a test at all.** The suite had crept to **647 seconds** for 99
tests, and I'd been assuming that was accumulated volume. It wasn't. `make_user` — my own
helper from the earlier testing block — creates users with a real password, and Django's
default PBKDF2 hasher runs **1,200,000 iterations by design**. Three or four users per test
across fifty tests is hundreds of deliberately-expensive hashes. Overriding
`PASSWORD_HASHERS` to MD5 under the test runner took the suite to **10 seconds**: a ~65×
speedup from four lines, none of it touching production.

**Correction, and the part worth remembering:** my first version guarded on
`if "test" in sys.argv`, which is the idiom you'll find in a hundred blog posts. It is also
wrong — it matches `test` *anywhere* in the arguments, including
`createsuperuser --username test`, which would silently store a real account's password as
MD5. An optimisation whose guard is too loose stops being an optimisation and becomes a
quiet security downgrade, with no error to notice. Tightened to match the subcommand
position, `sys.argv[1:2] == ["test"]`, and verified by printing the live hasher outside a
test run: `pbkdf2_sha256`.

Worth having the one-sentence answer ready, because a panel will ask: the override applies
only when the subcommand is `test`, production and `runserver` use the real hasher, and
nothing under test asserts anything about hash strength — tests only need `check_password`
to round-trip.

The practical consequence is bigger than the number. A 10-second suite can run after every
part; a 10-minute one gets run at the end of a block, which is precisely how Block B's parts
became impossible to commit separately.

---

### 59. Three things the frontend needed that the backend didn't have

**Prompt:** Messaging Block D — hooks for conversations, messages and sending; a thread
list; a thread view with `after_id` polling and optimistic send; mark-read on open; and
"message the lender" on both listing cards and match results.

**Result:** Reading the code before writing any UI turned up three gaps, all of the same
kind — the brief assumed things that didn't exist:

1. **`ListingSummary` carried no lender.** "Hide it on your own listings" was impossible for
   match results, and the only alternative was a request per card.
2. **`AuthContext` held `{username}` and nothing else.** It assembled that from the login
   *form* and never asked the server, while everything in the API identifies people by id.
   The client literally could not answer "is this mine?".
3. **There is no listing detail page.** Cards aren't clickable, so one of the two entry
   points the brief named had nowhere to live. Put the button on the card itself.

Same shape as the "shared component library" that turned out not to exist in the screenshots
block. A brief written from the outside describes the app as it ought to be; the ten minutes
spent checking is what stops that becoming a 5pm surprise.

**The piece worth the most: `mergeMessages` got its own module, and a real test.** The
frontend has no test runner, and the polling merge is exactly the code that can't be
verified by looking at it — optimistic messages have no server id, so when the polled real
copy arrives there's nothing to match it against and both render. Pulling the pure function
out of the hook made it testable with plain `node`: 12 assertions, including *"someone else
saying the same thing does not confirm my pending copy"* and *"the confirmed message keeps
its SERVER id, not the temp one"*. A file with no dependencies on React is testable whether
or not the project has a test framework.

The dedupe is a heuristic — sender plus body — and the file says so. Send identical text
twice in quick succession and the second pending copy vanishes a beat early. The correct fix
is a client-supplied id echoed back by the API; that is a backend change and it isn't made.

**Two small things that would each have cost an hour to find later:**

- **Optimistic ids are strings on purpose.** `newestServerId` filters to integers, so a
  pending message can never push the `after_id` cursor forward past real messages that were
  never fetched — which would silently lose them, and only for the person who just sent
  something.
- **The effects key on the newest message id, not the array length.** When an optimistic
  message is swapped for its real twin the length is *unchanged*, so a length-based effect
  misses the exact moment a send lands — the scroll and the mark-read would both skip it.

**A decision paid off somewhere I hadn't predicted.** Idempotent create was chosen back in
bookmarks so a double-tapped bookmark wouldn't error. It's what lets "Message the lender" be
a single call that neither knows nor cares whether a thread already exists — no "check then
create", no race, and a double-click can't produce two conversations. Rules chosen for one
reason keep earning in places the reasoning never mentioned.

**Not verified, and worth saying plainly:** none of this has been seen in a browser. It
type-checks, builds, and the merge logic is tested, but optimistic send, polling, the badge
clearing and the match → message path have only been reasoned about. `.thread-view` also
pins the composer with `height: calc(100vh - 140px)`, where 140 is an estimate of the site
header — wrong and you get a double scrollbar or a composer off the bottom of the screen.

---

### 60. A well-reasoned decision that reasoned about the wrong thing

**Prompt (review):** the `/auth/me/` fallback has a hole — identity is fetched on the login
transition, so a reload with a stored token gives an authenticated session with `id: null`,
and the "message the lender" button then appears on your own listings. Also: don't tune the
`calc(100vh - 140px)`, delete it.

**Result:** The review was right about the mechanism and, checking it, the reality is worse
than the diagnosis. `tokenStore` is a module-level variable with no persistence at all, so a
reload doesn't produce `id: null` — **it logs you out completely.** The scenario named can't
happen yet; a different and larger demo hazard can.

That distinction mattered enough to check before implementing. The fix is the same either
way, but it moves from "repair a live bug" to "make the structure correct now so it doesn't
become one", plus a separate, larger question — should the token persist? — that shouldn't
be slipped in as part of a bug fix.

**Why the fallback was incomplete is the part worth keeping.** It wasn't careless; it
reasoned carefully about the wrong axis. The comment I wrote said: *if `/me/` fails the token
is still good, so keep the session rather than logging the user out.* Every word of that is
true. But it reasoned about **whether the token is valid**, and the actual question is
**when identity gets loaded** — and identity was tied to the login *event* rather than to
the token's existence. A decision can be sound about the thing it considered and still be
wrong because it considered the wrong thing.

Two changes:

- **Identity follows the token, not the login.** An effect on mount loads `/me/` whenever a
  token exists. Today that's a no-op, because there's never a token at boot. It costs
  nothing and it is the only version that stays correct once the token is persisted.
- **`id: null` now fails closed.** It means "identity unknown", not "not mine", and
  `MessageLenderButton` hides rather than guessing. Showing it costs a lender a 400 from the
  self-conversation guard in front of an audience; hiding it costs one unavailable button in
  a state that shouldn't arise. When the two errors aren't symmetric, pick the quiet one.

**And the CSS constant went, rather than getting tuned.** `height: calc(100vh - 140px)` was
a guess at the header's height that would break silently the next time the header changed.
Replaced with a chain that never needs to know: `#root:has(.thread-view)` caps the height —
scoped, so every other page keeps ordinary document scrolling — then flex does the rest,
with `min-height: 0` at each level because a flex item otherwise refuses to shrink below its
content and the overflow never engages. Nothing now knows how tall anything else is. The
review's framing was the useful bit: a constant that *can* be wrong is worse than a rule
that can't, even when the constant is currently right.

---

### 61. The three things ninety-nine tests couldn't tell me

**Prompt:** before anything else on Sunday — read `ACCESS_TOKEN_LIFETIME`, settle token
persistence as a written decision, set up two accounts, then actually click through the
messaging flow in two browsers.

**Result.** The lifetime is **8 hours**, already raised deliberately from SimpleJWT's
5-minute default. But the reasoning offered — *if the lifetime is generous, persistence
matters less* — doesn't hold, and saying so was the useful part. **Expiry and reload are
independent hazards.** The token died when the JS module unloaded, not when the clock ran
out, so F5 logged you out with 7 hours 59 minutes left on a perfectly valid credential. A
long lifetime does nothing about that. Two problems sharing one symptom ("suddenly logged
out") are still two problems.

**The persistence decision was settled by the test I needed to run, not by security
reasoning.** Both `sessionStorage` and `localStorage` survive a reload and both are equally
exposed to XSS — an injected script reads either, and no better than the module variable
they replace. What separates them is scope: `sessionStorage` is **per-tab**, `localStorage`
is per-origin. The entire click-through is "be a lender in one tab and a borrower in
another", and `localStorage` would have had the second login silently replace the first,
making the verification impossible to perform at all. The requirement that picked the design
came from testing, not from threat modelling. The production answer — refresh token in an
httpOnly cookie, short-lived access token in memory — is written into `tokenStore.js` as
scoped out rather than left as an implied "we know, we know".

**Two failures during the walkthrough that turned out not to be failures**, and both were
worth the minutes spent proving it:

- **Login refused with "No active account found".** Rather than reading my own recent
  `AuthContext` changes — which is where suspicion naturally goes after touching auth an
  hour earlier — I checked the server first: the user existed, was active,
  `check_password` returned True, and a real HTTP POST to `/api/auth/login/` returned 200
  with a token pair. That proved the backend, the database, the URL and the credentials
  were all fine in about ninety seconds, and left only the browser. It was a mistyped
  password.
- **The lender's Messages page was empty.** The conversation had been opened against
  listing 384, owned by a different user entirely, so the lender saw nothing because they
  genuinely weren't a participant. **The derived-participant scoping was working
  correctly**, which is exactly what it should look like from outside. The cause turned out
  to be the second result being clicked rather than the first — the ranker had put the right
  listing on top.

I had jumped to "the ranking is non-deterministic, so the demo path isn't reproducible",
which was a plausible story that happened to be wrong. The database told me *which* listing
the thread was about; it could not tell me *why* that one was chosen, and I filled the gap
with the more interesting explanation rather than the more likely one. The residual point is
smaller and duller: several near-identical drills sit within a kilometre of the search
origin, so clicking the wrong card is easy — under demo pressure, easier still.

**The verification itself.** Three behaviours were unverifiable by the suite and all three
passed: an optimistic message does not double-render when its polled twin arrives, so the
sender+body dedupe holds against real polling and not merely against twelve `node`
assertions; a reply appears in the other tab within ~5s without it being touched, which is
the only proof `after_id` polling works end to end; and "message the lender" is correctly
absent on your own listing, which needed `lender_id` and the user's `id` to both survive the
whole trip. Ninety-nine green tests said the code was internally consistent. They could not
have told me any of that.

**Fixture gap worth recording:** none of the six seeded users owned zero listings, and none
had a known password. The borrower must own **nothing**, so that a missing "message the
lender" button means a bug rather than "oh, that one's mine". `setup_demo_accounts.py`
creates the pair idempotently, so a half-finished walkthrough can be restarted rather than
untangled.

---

### 62. Reading the rows, not the model

**Prompt:** notifications API — inventory what yesterday's service actually wrote, then a
scoped list, a separate unread-count endpoint, a serializer with explicit defaults, and an
idempotent mark-read taking a list of ids.

**Result.** The inventory step earned its ten minutes by answering questions the model
diagram couldn't. The brief assumed a `recipient` field; the column is **`user`** — and
since a service has already written rows against it, the serializer had to match reality
rather than the plan. It also assumed a `kind` discriminator might be missing: `type` exists
with three choices, of which **only `new_message` has ever been written**. `new_match` and
`bookmark_update` are declared and dead.

That last fact changed a design decision. A serializer that switches on `type` will
eventually meet a row written by newer code, so `render_text()` returns a bland fallback
instead of raising. **A bell that 500s because someone added an enum value is worse than one
that says "You have a new notification".** Same reasoning for the payload: every lookup has
a fallback, because `payload` is schemaless and one malformed row shouldn't take down the
whole dropdown.

**The Day 9 trap reappeared in a new costume**, and this time the demonstration was
unusually clean. Both routing ids are read straight out of the JSON with
`source="payload.conversation_id"`. Dropping the `default=None` from one of them produced:

```
{'id': 1, 'type': 'new_message', 'listing_id': None, 'is_read': False, ...}
```

`listing_id` kept its default and reports `null`; `conversation_id` is simply **gone** —
both in the same response, one line of code apart. A schemaless payload makes this far more
likely than a missing annotation did: any row written before a key existed silently loses
the field, the client reads `undefined`, the click routes nowhere, and nothing errors
anywhere.

**Splitting the count from the list was the performance decision, and the test is what
protects it.** The badge polls every ten seconds, on every page, forever. Reusing the list
endpoint would ship twenty serialized rows — each with a rendered sentence and a payload —
so a client can render one digit. `unread_count` is a single `COUNT(*)` with no serializer
involved, and its response deliberately has **no `results` key**; a test asserts
`set(payload) == {"unread"}`, which fails the moment anyone folds rows back in. Guarding the
shape is what stops the optimisation being undone by a well-meaning refactor.

**Three details in `mark_read` that only look fussy until they bite:**

- Someone else's id is **ignored, not rejected** — the update runs against `get_queryset()`,
  so it matches nothing. A 404 would confirm the row exists.
- Already-read rows are filtered out *before* the `UPDATE`, so re-sending ids reports
  `marked: 0`. Idempotent by construction rather than by catching an error.
- **`bool` is excluded from id coercion.** `True` is an `int` subclass in Python, so `[True]`
  would have quietly become id `1` and marked a real notification read — invisible from
  outside, and untraceable from the symptom.

Breaking the scoping — one word, `self.get_queryset()` to `Notification.objects` — failed
with `1 != 0`: Alice marking Bob's notification read, clearing a badge on an account she
cannot see. The most damaging thing this endpoint could do, one identifier away.

**Correction, on communication rather than code.** My summary listed those behaviours under
"Three behaviours worth knowing" and the verification under "The guard, proven", and both
were read as defect reports needing fixing. They were the opposite — deliberate design, and
a test proving itself. Describing correct behaviour in the same register as a bug list is a
writing failure, not a reading one: a section that opens with a broken assertion needs to say
it was deliberate and already reverted, in the heading.

---

### 63. The second trigger, and a test that only fails for one reason

**Prompt:** notifications fire on two triggers. The message one exists; the match one needs
deciding first. Then the bell, then the tests — interleaved, not batched.

**The decision, which was the interesting part.** "A search returned new matches" sounds
like it notifies the searcher, and that is useless: they are looking at the results. The
value is the other direction — **tell the LENDER their listing ranked into someone's
search**. "Your drill matched a request 1km away" is behaviour a lender would act on, it
demos well, and it needs no saved-search feature to exist. Getting that backwards would
have produced a technically-working feature nobody has a reason to open.

It also caught a bug I had already written. Yesterday's serializer rendered `new_match` as
*"New matches for your search"* — the borrower's sentence, written before the direction was
settled. Under the lender-side decision that string is addressed to the wrong person
entirely. The sentence is now "Cordless Drill matched a nearby request".

**Three guards, each for a failure I could name:**

- **Never notify the searcher about their own listing.** The seed data is full of
  near-duplicates, so searching for something resembling your own item is common.
- **Cap at the top few ranked results**, not the candidate set. The signal is "yours
  ranked", not "yours was retrieved" — the whole set would light a dozen bells for listings
  nobody looked at.
- **Collapse per (owner, listing) within a window.** Demo searches repeat the same query
  minutes apart. Without this a lender's bell reads "20" by lunchtime and means nothing.
  Deliberately per *listing*, not per owner: one lender with two matching items should hear
  about both.

The collapse check is a single SELECT covering every owner in the batch rather than one per
listing, because this runs inside a request whose latency gets watched live. Measured after
wiring, as the brief asked: **6.5ms cold** writing three rows, **1ms warm** when the guard
suppresses everything, against LLM calls of 800–3000ms. Under one percent of a match.

**The test worth keeping is the one about the seam, not the logic.** Eleven tests already
proved `notify_listings_matched` behaves correctly — guards, collapse, cap, payload shape,
query count. **Every one of them would keep passing if the call were deleted from
`rank_candidates`.** So there is a separate test that runs a real ranking and asserts a
notification appeared. Removing that one line produced exactly one failure out of 62, with
the service suite entirely green: the clearest possible statement that the code works and is
never reached.

Its sibling matters too: `rank_candidates` without a `searcher` must notify nobody. Every
other test in that suite calls it that way, so if the default ever changed, the whole file
would start writing rows as a side effect of testing something else — passing, and quietly
wrong.

**A gap the frontend forced.** Match notifications route to a listing, and there was no
listing page — cards render in grids and aren't clickable. The brief's warning was exact: *a
dead link in a dropdown is the kind of thing that gets clicked accidentally during a live
demo*. So `/listings/:id` exists now, reusing `MessageLenderButton` rather than restating
the hidden-on-your-own-listings rule. The bell also renders a row with no destination as
plain text rather than a link, because a payload can legitimately lack an id.

**What the client does NOT own: the sentence.** The kind map holds an icon and a route, and
`text` comes from the server. Duplicating the wording client-side is how a bell and a
notifications page end up disagreeing about what happened.

**Unverified, and worth saying plainly:** the bell has not been opened in a browser. It
builds and lints, the API beneath it has 137 passing tests, but the badge clearing, the
dropdown's click-away, and both link destinations are reasoned about rather than seen.

---

### 64. Eleven points of flattery

**Prompt:** install coverage with branch coverage on, omit only migrations, settings,
entrypoints, tests and the venv — *nothing else* — record the baseline before writing
anything, and read the report by missed lines rather than by percentage.

**Result: 75%, then 64%.** The first number was mine and it was wrong.

I omitted three extra files — `setup_demo_accounts.py`, `fill_demo_thread.py`,
`mcp_client_demo.py` — on the reasoning that they are hand-run developer tooling with no
importable behaviour, would sit at 0% forever, and would understate coverage of the code
that actually ships. Every clause of that is true. It is also exactly the move the brief
named in advance: *omitting a module to lift the number is the thing you don't want to
explain on Friday.*

What changed my mind wasn't that the reasoning was wrong, but that **it needed reasoning at
all**. "We omitted migrations, settings, entrypoints, tests and the venv" is a sentence that
ends. Anything past that invites the next question, and the next question is what *else*
was excluded. The three files cost **eleven points** — 165 statements at zero — and buying
eleven points with an argument you have to make is a bad trade when someone can open
`.coveragerc` and read the list themselves.

**What the report said, versus what I would have guessed.** The point of measuring first is
that intuition is stale, and mine was:

- **`matching/views.py` sits at 23%** — lines 26–70, essentially the whole `post()` method.
  That is `POST /api/match/`, the AI feature the entire demo is built on, and **nothing
  exercises it over HTTP**. All sixteen matching tests call the services directly.
- **`messaging/views.py` and `notifications/views.py` are at 100%** — because those got HTTP
  tests when they were built. The contrast is in the same report, two rows apart. Yesterday's
  lesson about testing the seam rather than the logic, restated as a number.
- `listings/views.py` 78–97 is the photo-extraction endpoint: same shape, same gap.

**What branch coverage bought, concretely.** `IsOwnerOrReadOnly` reports as covered under
statement coverage. Branch coverage shows line 17 —
`if not request.user or not request.user.is_authenticated` — has only ever gone one way. It
never fires, because DRF's authentication returns 401 before object permissions are
consulted. So it is either dead code or an untested safety net, and no amount of statement
coverage would have raised the question.

**The trap sitting in plain sight.** A dozen modules show exactly one missed line, all of
them `__str__` on a model. Covering them is trivial, would lift the total by a couple of
points, and would test nothing anyone could care about. The cheapest lines to cover are
reliably the ones least worth covering, and a coverage number is only useful while you are
still refusing to chase them.

**One honest framing worth keeping for Friday:** 306 of the 416 missed statements are
hand-run tooling — the MCP client demo, the MCP server, `seed_data`, the two demo scripts.
So 64% is depressed mostly by scripts, not by untested product logic. That is true, it is
checkable from the report, and it is a much better thing to say than a number with a
footnote about what was excluded.

---

### 65. Aiming at the report, and one test that outlived its reason

**Prompt:** close the coverage gaps in a stated order — HTTP end-to-end first, then provider
selection, the MCP server through its protocol, a call-site audit, permissions, and two
Postgres-facing tests.

**Result: product coverage 78% → 91%, overall 64% → 76%, 137 → 169 tests.** The ordering
was the useful part, and it came from the report rather than from instinct.

**One artifact fixed the two worst files.** A single signup → login → photo-to-draft →
create → search journey took `matching/views.py` from 23% to 74% and `listings/views.py`
from 65% to 85%. Both had well-tested service layers and untested endpoints — the same seam
problem as entry 63, showing up as two numbers in a table instead of as a bug. It uses a
real bearer token rather than `force_authenticate`, because the latter skips the JWT layer,
which is where a client's problems actually live.

**Testing the MCP server meant testing the protocol, not the functions.** `geo_search` and
`trust_check` are thin adapters over already-covered services; calling them directly would
have proved nothing new. What was untested was everything between a client and that logic —
tool registration, the JSON schema derived from each signature, argument validation, the
response shape. The library's in-memory transport gives all of that without spawning a
subprocess. Two things that would have cost an hour cold: it needs `TransactionTestCase`,
because sync tools dispatch on worker threads and `TestCase`'s wrapping transaction makes
every fixture invisible to them; and the discovery test — *both tools and the resource are
advertised* — is the Phase 3 deliverable restated as an assertion, failing if a decorator is
deleted.

**The call-site audit found nothing, which was the finding.** Seven seams removed one at a
time: four trust rules, the cache read, the cache write, the annotator seam. Every one
produced failures, and the trust-rule failures named themselves through `subTest` labels —
`rule='price far outside its band'`. The cache was the exception worth noting: **removing
the read and removing the write produce identical failures**, the same two tests with the
same messages. Both are caught, so it is not a coverage gap; it is a *diagnostic* one, and
it makes the case for table-driven tests better than an argument could — the trust rules
tell you which rule broke, the cache makes you bisect.

**A dead branch, deleted rather than covered.** Branch coverage showed `IsOwnerOrReadOnly`'s
anonymous check had only ever evaluated one way. It is unreachable: the class is only ever
composed with `IsAuthenticatedOrReadOnly`, so an anonymous write 401s before object
permissions run, and an anonymous read returns at the `SAFE_METHODS` line above. Statement
coverage reported that file as green. The comment now records the composition that made it
dead, so the check comes back if anyone pairs the class with `AllowAny`.

**The re-evaluation worth keeping.** Two tests were planned as Postgres insurance: one
pinning the JSONField collapse lookup, one pinning numeric precision. After the Postgres
move was cancelled I kept both, and that was wrong on the first. The collapse behaviour is
already asserted by eleven notifier tests from entry 63 — writing a second version of it was
duplicate coverage dressed as diligence, justified by a migration that is no longer
happening. **Deleted it.** The precision test was kept, and not because it survived a
cull: it was never really about Postgres. `distance_km` and the daily rate are rendered
verbatim on a match card, so a coercion bug shows up as `1.4177446878757824 km away` in
front of an audience. Rewritten to assert through the HTTP response rather than the model,
which is where the Haversine tests cannot see.

That rewrite found something. The match response builds `ListingSummary` with **pydantic**,
while `/api/listings/` uses **DRF** — two independent serialization paths for the same
price. They both produce `"3.00"`, and that agreement was an assumption until it became an
assertion.

**Correction:** the coverage config omitted `*/tests.py` but not `*/test_*.py`, so
`test_mcp.py` and the portability module were being measured as product code. Every figure
quoted before that fix was mildly wrong in an unhelpful direction — test files with partial
execution dragging the total. Fixed; the corrected numbers are the ones above.

---

### 66. Writing down what the number doesn't say

**Prompt:** capture the artifacts — both coverage figures with the exclusion named in
words, the test composition while it's fresh, the call-site finding as a reflection
paragraph, and the SQLite decision written twice: operational in the README, reasoning in
the reflection doc.

**Result.** Four documents rather than four numbers, and the writing forced two things into
the open that the measuring had not.

**Reach is not dependence, and that is the whole finding.** Coverage answers "was this line
executed". It cannot answer "does anything rely on this line being here". Eleven tests
covered `notify_listings_matched` — guards, cap, collapse window, payload, query count — and
**every one passed with the call deleted from `rank_candidates`**. A perfect, unreachable
service, green throughout, because the tests called the function directly. That is the third
piece of testing-discipline evidence, and the strongest, because unlike the two prompt bugs
it is about my own process rather than the model's.

The fix is a test that exercises the *call site* rather than the function. It fails for
exactly one reason, and it is the reason nothing else can see.

**Composition had to be written today or reconstructed wrongly on Wednesday.** 169 backend
tests split roughly 62 service-level, 92 API integration, 13 MCP protocol, 1 end-to-end
journey; 16 frontend logic tests. Nobody remembers that ratio at 6pm, and deriving it from
the file tree is both slow and quietly inaccurate — several files hold both kinds.

**The SQLite decision needed two documents, not one.** The README wants the operational
facts: single node, volume-mounted, WAL, one worker. The reflection doc wants the reasoning —
that Postgres was cancelled under deadline, and what specifically would have to change. Two
things, both checked rather than assumed: the notification collapse filter depends on
SQLite's `json_extract()` semantics, and the extraction cache is `LocMemCache`, which is
**per-process** — a second worker halves the hit rate and every miss is a paid vision call.
That last one fails as a bill rather than as an error, which is why it is written down.

There is a third, smaller one worth having: the collapse rule is an `exists()` followed by a
`create()`, so simultaneous messages could both slip through. The real fix is a partial
unique index, which **Postgres has and SQLite does not**. At one writer it cannot happen.
Naming the concurrency assumption is what turns a shortcut into a scoped decision.

**Two things the writing surfaced that the measuring missed.**

First, **entry 59 was wrong**. It claimed `mergeMessages` had "twelve assertions run by
plain node" — I ran them in a scratch file and never committed one. The claim had been sitting
in the reflection doc for two days describing tests that did not exist. Now it does: sixteen
frontend tests via `node:test`, no framework, no mocking, including the case that matters
most — *someone else saying the same thing must not confirm my pending message*.

Second, **Week 1's three component tests were never in this repo at all.** Not deleted by
nine days of refactoring, as I half-expected: nothing test-shaped appears anywhere in the
git history. The honest position is that frontend testing was scoped to pure logic in favour
of API coverage, which is defensible. Silence about it would not have been.

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
- **DRF authenticates before it checks permissions.** A stale or malformed token 401s an
  `AllowAny` endpoint, because permissions never get to run. This one rule explains the signup
  bug, why SimpleJWT's login view was immune, and why `IsAuthenticatedOrReadOnly` alone left
  writes unguarded.
- **Changing the content type changes the parsing rules.** Moving create from JSON to
  multipart silently flipped `is_available` to `False`, because DRF treats an absent boolean
  in HTML-form input as an unchecked checkbox. Same endpoint, same fields, different default.
- **Verify the paths a change could break, not just the path it fixes.** Adding the ownership
  permission would have 403'd every bookmark — the failing case was the one that looked
  unrelated. Every fix since gets tested against the features around it.
- **Django's autoreloader is not reliable here.** Several fixes appeared not to work because
  the running process still held old bytecode. Worse, Django's 500 page reads source files
  *fresh from disk*, so the traceback displays the new code while executing the old — the
  page's source listing is not evidence of what's running. Restart `runserver` after backend
  edits.
- **An unhandled library exception becomes a 500.** DRF only converts `APIException`,
  `Http404` and `PermissionDenied`; anything else propagates to Django. Third-party errors
  (`UnidentifiedImageError`) need catching and re-raising as a typed error the view can map to
  a real status code.
- **pre-commit loops forever if `git add` misses a file the hooks fixed.** The hooks run
  against *staged* content, fix the working tree, then abort. Staging only part of the change
  next time re-stages the same unfixed file, so the hook fixes it again and aborts again — I
  went three rounds before spotting it. After an abort, `git status --short` and stage
  everything showing `MM`. Two commits had silently never landed by the time I checked.
- **Run the README's own setup from a fresh clone.** Cloning into a temp directory and
  following my own instructions caught `.env.example` being untracked — the `cp .env.example
  .env` step I'd just documented would have failed for anyone but me. Nothing else in the
  setup, including the full `requirements.txt` install, was wrong; the one gap was invisible
  from inside a working tree.
- **n=1 is not evidence with a non-deterministic system.** Identical input flipped between a
  match and an empty result about a quarter of the time. Any prompt change judged on one
  before/after run is judged on noise. Runs are cheap; conclusions drawn from one aren't.
- **"Permitted" is not "correct".** The rank prompt said to leave out listings that don't fit,
  and the model padded anyway. It stopped once returning nothing was named as the *right*
  answer rather than an allowed one. Models optimise toward what you frame as success.
- **Fluent and wrong is more dangerous than vague and wrong.** An extension cord ranked for
  cutting metal pipes, with a plausible-sounding rationale, reads as competent right up until
  someone checks. Weak output announces itself; confident fabrication doesn't.
- **One live provider can't tell you which behaviours are general.** "The model ignores the
  no-fences instruction" was true of Haiku and false of DeepSeek. Everything learned from a
  single model is a hypothesis about that model.
- **Say what a number means.** `suggested_price: a number in USD` produced resale values in
  a lending marketplace, three times out of three. The model wasn't wrong; the prompt never
  said what it was pricing. Every ambiguous field in a prompt gets resolved by the model's
  priors, and its priors are not your product.
- **An instruction the model ignores is a finding, not a bug to argue with.** Six of six
  responses arrived fenced despite an explicit instruction not to. The right response was to
  record that the defensive parser is load-bearing, not to escalate the wording.
- **The stub proves the plumbing, never the output.** Fencing rate, retry rate, and whether
  the values mean anything are all invisible until a real model answers. Everything the stub
  validated stayed valid; everything it couldn't see was wrong.
- **Ask what a green test would look like if the code were broken.** Two of the four cache
  tests would have passed with the provider never called, because `LocMemCache` survives
  between tests and the first two share a key. A test that passes without executing the code
  under test is worse than no test — it reports coverage it doesn't have.
- **Check the brief against the code before writing to it.** "Test the radius widening" and
  "the three seeded awkward cases are your fixtures" both described a codebase that didn't
  exist yet. Reading the source first turned two hours of confused test-writing into fifteen
  minutes of implementation.
- **Patch where a name is used, not where it's defined.** `from x import y` binds `y` into
  the importing module at import time; patching `x.y` afterwards has no effect on it.
- **Build the fixtures before the rules that read them.** Every trust rule looked fine in
  isolation; two were worthless against the actual data — one fired on 100% of rows, one on
  80% as pure seed artifact. Neither is visible from reading the rule. Check what a new
  detector *actually* flags across the whole table before trusting a passing spot-check.
- **A guard can look like formatting.** `str(query.max_price)` in a trace call read as
  cosmetic; it was the only thing keeping a `Decimal` out of a `JSONField`. Moving code past
  something you don't recognise deletes it silently. When a refactor relocates a call, read
  what the original was doing to its arguments, not just where it went.
- **Verify the library you have, not the one you remember.** mcp 2.0 renamed `FastMCP` and
  changed how sync tools are dispatched, which invalidated both the import and a workaround I'd
  planned for an error that can no longer occur. Two minutes inspecting the installed package
  replaced two assumptions.
- **A model string is not a model decision.** The provider named Opus while `MAX_IMAGE_DIM`
  was tuned for a cheaper tier and the call skeleton carried settings that contradicted both.
  Nothing errored, because none of it had ever run. Unexecuted code drifts silently — the
  README forced the inconsistency into the open by making me write down *why* the model was
  chosen.
- **A constraint you know numerically should be written as a check, not a claim.** I knew the
  demo output's longest line was 88 characters and still wrote "the terminal will be wider than
  90 columns" instead of `$Host.UI.RawUI.WindowSize.Width` → needs ≥ 95. The number was in my
  hands and I spent it on an assertion. Wrapped screenshots were the result.
- **Pick demo inputs by querying the data, not by choosing round numbers.** A 5 km radius looks
  more natural than 3.5 km and returns twice as much as fits on a slide. Every fixed input in a
  demo — radius, id, threshold — should be the output of a query you ran, and the reason should
  be written down next to it.
- **A demo that reaches past the interface proves nothing about the interface.** The MCP client
  had to import nothing from Django, or "the tools work over the protocol" would have been an
  untested claim dressed as a screenshot. What a demo is *forbidden* to touch is what makes it
  evidence.
- **Ask whether a missing value throws or vanishes.** A DRF `read_only` field with no attribute
  behind it drops its key from the response instead of raising, and the client reads `undefined`
  — falsy, plausible, silent. I'd assumed it would error, because that's what a missing
  attribute normally does. Whenever a value might be absent, find out which of the two failure
  modes the library picked; only one of them tells you.
- **Write the broken version and run the test against it.** Stronger than asking what a green
  test would look like if the code were broken (entry 44) — actually make the code broken. The
  owner-spoofing test and the query-count guard both looked obviously correct and I only *knew*
  they worked after watching them fail. Two minutes each, and it's the only thing separating a
  test from a comment.
- **An exception in the permission layer is usually a smell about the URL shape.**
  `get_permissions` existed only to suppress the ownership check for bookmarking — because
  bookmarking is a POST against someone else's listing. Moving to a resource where the row is
  your own deleted the exception outright. A carve-out that reads as "this endpoint is just
  special" is worth one question: special compared to what shape?
- **A test fixture's invariant belongs in code, not in a comment above it.** "Defaults are
  deliberately trust-CLEAN so a test only sees flags it asked for" was true, important, and
  enforced by nothing — sitting above one of three copies of the same factory. Isolating a
  single rule is impossible until that invariant is shared and named. The fixture was the
  hard part of the testing day; the assertions took minutes.
- **Test the wiring, not the unit, when the unit is a policy class.** A passing unit test of
  `IsOwnerOrReadOnly.has_object_permission` proves the logic is right and says nothing about
  whether it is *attached*. The real bug was a missing entry in `permission_classes`, which
  only an endpoint test can see. Same for `DELETE`: permissions are evaluated per request, so
  a rule proven on `PATCH` is not proven on `DELETE`.
- **The failure message is the deliverable.** Table-driven with `subTest` reported
  `caller='authenticated non-owner'` got 200 instead of 403 — the broken case named itself.
  The same four assertions merged into one test would have said "403 expected" and left me
  bisecting. Choose the test shape by what it says when it fails, not by what it looks like
  when it passes.
- **A refused request must also be a request that did nothing.** A 403 describes the
  response, not whether the write landed before the check. Asserting the status code alone
  leaves the actual question — did the row change? — untested.
- **Query the data before writing the migration that assumes it.** A whole data-migration
  step — dedupe, keep the oldest per pair — was planned against a table holding zero rows.
  Thirty seconds of `select count(*)` deleted the hardest task in the block. The check is
  always cheaper than the migration it might cancel.
- **Know how your database renders what you asked for.** SQLite reported my named unique
  constraint as `sqlite_autoindex_..._1`, which reads exactly like the name not having
  applied. It had — the name lives in the table DDL, and `origin='u'` in `PRAGMA index_list`
  is the tell. A verification you can't interpret is worse than none, because it invites you
  to "fix" something that was already right.
- **Write down the cost of the shortcut, in the same hour you take it.** Two
  `last_read_at` columns instead of a participant table is defensible under a deadline;
  what makes it defensible rather than sloppy is naming the consequence — every unread
  calculation now branches on which participant is asking. Stated now it's a trade-off.
  Discovered in two days' time it's a surprise.
- **Two features can each be correct and still be broken together.** The notification
  collapse rule and the mark-read endpoint both passed their own tests; shipping them
  without clearing notifications on read produced permanent silence, not a stuck badge.
  Unit-correct is not integration-correct. When one feature's behaviour is *conditional on
  another feature's state*, the test that matters is the one that runs both in sequence.
- **Scope the choices, don't check the answer.** Narrowing a serializer field's queryset to
  what the requester may reference rejects "not yours" with the same error as "doesn't
  exist" — the non-disclosure comes free. A membership check performed afterwards has to
  remember to return the right status *and* the right message, and one of those gets it
  wrong eventually.
- **A "not mine" fixture must differ on every path that grants access.** With a derived
  participant, changing the initiator isn't enough — the listing owner grants access too.
  My isolation fixture shared an owner, so it failed against correct code and would have
  passed against a leak. A fixture that can't distinguish those two is worse than none.
- **A slow test suite is usually one expensive thing repeated, not a lot of work.** I'd
  written off 647 seconds as accumulated volume. It was password hashing — PBKDF2 at 1.2
  million iterations, several users per test. Measure what the time is actually going into
  before accepting that a suite is "just big"; the answer is often a single line.
- **A guard that's too loose turns an optimisation into a vulnerability.**
  `if "test" in sys.argv` matches `createsuperuser --username test` and would store a real
  password with a deliberately weak hasher — silently, with no error. When a condition
  switches off a safety property, match it precisely (`sys.argv[1:2] == ["test"]`) and then
  go and *print the live value* outside that condition to prove it.
- **When a brief asks for work already done, say so and deliver the difference.**
  Re-writing eight tests that already existed would have looked like effort and produced
  nothing. Mapping them to what was there took minutes and exposed the actual gap: a
  missing helper and four guards nobody had ever proven.
- **No test runner is not the same as untestable.** The trickiest frontend logic in the
  project — merging polled messages against optimistic ones — became twelve assertions run
  by plain `node`, purely by moving the pure function out of the hook that used it. If a
  piece of logic is hard to be sure about by reading, that is the argument for extracting
  it, not for writing a longer comment.
- **Set a load-bearing default explicitly.** `refetchIntervalInBackground` already defaults
  to `false`, which is what stops a poll running in a hidden tab. Relying on that means a
  library upgrade can change behaviour with nothing in the diff to review. Write down the
  values you are depending on, especially the ones you agree with.
- **A rule chosen for one reason keeps earning in places the reasoning never mentioned.**
  Idempotent create existed so a double-tapped bookmark wouldn't 400. It is also why
  "message the lender" is one call instead of check-then-create, why a double-click can't
  make two threads, and why the button needs no knowledge of whether a conversation exists.
  Good constraints compound; that is the argument for deciding them deliberately rather
  than per feature.
- **Check which axis a decision reasoned about, not just whether its reasoning was sound.**
  "The token is still valid, so keep the session" was entirely true and still produced a
  bug, because the question was never token validity — it was *when identity loads*. A
  justification that survives scrutiny can still be answering a question nobody asked.
- **Tie state to the thing it depends on, not to the event that first produced it.**
  Identity depends on having a token, so it must load whenever a token exists. Hanging it
  off the login transition worked only because nothing yet survived a reload.
- **When two failure modes aren't symmetric, fail toward the quiet one.** Unknown identity
  could show the button (a visible 400 in front of an audience) or hide it (one missing
  button in a state that shouldn't occur). "I can't tell" must never be treated as "no".
- **A constant that can be wrong is worse than a rule that can't.** `calc(100vh - 140px)`
  encoded the header's height in a place that would never be updated with it. The fix
  wasn't a better number — it was an arrangement where no number is needed.
- **Two hazards sharing one symptom are still two hazards.** "Suddenly logged out" was
  both token expiry and token loss on reload, and fixing the lifetime addressed only one.
  When a fix "should have" solved something and didn't, check whether the symptom had a
  second cause rather than assuming the fix was wrong.
- **Prove what the server does before debugging the client.** After touching auth an hour
  earlier, a login failure looked like my bug. Ninety seconds — user exists, `is_active`,
  `check_password` True, a real HTTP POST returning 200 — eliminated the entire backend and
  left only the browser. Suspicion naturally lands on whatever you touched most recently,
  which is exactly why it needs evidence.
- **Let the test you have to run inform the design.** `sessionStorage` over `localStorage`
  wasn't chosen on security grounds — they're equivalent there. It was chosen because
  per-tab scoping is what makes "lender in one tab, borrower in another" possible at all.
  A design that can't be exercised is a design that won't be verified.
- **Correct behaviour can look exactly like a bug from outside.** An empty inbox was the
  scoping working — the user genuinely wasn't a participant. Before debugging, check
  whether the data actually matches the scenario you think you're testing.
- **Don't infer a cause the evidence doesn't reach.** The database showed which listing a
  thread belonged to, and I concluded the ranker had misordered results — a tidy story that
  explained the symptom and was false. It was a misclick. Evidence that narrows *what*
  happened rarely establishes *why*, and the interesting explanation is the one to distrust
  first.
- **Read the rows, not the model.** The field was `user`, not the `recipient` the plan
  assumed; two of three declared types had never been written. A service that has already
  populated a table has settled questions the schema only gestures at, and the code being
  written next has to match what's there.
- **A schemaless column needs a fallback at every read.** `payload` is JSON, so any row
  written before a key existed loses that field silently — DRF drops it rather than
  raising, and the client reads `undefined`. Where a strict column would have failed
  loudly, JSON just gets quieter.
- **Protect an optimisation with a test on its shape, not just its speed.** Splitting the
  unread count out of the list only stays split if something fails when they merge again.
  Asserting the response has exactly one key does that; asserting it is "fast" would not.
- **Beware `bool` wherever ids are coerced.** `isinstance(True, int)` is `True` in Python,
  so `int(True) == 1` and a stray boolean silently addresses row 1. Any `int()` over
  client-supplied data wants a bool guard.
- **Describing correct behaviour in the register of a bug list reads as a bug list.**
  Sections headed "worth knowing" and "the guard, proven" were taken as defects to fix.
  When a summary mentions a broken assertion, the heading itself has to carry that it was
  deliberate and already reverted.
- **Test the seam separately from the logic it connects.** Eleven tests proved the match
  notifier behaved; all eleven would have passed with the call deleted from the ranker.
  A test that exercises the *call site* fails for exactly one reason, and it is the reason
  no other test can see.
- **Decide the direction of a notification before building it.** "A search found matches"
  reads as news for the searcher, who is already looking at the results. The value was
  entirely on the other side. A feature can be correct, tested and pointless if the
  audience was chosen by grammar rather than by asking who would act on it.
- **A string written before a decision outlives the decision.** The `new_match` sentence
  was drafted borrower-side and survived into a lender-side feature, addressed to the wrong
  person. When a direction is settled, grep for the copy written under the old assumption.
- **A link with no destination should render as text.** Payload ids can legitimately be
  absent, and a dropdown row that looks clickable and goes nowhere gets clicked — most
  likely by someone demonstrating the product to a room.
- **An exclusion that needs an argument costs more than the points it buys.** Omitting three
  hand-run scripts from coverage was defensible and I could defend it — which is the
  problem. A list that ends at "migrations, settings, entrypoints, tests, venv" needs no
  defending at all. Eleven points is a cheap price for a number nobody has to interrogate.
- **Measure before deciding where to aim.** I would have guessed the untested code was the
  MCP tools. It was the match endpoint — the flagship feature, at 23%, while the two
  viewsets built last week sat at 100%. Two days is long enough for intuition about your own
  codebase to go stale.
- **Branch coverage finds the guard that never fires.** A permission check reported as fully
  covered had only ever evaluated one way, because DRF returns 401 before object permissions
  run. Statement coverage cannot ask that question, and guards are precisely where the
  unexercised side is the one that matters.
- **The cheapest lines to cover are the ones least worth covering.** A dozen modules were one
  line short of 100%, every one a model's `__str__`. A coverage number stays useful only
  while you are still willing to leave those red.
- **When the reason for a test disappears, re-read the test.** Two were written as Postgres
  insurance. When the migration was cancelled I kept both out of momentum; one was already
  covered elsewhere and had to go, the other turned out never to have been about Postgres at
  all. Cancelled work leaves artefacts behind, and "we already wrote it" is not a reason to
  keep something.
- **Assert where the value is read, not where it is computed.** The Haversine tests check the
  distance; only an HTTP-level test can see whether it survives serialization as a number
  rounded to the places the card displays. A value is correct at the point of use or it isn't
  correct.
- **Two serializers for one field is two contracts.** The match response uses pydantic and
  the listings endpoint uses DRF, for the same price. They agree — which was an assumption
  until something asserted it, and assumptions about parallel code paths are the ones that
  drift.
- **Check that a coverage config excludes what you think it does.** `*/tests.py` does not
  match `test_mcp.py`. Test files were being measured as product code and quietly moving the
  number. A measurement tool needs its own sanity check before its output is quoted.
- **Coverage measures reach, never dependence.** Eleven green tests around a service that
  nothing called. "Was this executed" and "does anything rely on this" are different
  questions, and only the second one is about whether the feature works.
- **Write the composition down the day you build it.** Which tests are unit and which are
  integration is obvious while writing them and guesswork a week later — several files hold
  both. Reconstructing it from a file tree is slow and quietly wrong.
- **A shortcut becomes a judgement call the moment you write down what would have to
  change.** SQLite in production is indefensible as "we ran out of time" and entirely
  defensible as "one writer, one node, and here are the two things that break at scale" —
  same decision, different amount of thinking made visible.
- **A claim in a reflection doc is a claim about the repo.** Entry 59 described twelve
  frontend assertions that were run once in a scratch file and never committed. Documenting
  work is not the same as landing it, and the doc had been wrong for two days.

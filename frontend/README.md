# Neighbour Node — frontend

React 19 SPA for the Neighbour Node lending marketplace. Browse listings, draft one from a
photo, search in plain English, bookmark, and message a lender.

Project-level documentation — architecture, API conventions, decisions — lives in the
[root README](../README.md). This file covers running and building *this* package.

---

## Running it

**With the rest of the stack (what the demo runs):**

```bash
cd ..
docker compose up --build      # http://localhost:8080
```

nginx serves the built bundle and proxies `/api`, `/media`, `/static` and `/admin` to
gunicorn. One origin, so there is no CORS configuration to keep in sync.

**On its own, against a local backend:**

```bash
npm install
npm run dev                    # http://localhost:5173
```

The dev server needs a backend on `http://localhost:8000` and `VITE_API_BASE_URL` set to
match — see below. This is the only mode where the two origins differ, which is why
`django-cors-headers` exists in the backend.

| Script | Does |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Production bundle into `dist/` |
| `npm run preview` | Serve the built bundle locally |
| `npm run lint` | ESLint over the whole package — exits zero |
| `npm test` | Node's built-in test runner over `src/**/*.test.js` |

---

## `VITE_API_BASE_URL` is a build argument, not an environment variable

Vite substitutes `import.meta.env.*` at **build** time — the value is baked into the bundle
as a string literal. Setting it in docker-compose `environment:` does nothing, because by
then the bundle is already built. It is passed as a Docker build arg instead, defaulting to
`/api` (see [`Dockerfile`](Dockerfile) and the `args:` block in
[`docker-compose.yml`](../docker-compose.yml)).

`mediaUrl()` in [`src/api/client.js`](src/api/client.js) derives `/media/` from the same
value, so listing photos stay same-origin too.

---

## Layout

```
src/
  api/         axios client + JWT token store
  components/  Layout, ListingCard, MessageLenderButton, NotificationBell
  context/     AuthContext (the context) · AuthProvider (the component) · useAuth (the hook)
  hooks/       one TanStack Query hook per resource, plus query-key modules
  pages/       route components
  utils/
```

**Why `context/` is three files.** `react-refresh` requires a module to export components
or non-components, never both — mixing them breaks Fast Refresh, because the bundler cannot
tell whether a changed export is hot-swappable or needs a full remount. Holding the context,
its provider and its hook in one file exports all three kinds at once, so they are split.

State is TanStack Query for anything server-owned and `useState` for the rest. There is no
Redux layer because caching, refetching and loading state — the reasons to reach for one —
are what Query already does.

---

## Tests

```bash
npm test
```

Node's built-in runner, no framework. Coverage here is deliberately narrow: the logic worth
testing in isolation is the pure functions (`mergeMessages`, `notificationKinds`), and
everything else is better covered by the backend's end-to-end journey test, which exercises
the real API the components call. See [`docs/testing.md`](../docs/testing.md).

# MCP server — running it, and reproducing the screenshots

`backend/mcp_server.py` exposes the match agent's two tools and one resource over the
Model Context Protocol on the stdio transport. `backend/mcp_client_demo.py` is a small
client that drives it: it spawns the server, completes the handshake, **discovers** the
tools rather than assuming them, and calls two of them with fixed inputs.

Every command below is copy-pasteable and produces the same output on a seeded database.
The screenshots in [`screenshots/`](screenshots/) are captures of exactly these commands,
in this order.

---

## One-time setup

From the repo root:

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows.  macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # seed_data needs at least one user to own listings
python manage.py seed_data --clear
```

`seed_data` creates 47 listings: 40 random, 3 that stress ranking, and 4 that each break
exactly one trust rule. The demo inputs below are chosen against that data.

---

## The five commands

Run each in its own clean terminal, in `backend/`, with the venv activated.

| # | File | Command |
|---|---|---|
| 1 | `01-server-running.png` | `python mcp_server.py` |
| 2 | `02-client-connected.png` | `python mcp_client_demo.py connect` |
| 3 | `03-tools-discovered.png` | `python mcp_client_demo.py discover` |
| 4 | `04-geo-search-result.png` | `python mcp_client_demo.py geo` |
| 5 | `05-trust-check-result.png` | `python mcp_client_demo.py trust` |

`python mcp_client_demo.py` with no argument runs steps 2–5 in one pass. Use it to check
the whole path works before you start capturing; capture with the individual steps so
each frame is one idea.

### What has to be visible in each frame

1. **Server running** — the stderr banner `neighbour-node MCP server starting on stdio`
   and a cursor that does not return. The server is waiting on stdin; that is correct
   behaviour, not a hang. `Ctrl-C` to exit.
2. **Client connected** — server name and version, the negotiated protocol version, and
   the advertised capabilities. This is the handshake completing over a real pipe.
3. **Tools discovered** — both tools (`geo_search`, `trust_check`) **and** the resource
   template (`listing://{listing_id}`) in the same frame, with their parameters. This is
   the shot that proves discovery: those names came back over the wire from
   `tools/list` and `resources/templates/list`, they are not hardcoded in the client.
4. **geo_search result** — the arguments line and all three results with distances.
5. **trust_check result** — the arguments line, the single flag, and the one-line summary
   at the bottom.

### Shot 1 and shots 2–5 are different processes

Worth knowing before anyone asks. Under the stdio transport a client *spawns its own
server as a subprocess* and talks to it over that subprocess's stdin/stdout. So the
server you start by hand in shot 1 is not the one the client talks to in shots 2–5 —
the client starts its own (which is why its banner appears at the top of each of those
frames too).

Shot 1 still earns its place: it proves the entrypoint boots cleanly on its own —
`django.setup()` runs, the model imports resolve, nothing writes to stdout — which is
the failure mode that actually bites here. See "stdout is the transport" below.

---

## Why these inputs

Both calls use fixed inputs chosen so the output is small and each result has one
obvious explanation.

**`geo_search` at (40.0, -75.0), radius 3.5 km → 3 results.** That point is the
reference the seed data is built around. The radius is deliberate: 2 km returns one
listing, 5 km returns six and stops fitting on a slide. 3.5 km returns three, in
ascending distance order, which shows the ranking without needing a scrollbar.

**`trust_check` on "Basic Claw Hammer" → exactly one flag.** A claw hammer listed at
$1,450 against a plausible band of $3–$150 for tools. It trips `price_out_of_range` at
`high` severity and nothing else — its title agrees with its category, its description
is a real description, it has a photo. One flag, one sentence: *the rule caught a price
that is roughly ten times the top of the band for that category.*

The other seeded fixtures each trip one different rule, if you want a different example:

| Listing | Flag |
|---|---|
| Professional DSLR Camera (filed under `tools`) | `title_category_mismatch` — high |
| Basic Claw Hammer ($1,450) | `price_out_of_range` — high |
| Extension Cord (description: "Cord.") | `thin_description` — medium |
| Folding Camping Table (no image) | `no_photo` — low |

The client resolves the listing id from the `geo_search` results by title rather than
hardcoding a primary key, so reseeding the database doesn't break the demo. It also
means shots 4 and 5 chain: the id in shot 5 comes from the results in shot 4.

---

## Capture settings

These get projected. Anything you'd have to zoom into is wasted.

- Clear scrollback first (`cls` / `clear`) so the command is the top line of the frame.
- Terminal font up two or three sizes; window narrow enough that no line wraps. The
  demo output is padded to 64 columns, so ~90 columns is comfortable.
- No personal paths in frame — `cd backend` first so the prompt is short, and don't
  capture a title bar showing the full checkout path.
- Crop tight to the terminal. Save as PNG into `docs/screenshots/` with the numbered
  names in the table above; the numbering is what makes them drop into slides in order.

---

## Verifying it was really the same code path

Every MCP call writes a `TraceLog` row with `agent_name="mcp"`, so a tool invocation
that arrived over the protocol can be pulled out of the trace exactly like an agent step:

```bash
python manage.py shell -c "from apps.core.models import TraceLog
for t in TraceLog.objects.filter(agent_name='mcp').order_by('-created_at')[:6]:
    print(f'{t.created_at:%H:%M:%S}  {t.tool_name:<12} {t.status:<6} {t.duration_ms}ms  run_id={t.run_id[:8]}')"
```

The `run_id` each tool returns in its result appears in this table. That is the thing
to show if anyone asks whether the MCP tools are a separate reimplementation: they
aren't — `geo_search` calls `matching.services.geo_search` and `trust_check` calls
`matching.trust.check_listing_by_id`, the same functions the match agent calls
in-process, writing to the same trace.

---

## Driving it from a real client instead

The demo client is deliberately small so it can be read. To point a production client at
the same server, copy [`.mcp.json.example`](../.mcp.json.example) and fill in your paths:

```bash
cd neighbour-node-agent    # repo root, so the config is picked up
cp .mcp.json.example .mcp.json
# edit both paths to your checkout, then:
claude                     # then /mcp shows: neighbour-node · connected
```

Both entries are absolute paths — the interpreter inside `backend/venv` and
`backend/mcp_server.py` — so the file is only ever valid on one machine. That is why
`.mcp.json` is gitignored and only the example is committed, the same arrangement as
`.env` / `.env.example`. On Windows the interpreter is `backend\venv\Scripts\python.exe`
rather than `backend/venv/bin/python`.

---

## Two things that bite

- **stdout is the transport.** A single `print()` in server code corrupts the JSON-RPC
  stream and the client drops the server with no visible error. All diagnostics go to
  stderr.
- **Django must be configured before any model import.** `mcp_server.py` sets
  `DJANGO_SETTINGS_MODULE` and calls `django.setup()` before importing from `apps.*`,
  which is why those imports carry `# noqa: E402`.

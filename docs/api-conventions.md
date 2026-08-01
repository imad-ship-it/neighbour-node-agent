# API conventions

Bookmarks is the first *join-row* feature in this codebase — a row that exists only to
connect a user to something else, with a uniqueness constraint and a toggle-ish feel.
Messaging threads and notifications are the same shape, so the decisions below were made
once, deliberately, in the cheapest place to change them.

**Use this as a checklist when building those two.** Where a rule has a messaging or
notifications analogue, it is named. Inconsistency between the three is the kind of thing
a panel notices.

---

## The build order

Seven steps, in this order, per app. The rules below explain *why* each one looks the way it
does — this section is what you execute from, so that building the remaining apps is
execution rather than re-design.

**Both remaining apps already have their model and migration**, which is why this starts at
`urls.py` rather than at the model.

| # | Step | Rule | What "done" looks like |
|---|---|---|---|
| 1 | `urls.py` + wire into `config/urls.py` | [1](#1-resource-style-not-action-style) | A router with an explicit `basename` (there's no `queryset` attribute to infer it from). Nouns, not verbs. |
| 2 | ViewSet with scoped `get_queryset` | [2](#2-owner-scoped-get_queryset--404-never-403) | Filtered to `request.user` **in the queryset**, plus `select_related` for anything the serializer reaches through. |
| 3 | Serializer with request-derived owner | [3](#3-the-owner-comes-from-requestuser-never-the-payload), [7](#7-read-side-nests-a-compact-representation) | No `user`/`sender` field. Write takes ids; read nests what the component renders. |
| 4 | Permission | [2](#2-owner-scoped-get_queryset--404-never-403) | Usually just `IsAuthenticated` — step 2 already did the access control. Reach for a permission class only for a *public* resource. |
| 5 | Hook | [9](#9-frontend-mutation-in-a-hook-state-from-the-payload) | Mutation in `use<Thing>X`, optimistic cycle, query keys exported and imported, never re-declared. |
| 6 | Page | [7](#7-read-side-nests-a-compact-representation) | Route, nav link, and the empty state built **now**, not last. |
| 7 | Two tests | [8](#8-every-private-row-feature-gets-these-four-tests) | See below. |

### Which two tests

Rule 8 lists four. Under a two-days-three-apps constraint, **these two are the floor**,
because both cover a failure that passes silently *and* is a security hole rather than a
polish issue:

1. **Scoping** — another user's row returns 404 on GET *and* DELETE.
2. **Owner from request** — a payload naming someone else is ignored.

Query-count and duplicate-create are the two to add if the day allows. Skipping them costs
performance and UX; skipping the first two costs correctness of access control.

### Per-app variants

The two things that differ, named so you don't rediscover them at 11pm:

**Messaging.** A `Conversation`'s second participant is **not a field** — it's
`listing.lender`. So step 2's scope is `Q(initiator=user) | Q(listing__lender=user)`, not
`filter(user=...)`. Get this wrong and either a lender can't see their own threads, or
everyone can see everything. Also: there is **no unique constraint** on
`(listing, initiator)`, so rule 4's idempotent create is the only thing stopping duplicate
empty threads — add the constraint (rule 5) or accept that duplicates are possible.

**Notifications.** Rows are **server-created**, so rule 4 barely applies — there is no
client POST. The work is on the read side: the unread count is a rule-6 annotation, shared
by the bell badge and the page, and *"mark all read"* is the one legitimate action endpoint
in the project because it genuinely isn't a single resource.

---

## 1. Resource style, not action style

`POST /api/bookmarks/` creates, `DELETE /api/bookmarks/{id}/` removes. No
`POST /listings/{id}/bookmark/` toggle.

**Why.** A toggle endpoint races itself: two rapid clicks send two POSTs, and the second
can flip the state back before the first response lands, so the UI and the database
disagree with no error anywhere. Create and delete are separately idempotent; a toggle is
not idempotent at all.

The usual objection to resource style is that the client needs the row's id to delete it.
That is solved on the read side — see rule 6 — not by reaching for an action endpoint.

> **Messaging / notifications.** Same. `DELETE /api/notifications/{id}/`, not
> `POST /api/notifications/{id}/dismiss/`. "Mark all read" is the one legitimate action
> endpoint, because it genuinely isn't a single resource.

## 2. Owner-scoped `get_queryset` → 404, never 403

```python
def get_queryset(self):
    return Bookmark.objects.filter(user=self.request.user)
```

Filter in `get_queryset`. Do not fetch broadly and check ownership in the view body or a
permission class.

**Why.** A row that isn't yours is a row that doesn't exist, as far as you're concerned.
A 403 confirms the id is real to someone who has no business knowing that. It is also the
cheaper option — you have to *add* code to get a 403.

**Note the deliberate inconsistency with `listings`.** `IsOwnerOrReadOnly` returns 403
there, and that is correct: listings are *public* resources with restricted writes, so
their existence is not a secret. Bookmarks, threads and notifications are private rows.
The rule is "public resource → 403, private row → 404", not "always 404".

> **Messaging / notifications.** Identical, and this is the one to get right. A message
> thread you aren't a participant in must 404. Scope on the participant relation, not the
> sender.

## 3. The owner comes from `request.user`, never the payload

The write serializer accepts a listing id and nothing else. `user` is set in
`perform_create`, or via `HiddenField(default=CurrentUserDefault())`.

**Why.** A writable `user` field lets any authenticated caller create rows on another
account's behalf, and it will pass every test you write unless you specifically test for
it. Rule 8 covers that test.

> **Messaging / notifications.** Same. `sender` and `recipient` come from the request and
> the URL, never from the body.

## 4. Duplicate create is idempotent

`get_or_create`, returning the existing row with `200` rather than an error.

**Why.** The client is running an optimistic update. A double-click, a retry after a
flaky connection, or two tabs open all produce a second POST for a state the user already
asked for. Returning `400 — must make a unique set` makes the UI show a failure for
something that actually succeeded. `201` on create, `200` on "already there", is the
honest distinction.

The trade-off, stated: a POST that sometimes returns `200` is mildly non-standard. That
is a smaller cost than error-handling a non-error.

> **Notifications.** Less relevant — notifications are server-created. **Messaging:**
> relevant for creating a thread between two users who already have one; return the
> existing thread rather than a second empty one.

## 5. `UniqueConstraint`, named — not `unique_together`

```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=["user", "listing"],
            name="unique_user_listing_bookmark",
        )
    ]
```

**Why.** Django's docs prefer `UniqueConstraint` and note `unique_together` may be
deprecated. The name is the practical win: a named constraint makes the `IntegrityError`
legible in logs and in Postgres, which matters more once this shape exists in three apps.

> **Messaging / notifications.** Copy the named form. `unique_thread_participants`, etc.

## 6. Read side: annotate, never `SerializerMethodField`

Per-object state belongs in `get_queryset` as an `Exists`/`Subquery` annotation, exposed
as a read-only serializer field.

**Why.** A `SerializerMethodField` that queries runs once per row. On the listings page
that is one extra query per listing — invisible in development with a handful of rows,
and an N+1 on a seeded database right before a demo.

Annotate **both** the boolean and the id:

- `is_bookmarked` — what the card renders
- `bookmark_id` — what the card needs to issue `DELETE`, which is what makes rule 1
  workable without an action endpoint

**Always give the serializer field a `default`.** This is not defensive habit, it's a real
trap:

```python
is_bookmarked = serializers.BooleanField(read_only=True, default=False)
bookmark_id = serializers.IntegerField(read_only=True, default=None)
```

When a `read_only` field's attribute is missing, **DRF does not raise — it silently drops
the key from the response.** The create endpoint serializes a freshly saved instance that
never went through `get_queryset`, so without the defaults `is_bookmarked` is simply
absent, the client reads `undefined`, and `undefined` is falsy. The bug renders as
"correct" and never throws.

A `SerializerMethodField` is acceptable *only* if it reads an existing annotation via
`getattr` and issues no query. The banned thing is the query, not the field type — but the
plain field with a default is clearer about where the value comes from.

> **Notifications.** This is the unread count. Annotate it; do not compute it per row.
> **Messaging:** unread-per-thread and last-message-preview are the same pattern.

## 7. Read side nests a compact representation

`BookmarkSerializer` nests the listing, rather than returning a bare id.

**Why.** My Bookmarks renders `ListingCard`. A bare id would force a second round-trip to
hydrate every row, and the page would render empty and then pop.

**Nest the smallest serializer the component actually needs.** Nesting the *full*
`ListingSerializer` drags its annotation-derived fields along, and those do not survive the
serializer boundary — `is_bookmarked` / `bookmark_id` come from `ListingViewSet.get_queryset`,
which never ran. On `/saved` that was recoverable because every row is bookmarked by
definition, so `to_representation` could set both without a query. Anywhere else the honest
answer needs its own annotation, and a nested full serializer quietly becomes an N+1 or a
wrong icon.

So: `ListingHeaderSerializer` (id, title, image) for anything that only identifies a listing —
message threads, notification payloads. Reserve the full serializer for surfaces that render
a real `ListingCard`.

> **Messaging.** A thread list nests the other participant, the last message, and a listing
> *header* — deliberately not a card, so there is no bookmark state to restore.

## 8. Every private-row feature gets these four tests

Not "some tests" — these four, because each covers a failure that passes silently:

1. **Scoping.** Another user's row returns 404 on GET *and* DELETE.
2. **Owner spoofing.** A payload carrying `user: <someone else>` is ignored, and the row
   is created for the requester.
3. **Duplicate create.** Second POST returns the same row, not a new one and not a 400.
4. **Query count.** `assertNumQueries` on the list endpoint, so the rule-6 annotation
   can't silently regress to an N+1.

Test 2 is the one that passes without being written, which is exactly why it's listed.

**Worked examples to copy:** `apps/bookmarks/tests.py` is organised under these four
headings. `ListingPermissionTests` in `apps/listings/tests.py` is the public-resource
counterpart — same shape, 403 instead of 404.

**Test through the endpoint, never by instantiating the permission class.** The bugs live
in the wiring — which permission classes are attached, whether the object-level check is
reached at all, whether `DELETE` takes the same path as `PATCH` — and a unit test of
`IsOwnerOrReadOnly` would pass happily while the endpoint sat wide open. That is precisely
how the earlier `IsAuthenticatedOrReadOnly`-only version let any logged-in user edit any
listing.

**Fixtures come from `apps.core.testing`.** `make_user` and `make_listing` build on a
`CLEAN_LISTING` dict whose defaults are deliberately trust-clean, so a test overrides one
field and sees one flag. Three lines in `setUp` is the pattern to copy:

```python
self.owner = make_user("owner")
self.other = make_user("other")
self.listing = make_listing(self.owner)
```

**Then break the code and watch the test fail.** Every guard here was verified that way —
drop `select_related` and the query-count test fails; remove `IsOwnerOrReadOnly` and four
permission tests fail naming the exact caller; reorder `RULES` and only the flag-order test
fails. Two minutes per guard, and it is the only thing separating a test from a comment.

## 9. Frontend: mutation in a hook, state from the payload

The mutation lives in a `use<Thing>Toggle` hook. The card stays presentational and reads
its state from the annotated server payload, never from local component state.

**Why.** `ListingCard` renders in three places — the listings page, match results, and My
Bookmarks. Local state means two pages can disagree about whether the same listing is
bookmarked, and the bug only appears when both are mounted.

Optimistic update is the standard shape: cancel → snapshot → apply → rollback on error →
invalidate on settle.

**Invalidate every affected key rather than doing per-page cache surgery.** Un-bookmarking
removes a row on My Bookmarks but only flips a flag on the listings page — same mutation,
different correct behaviour. Targeted surgery is the version that breaks in front of a
panel; a refetch is cheap.

> **Messaging / notifications.** Same split. The bell badge and the notifications page read
> the same annotated count.

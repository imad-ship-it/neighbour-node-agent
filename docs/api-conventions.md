# API conventions

Bookmarks is the first *join-row* feature in this codebase — a row that exists only to
connect a user to something else, with a uniqueness constraint and a toggle-ish feel.
Messaging threads and notifications are the same shape, so the decisions below were made
once, deliberately, in the cheapest place to change them.

**Use this as a checklist when building those two.** Where a rule has a messaging or
notifications analogue, it is named. Inconsistency between the three is the kind of thing
a panel notices.

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

> **Messaging.** A thread list nests the other participant and the last message.

## 8. Every private-row feature gets these four tests

Not "some tests" — these four, because each covers a failure that passes silently:

1. **Scoping.** Another user's row returns 404 on GET *and* DELETE.
2. **Owner spoofing.** A payload carrying `user: <someone else>` is ignored, and the row
   is created for the requester.
3. **Duplicate create.** Second POST returns the same row, not a new one and not a 400.
4. **Query count.** `assertNumQueries` on the list endpoint, so the rule-6 annotation
   can't silently regress to an N+1.

Test 2 is the one that passes without being written, which is exactly why it's listed.

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

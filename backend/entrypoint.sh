#!/bin/sh
# Container entrypoint: bring the schema up to date, seed a demo database if this
# is a fresh volume, then hand the process over to gunicorn.
#
# Everything here must be safe to run on every container start, because it does
# run on every container start — `docker compose restart` or a crash loop will
# re-enter it against a database that is already populated.
set -eu

echo "==> migrate"
python manage.py migrate --noinput

# Seeding is guarded on "are there any users", not on "does the file exist".
# The volume is created by Docker before this script runs, so the file always
# exists and is always non-empty once migrate has built the schema — file
# existence would mean "seed never runs".
#
# `manage.py shell -c` prints True/False from the ORM, which is the only check
# that reflects what the app will actually see.
#
# --no-imports and -v 0 are both required, not tidiness. Django 5.2 added an
# automatic model import to the shell, which prints "19 objects imported
# automatically" on stdout *before* the command's own output. Captured naively,
# HAS_USERS is that banner plus the value, never equals "False", and the seed step
# silently never runs — leaving an empty database and a demo with no listings.
HAS_USERS="$(python manage.py shell --no-imports -v 0 -c \
  'from django.contrib.auth import get_user_model; print(get_user_model().objects.exists())')"

if [ "$HAS_USERS" = "False" ]; then
  echo "==> empty database, seeding"

  # Ordering here is not arbitrary, and getting it wrong fails quietly — it was
  # wrong first time round and produced a database with one listing in it.
  #
  # seed_data must run FIRST, creating its own filler neighbours to own the
  # listings. setup_demo_accounts deletes every listing belonging to either demo
  # account (the lender's is recreated, the borrower must own nothing for the
  # walkthrough to make sense). So if the demo accounts already exist when
  # seed_data picks random owners, most of the seed is assigned to them and then
  # deleted moments later. Seeding first means neither demo account exists yet,
  # so there is nothing of theirs to delete and the full set survives.
  python manage.py seed_data --users 12
  python setup_demo_accounts.py
else
  echo "==> database already populated, skipping seed"
fi

# One worker by default — see docs/decisions.md. Threads rather than workers give
# concurrency without a second process, which keeps SQLite's single writer intact.
#
# The long timeout is for the extraction endpoint: a cold vision call can take
# tens of seconds, and gunicorn's 30s default would kill the worker mid-request
# and return a 502 that looks like an application bug.
echo "==> gunicorn (workers=${GUNICORN_WORKERS:-1}, threads=${GUNICORN_THREADS:-4})"
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-1}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -

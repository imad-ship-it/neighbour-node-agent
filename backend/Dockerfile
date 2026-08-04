# syntax=docker/dockerfile:1

FROM python:3.14-slim

# PYTHONDONTWRITEBYTECODE: .pyc files in a container are write amplification for
# no gain — the process starts once and the layer is read-only anyway.
# PYTHONUNBUFFERED: without it, print/logging output sits in a pipe buffer and
# `docker compose logs` shows nothing until the buffer fills, which reads as a
# hung container.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl is here for the compose healthcheck, not for the app. Everything else the
# project needs (Pillow in particular) ships manylinux wheels, so there is no
# compiler in this image and no build-essential layer to carry around.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies before source, so editing a view doesn't re-run pip. requirements
# changes rarely; apps/ changes constantly.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# The repo is developed on Windows, where the executable bit is not tracked by
# git and editors happily write CRLF. Either one turns this line into a runtime
# error that says "no such file or directory" while pointing at a file that is
# plainly there — because the kernel is looking for an interpreter called
# "/bin/sh\r". Normalising both at build time costs nothing and removes an hour
# of confusion. (.gitattributes pins the line endings at checkout too.)
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# collectstatic imports settings, and SECRET_KEY has no default — so without a
# value here the *build* fails, with an error about a missing key that has
# nothing to do with static files. This one is deliberately a throwaway: it is
# used to collect files and never to sign anything. The real key arrives from the
# environment at run time.
#
# Running this at build time rather than in the entrypoint means the work happens
# once per image instead of once per container start, and a broken static asset
# fails the build instead of the demo.
RUN SECRET_KEY=build-time-only-never-signs-anything \
    DJANGO_SETTINGS_MODULE=config.settings \
    python manage.py collectstatic --noinput --clear

# Drop root. The two writable paths are volume mount points, so they are chowned
# here to give the mounted volumes the right owner on first creation.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data /app/media \
    && chown -R app:app /app /data
USER app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]

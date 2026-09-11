# syntax=docker/dockerfile:1
#
# Two-stage build:
#   builder  - installs deps and uses PyInstaller to produce the same
#              single-file `lanyon` binary that `scripts/build.sh` builds on bare
#              metal, so building in Docker is a reproducible stand-in for
#              that process (and a way to produce a Linux binary without
#              installing Python/PyInstaller locally).
#   runtime  - a minimal image containing *only* that compiled binary, so
#              running this image is a faithful test of what end users get:
#              no Python interpreter, no pip packages, just `lanyon`.
#
# Build:  docker build -f docker/Dockerfile -t lanyon .
# Run:    docker run --rm -v "$PWD/example/demo-site:/site/src:ro" \
#           -v "$PWD/build:/site/build" lanyon -i /site/src -o /site/build
#
# Build context is the repo root (run these commands from there), since
# this Dockerfile COPYs src/ paths relative to the top level, not ./docker.
#
# For the incremental/watch/dev-server workflow, see docker-compose.yml (repo root).
#
# Both stages build FROM the same debian:bookworm-slim base (not the
# upstream python image) specifically so the builder's glibc always matches
# the runtime's glibc - a PyInstaller binary built against a newer glibc
# than the runtime image ships fails at startup with a GLIBC_x.xx not found
# error, and floating base-image tags make that mismatch resurface on any
# rebuild.

FROM debian:bookworm-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip libpython3.11 binutils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python3 -m venv /venv \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt pyinstaller
ENV PATH="/venv/bin:$PATH"

COPY src/lanyon_entry.py ./
COPY src/lanyon/ ./lanyon/

RUN /venv/bin/pyinstaller --onefile --name lanyon lanyon_entry.py

FROM debian:bookworm-slim AS runtime

# Unbuffered stdout: without this, lanyon's print()-based logging (build
# progress, watch-mode "change detected", the dev-server's request log)
# sits in Python's block buffer and never reaches `docker compose logs`
# until the buffer fills or the process exits.
ENV PYTHONUNBUFFERED=1

COPY --from=builder /build/dist/lanyon /usr/local/bin/lanyon

WORKDIR /site
ENTRYPOINT ["lanyon"]

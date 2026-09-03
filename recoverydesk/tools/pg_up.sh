#!/usr/bin/env bash
# pg_up.sh — revive the sandbox PostgreSQL 16 + pgvector verification rig.
# Binaries live in /tmp (not persisted); the CLUSTER lives at /home/user/pgdata
# (persisted). Re-run any time; idempotent.
set -euo pipefail

PGBIN=/tmp/pgroot/bin
PGDATA=/home/user/pgdata
PORT=5432
PGVER_TAG=16.9.0          # theseus-rs/postgresql-binaries release
PGVECTOR_TAG=v0.8.0

if [ ! -x "$PGBIN/postgres" ]; then
  echo "[pg_up] fetching portable PostgreSQL ${PGVER_TAG}…"
  curl -sL -o /tmp/pgfull.tar.gz \
    "https://github.com/theseus-rs/postgresql-binaries/releases/download/${PGVER_TAG}/postgresql-${PGVER_TAG}-x86_64-unknown-linux-gnu.tar.gz"
  mkdir -p /tmp/pgroot
  tar -xzf /tmp/pgfull.tar.gz -C /tmp
  mv "/tmp/postgresql-${PGVER_TAG}-x86_64-unknown-linux-gnu"/* /tmp/pgroot/
fi

export LD_LIBRARY_PATH=/tmp/pgroot/lib

# Snapshot restores drop EMPTY directories; PostgreSQL needs several inside its
# data directory. Recreate them before any start attempt (no-op when present).
if [ -d "$PGDATA" ] && [ -f "$PGDATA/PG_VERSION" ]; then
  for d in pg_commit_ts pg_notify pg_stat_tmp pg_serial pg_tblspc pg_twophase pg_subtrans pg_replslot pg_logical/snapshots pg_logical/mappings pg_multixact/offsets pg_multixact/members; do
    mkdir -p "$PGDATA/$d"
  done
  chmod 700 "$PGDATA"
fi

if [ ! -f "$PGDATA/PG_VERSION" ]; then
  echo "[pg_up] initdb at $PGDATA…"
  "$PGBIN/initdb" -D "$PGDATA" -U rd_owner --auth=trust -E UTF8 --locale=C
fi

if ! "$PGBIN/pg_isready" -h 127.0.0.1 -p "$PORT" >/dev/null 2>&1; then
  echo "[pg_up] starting server on 127.0.0.1:${PORT}…"
  "$PGBIN/pg_ctl" -D "$PGDATA" -l "$PGDATA/server.log" \
    -o "-p ${PORT} -k /tmp -h 127.0.0.1 -c max_connections=60 -c shared_buffers=128MB" start
else
  echo "[pg_up] server already up."
fi

# pgvector: the extension CATALOG row persists in pgdata, but the .so lives in
# the wiped /tmp libdir -> rebuild whenever the library FILE is missing.
VECTORSO="$("$PGBIN/pg_config" --pkglibdir)/vector.so"
if [ ! -f "$VECTORSO" ] || ! "$PGBIN/psql" -h 127.0.0.1 -p "$PORT" -U rd_owner -d recoverydesk -tAc \
     "SELECT 1 FROM pg_extension WHERE extname='vector'" 2>/dev/null | grep -q 1; then
  if [ ! -d /tmp/pgvector-src ]; then
    curl -sL -o /tmp/pgvector.tar.gz "https://github.com/pgvector/pgvector/archive/refs/tags/${PGVECTOR_TAG}.tar.gz"
    mkdir -p /tmp/pgvector-src && tar -xzf /tmp/pgvector.tar.gz -C /tmp/pgvector-src --strip-components=1
  fi
  (cd /tmp/pgvector-src && make PG_CONFIG="$PGBIN/pg_config" -j2 >/dev/null && make PG_CONFIG="$PGBIN/pg_config" install >/dev/null)
  # DB may not exist on first boot
  "$PGBIN/psql" -h 127.0.0.1 -p "$PORT" -U rd_owner -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='recoverydesk'" | grep -q 1 || \
    "$PGBIN/createdb" -h 127.0.0.1 -p "$PORT" -U rd_owner recoverydesk
  "$PGBIN/psql" -h 127.0.0.1 -p "$PORT" -U rd_owner -d recoverydesk -c "CREATE EXTENSION IF NOT EXISTS vector;"
fi

"$PGBIN/psql" -h 127.0.0.1 -p "$PORT" -U rd_owner -d recoverydesk -tAc "SELECT version();" | head -1
echo "[pg_up] ready: postgresql+psycopg://rd_owner@127.0.0.1:${PORT}/recoverydesk"

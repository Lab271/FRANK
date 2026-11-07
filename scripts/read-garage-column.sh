#!/usr/bin/env bash
# column-rs on FRANK's sightings in the Garage bucket of `make up-s3` (#220).
#
#   scripts/read-garage-column.sh                  an interactive column-rs shell
#   scripts/read-garage-column.sh "SELECT …"       one query, then exit (or SQL="SELECT …")
#
# column-rs 0.45 opens an s3:// table location directly (t-rust-db/tools#123),
# read-only, through the manifest: the table is `sightings`, striped as the
# manifest says, each query reading the manifest again and fetching only the
# files it has not seen. Flushed files only: the open hour is in FRANK's WAL
# until the hour closes. http:// only (Garage); AWS S3 over https waits on
# tools#125. The key comes from s3/frank.env through the environment, never
# on the command line. COLUMN_RS names the binary when it is not on the PATH;
# GARAGE_S3_PORT (3900) and FRANK_S3_ENV (s3/frank.env) change where it looks.
set -euo pipefail

ENV_FILE=${FRANK_S3_ENV:-s3/frank.env}
PORT=${GARAGE_S3_PORT:-3900}
COLUMN_RS=${COLUMN_RS:-$(command -v column-rs || true)}

[ -x "$COLUMN_RS" ] || { echo "read-garage-column: column-rs not found (cargo install --git https://github.com/t-rust-db/tools --tag column-rs-v0.45.0 column-rs, or COLUMN_RS=path/to/column-rs)" >&2; exit 1; }
version=$("$COLUMN_RS" --version | awk '{print $2}')
[ "$(printf '%s\n0.45.0\n' "$version" | sort -V | head -1)" = 0.45.0 ] \
  || { echo "read-garage-column: column-rs $version cannot open s3:// locations; 0.45.0 or later" >&2; exit 1; }
[ -s "$ENV_FILE" ] || { echo "read-garage-column: no $ENV_FILE; run make up-s3 first" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

table="s3://frank/sightings?endpoint=http://127.0.0.1:$PORT&region=garage"
query=${1:-${SQL:-}}
if [ -n "$query" ]; then
  "$COLUMN_RS" -c "$query" "$table"
else
  echo "column-rs on s3://frank/sightings (the table is \`sightings\`); .quit to leave" >&2
  "$COLUMN_RS" "$table"
fi

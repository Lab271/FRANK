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
# until the hour closes. The key comes from s3/frank.env through the
# environment, never on the command line. COLUMN_RS names the binary when it
# is not on the PATH; GARAGE_S3_PORT (3900) and FRANK_S3_ENV (s3/frank.env)
# change where it looks. TLS=1 reads over Caddy's https://FRANK_HOST:9443
# (GARAGE_TLS_PORT, #224) instead: column-rs 0.46+ built with
# `--features s3-tls`, trusting Caddy's CA from CA_CERT
# (target/frank-local-ca.crt, written by `make trust`).
set -euo pipefail

ENV_FILE=${FRANK_S3_ENV:-s3/frank.env}
PORT=${GARAGE_S3_PORT:-3900}
COLUMN_RS=${COLUMN_RS:-$(command -v column-rs || true)}
MIN=0.45.0
if [ -n "${TLS:-}" ]; then
  MIN=0.46.0
  CA_CERT=${CA_CERT:-target/frank-local-ca.crt}
  [ -s "$CA_CERT" ] || { echo "read-garage-column: no $CA_CERT; run make trust first" >&2; exit 1; }
  export AWS_CA_BUNDLE=$CA_CERT
fi

[ -x "$COLUMN_RS" ] || { echo "read-garage-column: column-rs not found (cargo install --git https://github.com/t-rust-db/tools --tag column-rs-v0.46.0 column-rs, or COLUMN_RS=path/to/column-rs)" >&2; exit 1; }
version=$("$COLUMN_RS" --version | awk '{print $2}')
[ "$(printf '%s\n%s\n' "$version" "$MIN" | sort -V | head -1)" = "$MIN" ] \
  || { echo "read-garage-column: column-rs $version cannot open ${TLS:+https }s3:// locations; $MIN or later" >&2; exit 1; }
[ -s "$ENV_FILE" ] || { echo "read-garage-column: no $ENV_FILE; run make up-s3 first" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

endpoint=http://127.0.0.1:$PORT
[ -z "${TLS:-}" ] || endpoint=https://${FRANK_HOST:-frank.local}:${GARAGE_TLS_PORT:-9443}
table="s3://frank/sightings?endpoint=$endpoint&region=garage"
query=${1:-${SQL:-}}
if [ -n "$query" ]; then
  "$COLUMN_RS" -c "$query" "$table"
else
  echo "column-rs on s3://frank/sightings (the table is \`sightings\`); .quit to leave" >&2
  "$COLUMN_RS" "$table"
fi

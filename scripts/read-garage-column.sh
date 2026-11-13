#!/usr/bin/env bash
# column-rs on FRANK's sightings in the Garage bucket of `make up` (#220).
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
# is not on the PATH.
#
# Where it reads, in order of precedence:
#   URL=s3://bucket/prefix?endpoint=https://…&region=…   any location (AWS, another Garage);
#       the credentials in the environment are used as they are; AWS_CA_BUNDLE, when
#       set, is the CA trusted for https (else the system roots)
#   TLS=0   http://127.0.0.1:GARAGE_S3_PORT (3900), column-rs 0.45+
#   default https://FRANK_HOST:GARAGE_TLS_PORT (frank.local:9443, #224), column-rs
#       0.46+ built with `--features s3-tls`, trusting Caddy's CA from CA_CERT
#       (target/frank-local-ca.crt, written by `make trust`)
# The key comes from s3/frank.env (FRANK_S3_ENV) unless AWS_ACCESS_KEY_ID is set.
set -euo pipefail

ENV_FILE=${FRANK_S3_ENV:-s3/frank.env}
PORT=${GARAGE_S3_PORT:-3900}
COLUMN_RS=${COLUMN_RS:-$(command -v column-rs || true)}
URL=${URL:-}
TLS=${TLS:-1}
CA_CERT=${CA_CERT:-target/frank-local-ca.crt}

MIN=0.45.0
if [ -n "$URL" ]; then
  case $URL in *endpoint=https://*) MIN=0.46.0 ;; esac
elif [ "$TLS" != 0 ]; then
  MIN=0.46.0
  [ -s "$CA_CERT" ] || { echo "read-garage-column: no $CA_CERT; run make trust first (or TLS=0 for http)" >&2; exit 1; }
  export AWS_CA_BUNDLE=$CA_CERT
fi

[ -x "$COLUMN_RS" ] || { echo "read-garage-column: column-rs not found (cargo install --git https://github.com/t-rust-db/tools --tag column-rs-v0.46.0 column-rs --features s3-tls, or COLUMN_RS=path/to/column-rs)" >&2; exit 1; }
version=$("$COLUMN_RS" --version | awk '{print $2}')
[ "$(printf '%s\n%s\n' "$version" "$MIN" | sort -V | head -1)" = "$MIN" ] \
  || { echo "read-garage-column: column-rs $version cannot open this s3:// location; $MIN or later (https: built with --features s3-tls)" >&2; exit 1; }

if [ -z "${AWS_ACCESS_KEY_ID:-}" ]; then
  [ -s "$ENV_FILE" ] || { echo "read-garage-column: no $ENV_FILE; run make up first (or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)" >&2; exit 1; }
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

if [ -n "$URL" ]; then
  table=$URL
else
  endpoint=http://127.0.0.1:$PORT
  [ "$TLS" = 0 ] || endpoint=https://${FRANK_HOST:-frank.local}:${GARAGE_TLS_PORT:-9443}
  table="s3://frank/sightings?endpoint=$endpoint&region=garage"
fi
query=${1:-${SQL:-}}

# Say where it reads first (stderr, so query output stays clean). Colour on a
# terminal unless NO_COLOR is set; the location carries no secret.
if [ -t 2 ] && [ -z "${NO_COLOR:-}" ]; then
  b=$'\033[1m' c=$'\033[36m' g=$'\033[32m' y=$'\033[33m' z=$'\033[0m'
else
  b= c= g= y= z=
fi
case $table in *endpoint=https://*) scheme="${g}https${z}" ;; *) scheme="${y}http (no TLS)${z}" ;; esac
printf '%s→ s3-column%s %s%s%s  [%s]\n' "$b" "$z" "$c" "$table" "$z" "$scheme" >&2

if [ -n "$query" ]; then
  "$COLUMN_RS" -c "$query" "$table"
else
  echo "the table is \`sightings\`; .quit to leave" >&2
  "$COLUMN_RS" "$table"
fi

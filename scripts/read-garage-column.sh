#!/usr/bin/env bash
# column-rs on FRANK's sightings in the Garage bucket of `make up-s3` (#220).
#
#   scripts/read-garage-column.sh                  an interactive column-rs shell
#   scripts/read-garage-column.sh "SELECT …"       one query, then exit (or SQL="SELECT …")
#
# column-rs (tools 0.44) opens a table directory on disk, not an s3:// location,
# so this mirrors the table first with rclone, the data files before the
# manifest so the manifest never names a file that is not there yet, then opens
# the copy: the table is `sightings`, striped as the manifest says. The copy
# is the flushed files only (no WAL: the open hour is not in S3 yet) and is
# a snapshot; run the script again for newer files. It is kept in s3/mirror
# (FRANK_S3_MIRROR), readable by you alone: it holds sightings.
# COLUMN_RS names the binary when it is not on the PATH; GARAGE_S3_PORT (3900)
# and FRANK_S3_ENV (s3/frank.env) change where it looks.
set -euo pipefail
umask 077

ENV_FILE=${FRANK_S3_ENV:-s3/frank.env}
PORT=${GARAGE_S3_PORT:-3900}
MIRROR=${FRANK_S3_MIRROR:-s3/mirror}
COLUMN_RS=${COLUMN_RS:-$(command -v column-rs || true)}

command -v rclone >/dev/null || { echo "read-garage-column: rclone is not installed (brew install rclone)" >&2; exit 1; }
[ -x "$COLUMN_RS" ] || { echo "read-garage-column: column-rs not found (build t-rust-db/tools, then COLUMN_RS=path/to/column-rs)" >&2; exit 1; }
[ -s "$ENV_FILE" ] || { echo "read-garage-column: no $ENV_FILE; run make up-s3 first" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a
export RCLONE_LOG_LEVEL=ERROR RCLONE_CONFIG_GARAGE_TYPE=s3 RCLONE_CONFIG_GARAGE_PROVIDER=Other \
  RCLONE_CONFIG_GARAGE_ENV_AUTH=true RCLONE_CONFIG_GARAGE_REGION=garage \
  RCLONE_CONFIG_GARAGE_ENDPOINT="http://127.0.0.1:$PORT"

table="$MIRROR/sightings"
mkdir -p "$table"
rclone sync --exclude manifest.json garage:frank/sightings "$table"
rclone copyto garage:frank/sightings/manifest.json "$table/manifest.json"

query=${1:-${SQL:-}}
if [ -n "$query" ]; then
  "$COLUMN_RS" -c "$query" "$table"
else
  echo "column-rs on $table (the table is \`sightings\`); .quit to leave" >&2
  "$COLUMN_RS" "$table"
fi

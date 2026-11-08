#!/usr/bin/env bash
# DuckDB on FRANK's sightings in the Garage bucket of `make up-s3` (#220).
#
#   scripts/read-garage.sh                    an interactive DuckDB shell
#   scripts/read-garage.sh "SELECT …"         one query, then exit (or SQL="SELECT …")
#
# The view `sightings` reads the Parquet files the manifest lists when the shell
# starts (not a bare `**` glob, which can count rows twice while a closed hour
# is merged into its day). The open hour is not in S3 yet: it is in the WAL
# until the hour closes. Restart the shell to see newer files. The key comes
# from s3/frank.env through the environment, never into a file or the output.
# GARAGE_S3_PORT (3900) and FRANK_S3_ENV (s3/frank.env) change where it looks.
set -euo pipefail

ENV_FILE=${FRANK_S3_ENV:-s3/frank.env}
PORT=${GARAGE_S3_PORT:-3900}

command -v duckdb >/dev/null || { echo "read-garage: duckdb is not installed (brew install duckdb)" >&2; exit 1; }
[ -s "$ENV_FILE" ] || { echo "read-garage: no $ENV_FILE; run make up-s3 first" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

init=$(mktemp)
trap 'rm -f "$init"' EXIT
cat >"$init" <<SQL
INSTALL httpfs;
LOAD httpfs;
CREATE SECRET garage (TYPE s3, PROVIDER credential_chain, CHAIN 'env',
  ENDPOINT '127.0.0.1:$PORT', REGION 'garage', URL_STYLE 'path', USE_SSL false);
SET VARIABLE files = (SELECT list('s3://frank/sightings/' || f.path)
  FROM (SELECT unnest(files) AS f FROM read_json('s3://frank/sightings/manifest.json')));
CREATE VIEW sightings AS SELECT * FROM read_parquet(getvariable('files'));
SQL

query=${1:-${SQL:-}}
if [ -n "$query" ]; then
  duckdb -init "$init" -c "$query"
else
  echo "DuckDB on s3://frank/sightings: the view \`sightings\` has the listed files (\`DESCRIBE sightings;\`); .quit to leave" >&2
  duckdb -init "$init"
fi

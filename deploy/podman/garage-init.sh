#!/usr/bin/env bash
# Prepares the Garage of `make up-s3` (#220): the one-node layout, the bucket
# `frank`, a key for FRANK and the bucket's website option. Safe to run again:
# it only adds what is missing. The key goes to s3/frank.env (created once;
# if Garage's files are wiped, the same key is imported again).
#
#   garage-init.sh "podman compose -f … -f …"   (the compose command, as `make` runs it)
#   GARAGE_EXEC="podman exec -e RUST_LOG=warn NAME /garage" garage-init.sh -
#       (a Garage container outside compose: `S3=1 make e2e`)
set -euo pipefail

COMPOSE=${1:?usage: garage-init.sh COMPOSE_COMMAND}
GARAGE_EXEC=${GARAGE_EXEC:-$COMPOSE exec -T -e RUST_LOG=warn garage /garage}
BUCKET=frank
KEY=frank-key
ENV_FILE=${FRANK_S3_ENV:-s3/frank.env}

garage() { $GARAGE_EXEC "$@"; }

for _ in $(seq 1 60); do
  garage status >/dev/null 2>&1 && break
  sleep 1
done
garage status >/dev/null 2>&1 || { echo "garage-init: Garage did not start" >&2; exit 1; }

# The layout: one node, one zone. Version 0 is a cluster with none yet.
if garage layout show 2>/dev/null | grep -q 'layout version: 0'; then
  id=$(garage status | awk '/127.0.0.1:3901/{print $1}')
  garage layout assign -z dc1 -c 1G "$id" >/dev/null
  garage layout apply --version 1 >/dev/null
fi

garage bucket info "$BUCKET" >/dev/null 2>&1 || garage bucket create "$BUCKET" >/dev/null

if ! garage key info "$KEY" >/dev/null 2>&1; then
  if [ -s "$ENV_FILE" ]; then
    # Garage lost its state; keep the key FRANK already has.
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    garage key import --yes -n "$KEY" "$AWS_ACCESS_KEY_ID" "$AWS_SECRET_ACCESS_KEY" >/dev/null
  else
    out=$(garage key create "$KEY")
    umask 077
    {
      echo "AWS_ACCESS_KEY_ID=$(echo "$out" | awk '/Key ID:/{print $3}')"
      echo "AWS_SECRET_ACCESS_KEY=$(echo "$out" | awk '/Secret key:/{print $3}')"
    } >"$ENV_FILE"
  fi
fi

chmod 600 "$ENV_FILE"
garage bucket allow --read --write --owner "$BUCKET" --key "$KEY" >/dev/null
garage bucket website --allow "$BUCKET" >/dev/null
echo "garage: bucket $BUCKET ready"

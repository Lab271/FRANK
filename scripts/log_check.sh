#!/usr/bin/env bash
# The web and app streams of a running `make up` (ADR-024, #307): one request
# through Caddy, with a made-up bearer token and session cookie, must give a
# Caddy line and a FRANK `frank::access` line with the same X-Request-Id,
# and neither secret may appear in either container's log.
#
#   make log-check                     # https://localhost:8443
#   URL=https://localhost:9443 COMPOSE="podman compose -p x -f …" scripts/log_check.sh
#
# The token and cookie are random per run and never valid: the request gets
# 401, which is logged like any other. -k: the certificate is from Caddy's
# local CA, which `make trust` may not have added yet.
set -euo pipefail

URL=${URL:-https://localhost:8443}
COMPOSE=${COMPOSE:-podman compose -f deploy/podman/compose.yaml}
rand() { openssl rand -hex 12; }
token="logcheck-$(rand)"
cookie="logcheck-$(rand)"
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)

headers=$(curl -sk -o /dev/null -D - \
  -H "Authorization: Bearer $token" \
  -H "Cookie: frank_session=$cookie" \
  "$URL/v1/whoami?log_check=1") || { echo "FAIL: no answer from $URL (is make up running?)"; exit 1; }
status=$(printf '%s' "$headers" | awk 'NR==1 {print $2}')
id=$(printf '%s' "$headers" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-request-id" {print $2}')
[ -n "$id" ] || { echo "FAIL: no X-Request-Id from $URL (status $status)"; exit 1; }

# Both containers write as they go; give the lines a moment.
fail=0
for _ in 1 2 3 4 5; do
  caddy=$($COMPOSE logs --since "$since" caddy 2>&1 || true)
  frank=$($COMPOSE logs --since "$since" frank 2>&1 || true)
  grep -q "$id" <<<"$caddy" && grep -q "$id" <<<"$frank" && break
  sleep 1
done
if grep "$id" <<<"$frank" | grep -q "frank::access"; then
  echo "ok: FRANK's frank::access line has $id"
else
  echo "FAIL: no frank::access line with $id"; fail=1
fi
if grep -q "$id" <<<"$caddy"; then
  echo "ok: Caddy's line has $id"
else
  echo "FAIL: no Caddy line with $id"; fail=1
fi
for secret in "$token" "$cookie"; do
  if grep -q "$secret" <<<"$caddy$frank"; then
    echo "FAIL: a secret is in the logs"; fail=1
  fi
done
if [ $fail -eq 0 ]; then echo "ok: neither the token nor the cookie is logged (status $status)"; fi
exit $fail

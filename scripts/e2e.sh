#!/usr/bin/env bash
# End-to-end check of a FRANK image (#208): a throwaway container without
# Caddy, on its own temporary data, with a partner, a contributor and an
# observer; then scripts/smoke.py --writable and the read-only checks.
#
#   scripts/e2e.sh                       # IMAGE=ghcr.io/lab271/frank:latest
#   IMAGE=ghcr.io/lab271/frank:<sha> E2E_PORT=18080 KEEP=1 scripts/e2e.sh
#   S3=1 scripts/e2e.sh                  # the sightings in a throwaway Garage (#220)
#   SSO=1 scripts/e2e.sh                 # also sign in through the OIDC stub (#238)
#
# With SSO=1 the stub (deploy/podman/sso-stub, development only) runs in the
# FRANK container's network, so http://localhost:$E2E_SSO_PORT (19400) is the
# issuer for this script and for FRANK alike; FRANK's public URL is then
# http://localhost:$E2E_PORT, the one http address ADR-020 allows.
#
# It runs alongside `make up` (another port, another data directory) and
# always removes its container; the data directory too, unless KEEP=1.
# On failure the container's log comes first, so a crash reads as one.
set -euo pipefail

IMAGE=${IMAGE:-ghcr.io/lab271/frank:latest}
PORT=${E2E_PORT:-18080}
PYTHON=${PYTHON:-python3}
NAME=frank-e2e-$PORT
GARAGE=frank-e2e-garage-$PORT
NET=frank-e2e-$PORT
STUB=frank-e2e-sso-$PORT
SSO_PORT=${E2E_SSO_PORT:-19400}
URL=http://127.0.0.1:$PORT
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/frank-e2e.XXXXXX")
linux=$([ "$(uname -s)" = Linux ] && echo 1 || true)

cleanup() {
  rc=$?
  if [ $rc -ne 0 ] && podman container exists "$NAME" 2>/dev/null; then
    echo "--- podman logs $NAME (last 40 lines) ---" >&2
    podman logs --tail 40 "$NAME" >&2 || true
    echo "---" >&2
  fi
  if [ $rc -ne 0 ] && podman container exists "$STUB" 2>/dev/null; then
    echo "--- podman logs $STUB (last 20 lines) ---" >&2
    podman logs --tail 20 "$STUB" >&2 || true
    echo "---" >&2
  fi
  podman rm -f "$STUB" >/dev/null 2>&1 || true
  podman rm -f "$NAME" >/dev/null 2>&1 || true
  if [ -n "${S3:-}" ]; then
    podman rm -f "$GARAGE" >/dev/null 2>&1 || true
    podman network rm "$NET" >/dev/null 2>&1 || true
  fi
  if [ -n "${KEEP:-}" ]; then
    echo "e2e: data kept in $tmp" >&2
  elif [ -n "$linux" ]; then
    podman unshare rm -rf "$tmp"  # owned by the container's uid 65532
  else
    rm -rf "$tmp"
  fi
  exit $rc
}
trap cleanup EXIT

mkdir -p "$tmp/data" "$tmp/participants"
[ -z "$linux" ] || podman unshare chown -R 65532:65532 "$tmp/data" "$tmp/participants"
mounts=(-v "$tmp/data:/data:Z" -v "$tmp/participants:/participants:Z")

# The image's own `frank` registers each organisation; the token is its
# only line on stdout.
token() { podman run --rm "${mounts[@]}" "$IMAGE" participant add "e2e-$1" --status "$1" --with-token 2>/dev/null; }
partner=$(token partner)
contributor=$(token contributor)
observer=$(token observer)
if [ -n "${SSO:-}" ]; then
  # sbp, the main company, with the stub's superadmin as a user without a
  # token: the sign-in links to it and keeps the role.
  podman run --rm "${mounts[@]}" "$IMAGE" participant add sbp --status core >/dev/null 2>&1
  podman run --rm "${mounts[@]}" "$IMAGE" user add sbp superadmin@sbp.example --role superadmin 2>/dev/null
fi

podman rm -f "$NAME" >/dev/null 2>&1 || true
run_args=()
if [ -n "${S3:-}" ]; then
  # A one-node Garage on its own network, the bucket and key made by the
  # same script as `make up-s3`; FRANK gets the key in its environment.
  podman rm -f "$GARAGE" >/dev/null 2>&1 || true
  podman network exists "$NET" 2>/dev/null || podman network create "$NET" >/dev/null
  mkdir -p "$tmp/s3/meta" "$tmp/s3/data"
  (umask 077; printf 'GARAGE_RPC_SECRET=%s\nGARAGE_ADMIN_TOKEN=%s\n' "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" >"$tmp/s3/garage.env")
  podman run -d --name "$GARAGE" --network "$NET" --env-file "$tmp/s3/garage.env" \
    -v "$here/../deploy/podman/garage.toml:/etc/garage.toml:ro,Z" \
    -v "$tmp/s3/meta:/meta:Z" -v "$tmp/s3/data:/data:Z" \
    "${GARAGE_IMAGE:-docker.io/dxflrs/garage:v2.1.0}" >/dev/null
  FRANK_S3_ENV="$tmp/s3/frank.env" GARAGE_EXEC="podman exec -e RUST_LOG=warn $GARAGE /garage" \
    "$here/../deploy/podman/garage-init.sh" -
  run_args=(--network "$NET" --env-file "$tmp/s3/frank.env"
    -e "FRANK_STORE=s3://frank/sightings?endpoint=http://$GARAGE:3900&region=garage")
fi
if [ -n "${SSO:-}" ]; then
  # The client secret: a file only, in a private directory; readable inside
  # the containers, whose users are not this one.
  mkdir -p "$tmp/sso" && chmod 700 "$tmp/sso"
  openssl rand -hex 32 >"$tmp/sso/client-secret" && chmod 644 "$tmp/sso/client-secret"
  podman build -q -t localhost/frank-sso-stub:e2e "$here/../deploy/podman/sso-stub" >/dev/null
  issuer=http://localhost:$SSO_PORT/oauth2/default
  redirect=http://localhost:$PORT/v1/sso/callback
  secret=(-v "$tmp/sso/client-secret:/run/secrets/frank-sso-client-secret:ro,Z")
  run_args+=(-p "127.0.0.1:$SSO_PORT:$SSO_PORT" "${secret[@]}"
    -e "FRANK_SSO_ISSUER=$issuer" -e FRANK_SSO_CLIENT_ID=frank-e2e
    -e FRANK_SSO_CLIENT_SECRET_FILE=/run/secrets/frank-sso-client-secret
    -e "FRANK_SSO_REDIRECT_URL=$redirect" -e FRANK_SSO_ORGANISATION=e2e-contributor)
fi
podman run -d --name "$NAME" -p "127.0.0.1:$PORT:8080" "${run_args[@]}" "${mounts[@]}" "$IMAGE" >/dev/null
echo "e2e: $IMAGE on $URL${S3:+ (sightings in Garage)}${SSO:+ (sign-in with SSO through the stub)}"
if [ -n "${SSO:-}" ]; then
  podman rm -f "$STUB" >/dev/null 2>&1 || true
  podman run -d --name "$STUB" --network "container:$NAME" "${secret[@]}" \
    -e "STUB_ISSUER=$issuer" -e "STUB_LISTEN=0.0.0.0:$SSO_PORT" -e STUB_CLIENT_ID=frank-e2e \
    -e STUB_CLIENT_SECRET_FILE=/run/secrets/frank-sso-client-secret -e "STUB_REDIRECT_URIS=$redirect" \
    localhost/frank-sso-stub:e2e >/dev/null
fi
for _ in $(seq 1 60); do
  curl -fsS "$URL/health" >/dev/null 2>&1 && break
  podman container exists "$NAME" || { echo "e2e: the container exited at startup" >&2; exit 1; }
  sleep 0.5
done

"$PYTHON" "$here/smoke.py" --url "$URL" --redirect no --writable \
  --token "$partner" --token "$contributor" --token "$observer"

if [ -n "${S3:-}" ]; then
  # The table's manifest must be in the bucket, not on the volume.
  info=$(podman exec -e RUST_LOG=warn "$GARAGE" /garage bucket info frank)
  echo "$info" | awk '/^Objects:/{n=$2} END{exit !(n>0)}' || { echo "e2e: the bucket is empty" >&2; echo "$info" >&2; exit 1; }
  echo "e2e: sightings are in the bucket"
fi

if [ -n "${SSO:-}" ]; then
  for _ in $(seq 1 60); do
    curl -fsS "$issuer/.well-known/openid-configuration" >/dev/null 2>&1 && break
    podman container exists "$STUB" || { echo "e2e: the SSO stub exited at startup" >&2; exit 1; }
    sleep 0.5
  done
  "$PYTHON" "$here/sso_check.py" --url "http://localhost:$PORT"
  "$PYTHON" "$here/sso_check.py" --url "http://localhost:$PORT" \
    --user 00u-stub-superadmin --email superadmin@sbp.example --role superadmin
fi

#!/bin/sh
# DB-IP Lite Country + ASN (CC BY 4.0, no account; #191) into
# DATA/geoip/dbip-lite: this month's, else last month's. Used by `make geoip`
# and by the STACKIT VM's monthly timer (#276). The files are downloaded to a
# temporary directory and moved into place only when both are complete, so a
# failed download keeps the previous ones. FRANK picks them up within a minute.
#
#   scripts/fetch-geoip.sh DATA
set -eu
data=${1:?usage: fetch-geoip.sh DATA}
url=${DBIP_URL:-https://download.db-ip.com/free}
dir="$data/geoip/dbip-lite"
install -d -m 700 "$data/geoip" "$dir"
tmp=$(mktemp -d "$data/geoip/.download.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
months="$(date -u +%Y-%m) $(date -u -v-1m +%Y-%m 2>/dev/null || date -u -d '1 month ago' +%Y-%m)"
for db in country asn; do
  for m in $months; do
    curl -fsSL "$url/dbip-$db-lite-$m.mmdb.gz" -o "$tmp/$db.gz" && break
  done
  [ -s "$tmp/$db.gz" ] || { echo "geoip: no DB-IP $db database for $months" >&2; exit 1; }
  gunzip -c "$tmp/$db.gz" >"$tmp/dbip-$db-lite.mmdb"
done
chmod 600 "$tmp"/*.mmdb
mv -f "$tmp"/*.mmdb "$dir/"
ls -l "$dir"

#!/bin/sh
# The warning (MISP, CC0) and reference (abuse.ch, CC0) lists into
# DATA/lists (#192, #193). Used by `make lists` and by the STACKIT VM's daily
# timer (#276). Each file is downloaded next to its place under a dot name and
# renamed when complete, so a failed download keeps the previous one. FRANK
# imports new or changed files within a minute.
#
#   [ABUSE_KEY=…] scripts/fetch-lists.sh DATA
#
# Without ABUSE_KEY (the abuse.ch Auth-Key) URLhaus and ThreatFox are skipped.
set -eu
data=${1:?usage: fetch-lists.sh DATA}
misp=https://raw.githubusercontent.com/MISP/misp-warninglists/main/lists
# Public DNS resolvers, and the special-purpose ranges: private, documentation
# (RFC 5737, RFC 3849), shared, link-local and multicast addresses.
warning="public-dns-v4 public-dns-v6 public-dns-hostname rfc5735 rfc1918 rfc3849 rfc6598 ipv6-linklocal multicast"
feodo=https://feodotracker.abuse.ch/downloads/ipblocklist.csv
# name=host:export, the key going in the URL.
keyed="urlhaus=urlhaus:online.csv threatfox_recent=threatfox:recent.csv"

w="$data/lists/warning"
r="$data/lists/reference"
install -d "$w" "$r"

for l in $warning; do
  curl -fsS -o "$w/.$l.json" "$misp/$l/list.json" || { echo "lists: MISP $l failed" >&2; exit 1; }
  mv -f "$w/.$l.json" "$w/$l.json"
done

curl -fsS -o "$r/.feodo_ipblocklist.csv" "$feodo" || { echo "lists: Feodo Tracker failed" >&2; exit 1; }
mv -f "$r/.feodo_ipblocklist.csv" "$r/feodo_ipblocklist.csv"

if [ -z "${ABUSE_KEY:-}" ]; then
  echo "lists: no abuse.ch Auth-Key (ABUSE_KEY): URLhaus and ThreatFox skipped" >&2
else
  for kv in $keyed; do
    n=${kv%%=*}
    he=${kv#*=}
    # The key goes through curl's config on stdin, not its command line.
    printf 'url = "https://%s-api.abuse.ch/v2/files/exports/%s/%s"\noutput = "%s"\n' \
      "${he%%:*}" "$ABUSE_KEY" "${he#*:}" "$r/.$n.csv" |
      curl -fsS --config - || { echo "lists: abuse.ch $n failed" >&2; exit 1; }
    mv -f "$r/.$n.csv" "$r/$n.csv"
  done
fi
ls -l "$w" "$r"

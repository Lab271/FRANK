# FRANK Phase 3 (ADR-016). Phase 2 (Python) is at the tag phase2-final.
SHELL := /bin/bash
CARGO ?= rustup run stable cargo
DATA ?= ./data
PARTICIPANTS ?= ./participants
TOKENS ?= ./tokens
IMAGE ?= ghcr.io/lab271/frank
VERSION := $(shell sed -n 's/^version = "\(.*\)"/\1/p' Cargo.toml | head -1)
WASM_BINDGEN_VERSION := 0.2.129
FRANK := target/release/frank
# PROJECT names the compose project (default: the directory, `podman`); the
# modes below share it, so `make down` stops either.
COMPOSE := podman compose $(if $(PROJECT),-p $(PROJECT)) -f deploy/podman/compose.yaml
COMPOSE_S3 := $(COMPOSE) -f deploy/podman/compose.s3.yaml
S3_DIR := s3
# `make up-sso` (#238): sign-in with SSO against the local OIDC stub
# (development only). Its client secret lives in ./sso/client-secret.
COMPOSE_SSO := $(COMPOSE) -f deploy/podman/compose.sso.yaml
SSO_DIR := sso
SSO_STUB_PORT ?= 9400
FRANK_SSO_ORGANISATION ?= sso-users
# The name and address of the podman deployment's HTTPS (Caddy, `tls
# internal`); FRANK_TLS_ADDR=443 for https://frank.local, on every interface.
FRANK_HOST ?= frank.local
FRANK_TLS_ADDR ?= 127.0.0.1:8443
# http://frank.local redirects to it; port 80 binds on every interface.
FRANK_HTTP_ADDR ?= 80
FRANK_HTTPS_PORT = $(lastword $(subst :, ,$(FRANK_TLS_ADDR)))
FRANK_URL_TLS = https://$(FRANK_HOST)$(if $(filter 443 %:443,$(FRANK_TLS_ADDR)),,:$(lastword $(subst :, ,$(FRANK_TLS_ADDR))))
CA_CERT := target/frank-local-ca.crt
N ?= 60
RATE ?= 60
DURATION ?= 1h
# DB-IP's free country and ASN databases, CC BY 4.0, no account needed (#191).
GEOIP_DIR := $(DATA)/geoip/dbip-lite
DBIP_URL := https://download.db-ip.com/free
# The abuse.ch Auth-Key for URLhaus and ThreatFox, read from 1Password by
# `make lists` (#193). The item is named by id: "abuse.ch" matches more than one.
ABUSE_KEY_REF ?= op://Private/ghrds67j2aclbtl2v2dbsodqiu/auth key
OP_ACCOUNT ?= my.1password.eu
# Tests (#208): `make smoke` checks a running FRANK at FRANK_URL (scheme and
# port; TLS=1 for the podman deployment's HTTPS) with TOKEN (space separated,
# never echoed). `make e2e` builds the image, unless E2E_TAG names one.
PYTHON ?= python3
FRANK_URL ?= http://127.0.0.1:8080
E2E_PORT ?= 18080
E2E_TAG ?=

.PHONY: help check build server wasm test test-slow assurance check-assurance smoke e2e lint fmt run participant participants user role token demo stream-setup stream geoip lists image up up-solo up-s3 up-sso sso-env s3-env s3-ls s3-browse s3-read s3-column down trust untrust clean

##@ General

help: ## Show targets by section (colour on a terminal, unless NO_COLOR is set)
	@if [ -t 1 ] && [ -z "$$NO_COLOR" ]; then b=$$'\033[1m'; c=$$'\033[36m'; d=$$'\033[2m'; r=$$'\033[0m'; fi; \
	awk -v b="$$b" -v c="$$c" -v d="$$d" -v r="$$r" ' \
	  BEGIN { FS = ":.*## "; printf "%sFRANK %s%s  %smake <target> [VAR=value]%s\n", b, "$(VERSION)", r, d, r } \
	  /^##@/ { printf "\n%s%s%s\n", b, substr($$0, 5), r; next } \
	  /^[a-z0-9-]+:.*## / { printf "  %s%-13s%s %s\n", c, $$1, r, $$2 }' $(MAKEFILE_LIST)

check: ## Verify the toolchain
	@rustup target list --installed | grep -q wasm32-unknown-unknown || { echo "rustup target add wasm32-unknown-unknown"; exit 1; }
	@wasm-bindgen --version | grep -q $(WASM_BINDGEN_VERSION) || { echo "cargo install wasm-bindgen-cli --version $(WASM_BINDGEN_VERSION) --locked"; exit 1; }
	@echo "toolchain ok"

##@ Build

build: server wasm ## Build the server (release) and the browser module

server: ## Build the server binary only
	$(CARGO) build --release --locked -p frank

wasm: ## Build web/pkg (frank-wasm for the browser)
	$(CARGO) build --release --locked -p frank-wasm --target wasm32-unknown-unknown
	wasm-bindgen --target web --no-typescript --out-dir web/pkg \
		target/wasm32-unknown-unknown/release/frank_wasm.wasm

clean: ## Remove build output
	$(CARGO) clean
	rm -rf web/pkg

##@ Develop

test: ## Run all tests
	$(CARGO) test --workspace --locked

lint: check-mvl-limit ## fmt check + clippy (native and wasm32) + qualified-subset gate, as CI runs them
	$(CARGO) fmt --all --check
	$(CARGO) clippy --workspace --all-targets --locked -- -D warnings
	$(CARGO) clippy -p frank-wasm --target wasm32-unknown-unknown --locked -- -D warnings

# Qualified-subset gate (#217), as in t-rust-db's sqlite-rs: no unsafe, dyn,
# explicit lifetimes or macros outside the curated allowlist (mvl-rust
# rust-limit). Scope: frank-core, the pure model. The frank server crate and
# frank-wasm are I/O boundaries (axum, tracing, json!, dyn callbacks) and are
# exempt. Production code only: each file is cut at its first #[cfg(test)]
# (the test module comes last by convention) before it is checked.
MVL_LIMIT ?= cargo-mvl-limit
MVL_LIMIT_CRATES := crates/frank-core
check-mvl-limit: ## Qualified-subset gate on frank-core (cargo-mvl-limit; MVL_LIMIT=path to override)
	@command -v $(MVL_LIMIT) >/dev/null 2>&1 || { \
	  echo "error: $(MVL_LIMIT) not found."; \
	  echo "install: cargo install --git https://github.com/mvl-lang/mvl-rust rust-limit --bin cargo-mvl-limit"; \
	  exit 1; }
	@tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; fail=0; \
	for f in $$(find $(MVL_LIMIT_CRATES) -path '*/src/*' -name '*.rs' | sort); do \
	  mkdir -p "$$tmp/$$(dirname $$f)"; \
	  awk '/^#\[cfg\(test\)\]/{exit} {print}' "$$f" > "$$tmp/$$f"; \
	  if ! (cd "$$tmp" && $(MVL_LIMIT) "$$f"); then echo "LIMIT VIOLATION: $$f"; fail=1; fi; \
	done; \
	if [ $$fail -eq 0 ]; then echo "check-mvl-limit: all files in the qualified subset"; fi; \
	exit $$fail

# Spec traceability (ADR-021): every **Implementation:** and **Tests:** link in
# .openspec/specs must resolve, and every relative Markdown link in the docs.
# ASSURANCE_MIN is the floor on tested scenarios; raise it as #250 adds specs.
ASSURANCE_MIN ?= 0
assurance: ## Spec -> code -> test traceability per spec (V=1: per requirement, with dead links)
	@python3 scripts/assurance.py $(if $(filter 1,$(V)),-v,)

check-assurance: ## Gate: no dead spec or doc links, tested scenarios >= ASSURANCE_MIN; tests the checker first
	@python3 -m unittest discover -q -s scripts -p 'test_assurance.py'
	@python3 scripts/assurance.py --min $(ASSURANCE_MIN)

fmt: ## Format the code
	$(CARGO) fmt --all

run: build ## Run on this machine (./data and ./participants, shared with up)
	FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) FRANK_TOKENS=$(TOKENS) $(FRANK) serve

##@ Participants (participants.db)

# Participants, users and tokens live in $(PARTICIPANTS)/participants.db and take
# effect on the next request, with the server running or not.
participant: server ## Register an organisation with a token: make participant NAME=me STATUS=partner
	@[ -n "$(NAME)" ] && [ -n "$(STATUS)" ] || { echo "usage: make participant NAME=<organisation> STATUS=observer|contributor|partner|core" >&2; exit 2; }
	@FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) $(FRANK) participant add "$(NAME)" --status $(STATUS) --with-token

participants: server ## List organisations, users and tokens
	@FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) $(FRANK) participant list
	@FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) $(FRANK) user list
	@FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) $(FRANK) token list

user: server ## Add a user with a token: make user PARTICIPANT=me NAME=alice [MACHINE=1] [ROLE=admin]
	@[ -n "$(PARTICIPANT)" ] && [ -n "$(NAME)" ] || { echo "usage: make user PARTICIPANT=<organisation> NAME=<user> [MACHINE=1] [ROLE=admin|superadmin]" >&2; exit 2; }
	@FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) $(FRANK) user add "$(PARTICIPANT)" "$(NAME)" $(if $(MACHINE),--machine) $(if $(ROLE),--role $(ROLE))
	@FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) $(FRANK) token new "$(NAME)"

role: server ## Set a user's role: make role NAME=alice ROLE=admin|superadmin|none
	@[ -n "$(NAME)" ] && [ -n "$(ROLE)" ] || { echo "usage: make role NAME=<user> ROLE=admin|superadmin|none" >&2; exit 2; }
	@FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) $(FRANK) user set-role "$(NAME)" $(ROLE)

token: server ## Another token for a user: make token NAME=alice
	@[ -n "$(NAME)" ] || { echo "usage: make token NAME=<user>" >&2; exit 2; }
	@FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) $(FRANK) token new "$(NAME)"

##@ Test

test-slow: ## Slow Rust tests (#[ignore = "slow"]): volume and paging
	$(CARGO) test --workspace --locked --release -- --ignored

smoke: ## Read-only checks of a running FRANK: make smoke TOKEN=… [FRANK_URL=…|TLS=1] [CA=…]
	@TOKEN="$(TOKEN)" $(PYTHON) scripts/smoke.py --url $(if $(TLS),$(FRANK_URL_TLS),$(FRANK_URL)) \
	  $(if $(TLS),--ca $(CA_CERT),$(if $(CA),--ca $(CA)))

e2e: $(if $(E2E_TAG),,image) ## Throwaway container (no Caddy), generated data, every check: [E2E_TAG=…] [E2E_PORT=18080] [KEEP=1] [S3=1: sightings in a throwaway Garage] [SSO=1: sign in through the OIDC stub]
	IMAGE=$(IMAGE):$(or $(E2E_TAG),$(VERSION)) E2E_PORT=$(E2E_PORT) PYTHON="$(PYTHON)" KEEP=$(KEEP) S3=$(S3) SSO=$(SSO) scripts/e2e.sh

##@ Data

demo: server ## Load N (60) synthetic sightings from the last 7 days into ./data (server stopped)
	@! pgrep -f "frank.* serve" >/dev/null || { echo "stop the running frank server first (it holds the table lock), or POST the file to /v1/sightings" >&2; exit 1; }
	python3 scripts/demo_sightings.py $(N) target/demo $(DATA)/lists
	@for f in target/demo/mdr-*.json; do \
	  FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) $(FRANK) ingest --as "$$(basename $$f .json)" --create $$f || exit 1; \
	done

stream-setup: server ## Register the checked-in test tokens (scripts/stream_tokens.json) in ./participants; local only
	@FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) python3 scripts/stream_sightings.py --setup --frank $(FRANK)

stream: ## Stream sightings through the API and watch the table: make stream RATE=60 DURATION=1h [FRANK_URL=…]
	python3 scripts/stream_sightings.py --rate $(RATE) --duration $(DURATION) --lists $(DATA)/lists

geoip: ## Download DB-IP Lite Country + ASN into data/geoip/dbip-lite (this month's, else last month's)
	@install -d -m 700 $(DATA)/geoip $(GEOIP_DIR)
	@set -euo pipefail; \
	tmp=$$(mktemp -d $(DATA)/geoip/.download.XXXXXX); trap 'rm -rf "$$tmp"' EXIT; \
	months="$$(date -u +%Y-%m) $$(date -u -v-1m +%Y-%m 2>/dev/null || date -u -d '1 month ago' +%Y-%m)"; \
	for db in country asn; do \
	  for m in $$months; do \
	    curl -fsSL "$(DBIP_URL)/dbip-$$db-lite-$$m.mmdb.gz" -o "$$tmp/$$db.gz" && break; \
	  done; \
	  gunzip -c "$$tmp/$$db.gz" > "$$tmp/dbip-$$db-lite.mmdb"; \
	done; \
	chmod 600 "$$tmp"/*.mmdb; mv -f "$$tmp"/*.mmdb $(GEOIP_DIR)/
	@ls -l $(GEOIP_DIR)

MISP_LISTS := https://raw.githubusercontent.com/MISP/misp-warninglists/main/lists
# Public DNS resolvers, and the special-purpose ranges: private, documentation
# (RFC 5737, RFC 3849), shared, link-local and multicast addresses.
MISP_WARNING := public-dns-v4 public-dns-v6 public-dns-hostname \
	rfc5735 rfc1918 rfc3849 rfc6598 ipv6-linklocal multicast
ABUSE_API := https://%s-api.abuse.ch/v2/files/exports/%s/%s
# name=host:export, the key going in between.
ABUSE_KEYED := urlhaus=urlhaus:online.csv threatfox_recent=threatfox:recent.csv
FEODO := https://feodotracker.abuse.ch/downloads/ipblocklist.csv

lists: ## Download the warning (MISP, CC0) and reference (abuse.ch, CC0; Auth-Key from 1Password, ABUSE_KEY_REF) lists into data/lists; the server imports them within a minute
	@install -d $(DATA)/lists/warning $(DATA)/lists/reference
	@set -euo pipefail; for l in $(MISP_WARNING); do \
	  curl -fsS -o $(DATA)/lists/warning/.$$l.json "$(MISP_LISTS)/$$l/list.json" \
	    || { echo "lists: MISP $$l failed" >&2; exit 1; }; \
	  mv -f $(DATA)/lists/warning/.$$l.json $(DATA)/lists/warning/$$l.json; \
	done
	@set -euo pipefail; d=$(DATA)/lists/reference; \
	curl -fsS -o $$d/.feodo_ipblocklist.csv "$(FEODO)" || { echo "lists: Feodo Tracker failed" >&2; exit 1; }; \
	mv -f $$d/.feodo_ipblocklist.csv $$d/feodo_ipblocklist.csv; \
	if ! KEY=$$(op read --account "$(OP_ACCOUNT)" "$(ABUSE_KEY_REF)" 2>/dev/null) || [ -z "$$KEY" ]; then \
	  echo "lists: no abuse.ch Auth-Key ($(ABUSE_KEY_REF)): URLhaus and ThreatFox skipped" >&2; exit 0; \
	fi; \
	for kv in $(ABUSE_KEYED); do n=$${kv%%=*}; he=$${kv#*=}; \
	  printf 'url = "$(ABUSE_API)"\noutput = "%s"\n' "$${he%%:*}" "$$KEY" "$${he#*:}" "$$d/.$$n.csv" \
	    | curl -fsS --config - || { echo "lists: abuse.ch $$n failed" >&2; exit 1; }; \
	  mv -f $$d/.$$n.csv $$d/$$n.csv; \
	done
	@ls -l $(DATA)/lists/warning $(DATA)/lists/reference

##@ Container (podman)

image: ## Build the container image with podman
	podman build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest -f Containerfile .

up: up-solo ## Alias of up-solo

up-solo: image s3-env ## Run in podman, the table on disk (the same ./data and ./participants as run): http://127.0.0.1:8080 and https://frank.local:8443
	mkdir -p data participants && touch $(TOKENS)
	FRANK_HOST=$(FRANK_HOST) FRANK_TLS_ADDR=$(FRANK_TLS_ADDR) FRANK_HTTPS_PORT=$(FRANK_HTTPS_PORT) \
	  FRANK_HTTP_ADDR=$(FRANK_HTTP_ADDR) $(COMPOSE) up -d --force-recreate --remove-orphans
	@echo "FRANK: $(FRANK_URL_TLS) (http://$(FRANK_HOST) redirects there; once: make trust), API also at http://127.0.0.1:$${FRANK_PORT:-8080}"

up-s3: image s3-env ## Like up-solo, the sightings' Parquet files in a Garage (S3) bucket, files in ./s3; the S3 API, its web endpoint and the admin API on 127.0.0.1:3900, :3902 and :3903, the S3 API over HTTPS at https://frank.local:9443
	mkdir -p data participants $(S3_DIR)/meta $(S3_DIR)/data && touch $(TOKENS)
	@[ -s $(S3_DIR)/garage.env ] || { umask 077; printf 'GARAGE_RPC_SECRET=%s\nGARAGE_ADMIN_TOKEN=%s\n' "$$(openssl rand -hex 32)" "$$(openssl rand -hex 32)" > $(S3_DIR)/garage.env; }
	$(COMPOSE_S3) up -d --force-recreate --remove-orphans garage
	FRANK_S3_ENV=$(S3_DIR)/frank.env deploy/podman/garage-init.sh "$(COMPOSE_S3)"
	FRANK_HOST=$(FRANK_HOST) FRANK_TLS_ADDR=$(FRANK_TLS_ADDR) FRANK_HTTPS_PORT=$(FRANK_HTTPS_PORT) \
	  FRANK_HTTP_ADDR=$(FRANK_HTTP_ADDR) $(COMPOSE_S3) up -d --force-recreate --remove-orphans
	@echo "FRANK: $(FRANK_URL_TLS) (http://$(FRANK_HOST) redirects there; once: make trust), API also at http://127.0.0.1:$${FRANK_PORT:-8080}"
	@echo "Garage: S3 http://127.0.0.1:$${GARAGE_S3_PORT:-3900} and https://$(FRANK_HOST):$${GARAGE_TLS_PORT:-9443}, bucket website http://frank.web.garage.localhost:$${GARAGE_WEB_PORT:-3902}/<key>, files in ./$(S3_DIR); make s3-ls lists the bucket"

up-sso: image s3-env sso-env ## Like up-solo, with sign-in with SSO against a local OIDC stub at http://localhost:9400 (SSO_STUB_PORT; development only: it signs in anyone who picks a name); new users land in FRANK_SSO_ORGANISATION (sso-users, contributor)
	mkdir -p data participants && touch $(TOKENS)
	@podman run --rm -v $(CURDIR)/participants:/participants:Z $(IMAGE):$(VERSION) participant list 2>/dev/null \
	  | awk '{print $$1}' | grep -qxF '$(FRANK_SSO_ORGANISATION)' \
	  || podman run --rm -v $(CURDIR)/participants:/participants:Z $(IMAGE):$(VERSION) \
	       participant add '$(FRANK_SSO_ORGANISATION)' --status contributor
	FRANK_HOST=$(FRANK_HOST) FRANK_TLS_ADDR=$(FRANK_TLS_ADDR) FRANK_HTTPS_PORT=$(FRANK_HTTPS_PORT) \
	  FRANK_HTTP_ADDR=$(FRANK_HTTP_ADDR) SSO_STUB_PORT=$(SSO_STUB_PORT) \
	  FRANK_SSO_REDIRECT_URL=$(FRANK_URL_TLS)/v1/sso/callback FRANK_SSO_ORGANISATION=$(FRANK_SSO_ORGANISATION) \
	  $(COMPOSE_SSO) up -d --build --force-recreate --remove-orphans
	@echo "FRANK: $(FRANK_URL_TLS) with sign-in with SSO (once: make trust); the OIDC stub at http://localhost:$(SSO_STUB_PORT)/oauth2/default (development only)"

# The OIDC client secret shared by FRANK and the stub (#238): made once,
# never printed, git-ignored. The directory is private (700); the file is
# 644 so the containers' own users (65532, 65533) can read the bind mount.
sso-env:
	@mkdir -p $(SSO_DIR) && chmod 700 $(SSO_DIR)
	@[ -s $(SSO_DIR)/client-secret ] || { umask 077; openssl rand -hex 32 > $(SSO_DIR)/client-secret; }
	@chmod 644 $(SSO_DIR)/client-secret

# The compose files name s3/*.env, which must exist for any compose command,
# also in up-solo and down. Empty until up-s3 fills them.
s3-env:
	@mkdir -p $(S3_DIR) && chmod 700 $(S3_DIR) && (umask 077; touch $(S3_DIR)/garage.env $(S3_DIR)/frank.env) && chmod 600 $(S3_DIR)/garage.env $(S3_DIR)/frank.env

s3-ls: s3-env ## List the objects in the Garage bucket (after up-s3)
	@$(COMPOSE_S3) exec -T garage /garage bucket info frank
	@set -a; . $(S3_DIR)/frank.env; set +a; \
	  printf 'user = "%s:%s"\n' "$$AWS_ACCESS_KEY_ID" "$$AWS_SECRET_ACCESS_KEY" \
	  | curl -fsS --config - --aws-sigv4 "aws:amz:garage:s3" "http://127.0.0.1:$${GARAGE_S3_PORT:-3900}/frank?list-type=2" \
	  | sed 's|<Contents>|\n|g' | sed -n 's|.*<Key>\([^<]*\)</Key>.*<Size>\([0-9]*\)</Size>.*|\2\t\1|p'

s3-browse: s3-env ## Browse the Garage bucket in the terminal with rclone ncdu (brew install rclone, after up-s3); S3_PATH=sightings/live starts deeper
	@command -v rclone >/dev/null || { echo "s3-browse: rclone is not installed (brew install rclone)" >&2; exit 1; }
	@[ -s $(S3_DIR)/frank.env ] || { echo "s3-browse: no $(S3_DIR)/frank.env; run make up-s3 first" >&2; exit 1; }
	@set -a; . $(S3_DIR)/frank.env; set +a; \
	  RCLONE_CONFIG_GARAGE_TYPE=s3 RCLONE_CONFIG_GARAGE_PROVIDER=Other RCLONE_CONFIG_GARAGE_ENV_AUTH=true \
	  RCLONE_CONFIG_GARAGE_REGION=garage RCLONE_CONFIG_GARAGE_ENDPOINT=http://127.0.0.1:$${GARAGE_S3_PORT:-3900} \
	  rclone ncdu garage:frank/$(S3_PATH)

s3-read: s3-env ## DuckDB on the sightings in the Garage bucket (brew install duckdb, after up-s3): view `sightings`; SQL="SELECT …" runs one query
	@scripts/read-garage.sh

s3-column: s3-env ## column-rs (0.46+, built with --features s3-tls) on the sightings in the Garage bucket over https://frank.local:9443 (after up-s3 and make trust; COLUMN_RS=path if not on the PATH): SQL="SELECT …" runs one query; TLS=0 reads http://127.0.0.1:3900 (0.45+); URL=s3://bucket/prefix?endpoint=…&region=… reads any location (AWS)
	@TLS="$(TLS)" URL="$(URL)" FRANK_HOST=$(FRANK_HOST) CA_CERT=$(CA_CERT) scripts/read-garage-column.sh

down: s3-env ## Stop the podman deployment, either mode (the data stays)
	$(COMPOSE_S3) down --remove-orphans

trust: s3-env ## Once, after make up: trust its HTTPS (Caddy's local CA) in the macOS keychain and map FRANK_HOST to this machine; asks for sudo
	@[ "$$(uname)" = Darwin ] || { echo "trust: macOS only; elsewhere add Caddy's root (caddy-data volume, caddy/pki/authorities/local/root.crt) to the system's trust store" >&2; exit 1; }
	@mkdir -p target
	@$(COMPOSE_S3) exec -T caddy cat /data/caddy/pki/authorities/local/root.crt > $(CA_CERT) 2>/dev/null && [ -s $(CA_CERT) ] \
	  || { rm -f $(CA_CERT); echo "trust: start the podman deployment first (make up)" >&2; exit 1; }
	sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $(CA_CERT)
	@grep -qE '^[^#]*[[:space:]]$(FRANK_HOST)([[:space:]]|$$)' /etc/hosts || { \
	  echo "adding $(FRANK_HOST) to /etc/hosts (127.0.0.1 and ::1)"; \
	  printf '127.0.0.1 %s\n::1 %s\n' $(FRANK_HOST) $(FRANK_HOST) | sudo tee -a /etc/hosts >/dev/null; }
	@echo "$(FRANK_URL_TLS) is trusted; restart the browser if it was open"

untrust: ## Remove the CA that make trust added from the macOS keychain (the /etc/hosts lines stay)
	@[ -s $(CA_CERT) ] || { echo "untrust: no $(CA_CERT); nothing was trusted from here" >&2; exit 1; }
	sudo security delete-certificate -Z "$$(openssl x509 -in $(CA_CERT) -noout -fingerprint -sha1 | cut -d= -f2 | tr -d :)" /Library/Keychains/System.keychain
	rm -f $(CA_CERT)

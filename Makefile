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
# PROJECT names the compose project (default: the directory, `podman`); every
# `make up` shares it, so `make down` stops whichever ran.
COMPOSE := podman compose $(if $(PROJECT),-p $(PROJECT)) -f deploy/podman/compose.yaml
COMPOSE_S3 := $(COMPOSE) -f deploy/podman/compose.s3.yaml
S3_DIR := s3
# `make up` runs with the sightings in Garage (S3, #220) and sign-in with SSO
# against the local OIDC stub (#238, development only); S3=0 and SSO=0 leave
# either out. UP_* only: `make e2e` reads S3 and SSO as off unless set.
UP_S3 := $(if $(filter 0,$(S3)),,1)
UP_SSO := $(if $(filter 0,$(SSO)),,1)
COMPOSE_UP := $(COMPOSE) $(if $(UP_S3),-f deploy/podman/compose.s3.yaml) $(if $(UP_SSO),-f deploy/podman/compose.sso.yaml)
COMPOSE_ALL := $(COMPOSE_S3) -f deploy/podman/compose.sso.yaml
UP_ENV = FRANK_HOST=$(FRANK_HOST) FRANK_TLS_ADDR=$(FRANK_TLS_ADDR) FRANK_HTTPS_PORT=$(FRANK_HTTPS_PORT) \
  FRANK_HTTP_ADDR=$(FRANK_HTTP_ADDR) SSO_STUB_PORT=$(SSO_STUB_PORT) \
  FRANK_SSO_REDIRECT_URL=$(FRANK_URL_TLS)/v1/sso/callback FRANK_SSO_ORGANISATION=$(FRANK_SSO_ORGANISATION)
# The SSO client secret lives in ./sso/client-secret.
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
# DB-IP's free country and ASN databases (#191) and the IoC lists (#192, #193)
# are fetched by scripts/fetch-geoip.sh and scripts/fetch-lists.sh, which the
# STACKIT VM runs on timers too (#276).
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
# `make fuzz` (#245): seconds per run, on the nightly toolchain cargo-fuzz needs.
FUZZ_TIME ?= 60

.PHONY: help check build server wasm test test-slow assurance check-assurance coverage quality version smoke log-check e2e fuzz audit lint fmt run participant participants user role token demo stream-setup stream geoip lists image up sso-env s3-env s3-ls s3-browse s3-read s3-column down trust untrust clean

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
# ASSURANCE_MIN is the floor on tested scenarios (195/203 = 96%; the rest are web UI, #254); raise it as tests land.
ASSURANCE_MIN ?= 0.95
assurance: ## Spec -> code -> test traceability per spec (V=1: per requirement, with dead links)
	@python3 scripts/assurance.py $(if $(filter 1,$(V)),-v,)

version: ## Show the version; fails if Cargo.toml, both Cargo.lock, README and CHANGELOG disagree. BUMP=major|minor|patch writes the next one everywhere and dates [Unreleased]
	@python3 scripts/version.py $(if $(BUMP),--bump $(BUMP),)

# Coverage and code quality (ADR-023): measured on their own into target/assurance/,
# read by assurance and check-assurance. COVERAGE_MIN (lines, 0.0-1.0) and CCN_MAX
# turn them into gates; unset, they are shown and never fail.
LIZARD ?= uvx lizard==1.25.1
check-assurance: ## Gate: no dead spec or doc links, tested scenarios >= ASSURANCE_MIN (and COVERAGE_MIN, CCN_MAX when set); tests the checker first, quietly unless it fails, so the dashboard comes first
	@out=$$(python3 -m unittest discover -q -s scripts -p 'test_*.py' 2>&1) || { echo "$$out"; exit 1; }
	@python3 scripts/assurance.py --min $(ASSURANCE_MIN) $(if $(COVERAGE_MIN),--coverage-min $(COVERAGE_MIN),) $(if $(CCN_MAX),--ccn-max $(CCN_MAX),)

coverage: ## Test coverage with cargo llvm-cov into target/assurance/coverage.json (runs every test, instrumented)
	@$(CARGO) llvm-cov --version >/dev/null 2>&1 || { echo "cargo install cargo-llvm-cov --locked && rustup component add llvm-tools-preview"; exit 1; }
	@mkdir -p target/assurance
	$(CARGO) llvm-cov --workspace --locked --json --summary-only --output-path target/assurance/coverage.json

quality: ## Code quality with lizard (CCN, function and file length, fan-in/out) into target/assurance/lizard.csv
	@mkdir -p target/assurance
	$(LIZARD) -l rust -Eio --csv crates/*/src > target/assurance/lizard.csv.tmp
	@mv target/assurance/lizard.csv.tmp target/assurance/lizard.csv

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

fuzz: ## Fuzz frank-core's submission parsers for FUZZ_TIME (60) seconds (nightly + cargo install cargo-fuzz); crashes land in fuzz/artifacts
	mkdir -p fuzz/corpus/parse
	cd fuzz && rustup run nightly cargo fuzz run parse corpus/parse ../examples ../examples/formats ../examples/demo \
	  -- -max_total_time=$(FUZZ_TIME) -timeout=10

audit: ## cargo deny check with deny.toml (#220), as CI runs it: licences, sources, advisories (cargo install cargo-deny)
	$(CARGO) deny --locked check

smoke: ## Read-only checks of a running FRANK: make smoke TOKEN=… [FRANK_URL=…|TLS=1] [CA=…]
	@TOKEN="$(TOKEN)" $(PYTHON) scripts/smoke.py --url $(if $(TLS),$(FRANK_URL_TLS),$(FRANK_URL)) \
	  $(if $(TLS),--ca $(CA_CERT),$(if $(CA),--ca $(CA)))

log-check: ## Against make up: one request through Caddy gives a Caddy line and a frank::access line with the same X-Request-Id, and no token or cookie in either (ADR-024)
	@URL=https://localhost:$(lastword $(subst :, ,$(FRANK_TLS_ADDR))) COMPOSE="$(COMPOSE)" scripts/log_check.sh

e2e: $(if $(E2E_TAG),,image) ## Throwaway container (no Caddy), generated data, every check: [E2E_TAG=…] [E2E_PORT=18080] [KEEP=1] [S3=1: sightings in a throwaway Garage] [SSO=1: sign in through the OIDC stub] [BROWSER=1: the web UI in Obscura]
	IMAGE=$(IMAGE):$(or $(E2E_TAG),$(VERSION)) E2E_PORT=$(E2E_PORT) PYTHON="$(PYTHON)" KEEP=$(KEEP) S3=$(S3) SSO=$(SSO) BROWSER=$(BROWSER) scripts/e2e.sh

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
	@scripts/fetch-geoip.sh $(DATA)

lists: ## Download the warning (MISP, CC0) and reference (abuse.ch, CC0; Auth-Key from 1Password, ABUSE_KEY_REF) lists into data/lists; the server imports them within a minute
	@KEY=$$(op read --account "$(OP_ACCOUNT)" "$(ABUSE_KEY_REF)" 2>/dev/null) || KEY=; \
	ABUSE_KEY="$$KEY" scripts/fetch-lists.sh $(DATA)

##@ Container (podman)

image: ## Build the container image with podman
	podman build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest -f Containerfile .

up: image s3-env $(if $(UP_SSO),sso-env) ## Run in podman: http://127.0.0.1:8080 and https://frank.local:8443, the sightings in a Garage (S3) bucket (files in ./s3; S3 API on 127.0.0.1:3900, admin :3903, https://frank.local:9443) and sign-in with SSO against a local OIDC stub at http://localhost:9400 (development only: it signs in anyone who picks a name). S3=0: the table on disk in ./data; SSO=0: tokens only
	mkdir -p data participants && touch $(TOKENS)
ifneq ($(UP_S3),)
	mkdir -p $(S3_DIR)/meta $(S3_DIR)/data
	@[ -s $(S3_DIR)/garage.env ] || { umask 077; printf 'GARAGE_RPC_SECRET=%s\nGARAGE_ADMIN_TOKEN=%s\n' "$$(openssl rand -hex 32)" "$$(openssl rand -hex 32)" > $(S3_DIR)/garage.env; }
	$(UP_ENV) $(COMPOSE_UP) up -d --force-recreate garage
	FRANK_S3_ENV=$(S3_DIR)/frank.env deploy/podman/garage-init.sh "$(COMPOSE_UP)"
endif
ifneq ($(UP_SSO),)
	@# New users land in FRANK_SSO_ORGANISATION (sso-users, contributor). The
	@# stub's admin and superadmin (users.json) are linked on sign-in to these
	@# users of sbp, the main company (core), and keep their roles: SSO never
	@# grants one. No tokens: they sign in with SSO.
	@run="podman run --rm -v $(CURDIR)/participants:/participants:Z $(IMAGE):$(VERSION)"; \
	  orgs=$$($$run participant list 2>/dev/null | awk '{print $$1}'); \
	  echo "$$orgs" | grep -qxF '$(FRANK_SSO_ORGANISATION)' || $$run participant add '$(FRANK_SSO_ORGANISATION)' --status contributor; \
	  echo "$$orgs" | grep -qxF sbp || $$run participant add sbp --status core; \
	  users=$$($$run user list 2>/dev/null | awk '{print $$1}'); \
	  for r in admin superadmin; do \
	    echo "$$users" | grep -qxF "$$r@sbp.example" || $$run user add sbp "$$r@sbp.example" --role $$r; \
	  done
endif
	$(UP_ENV) $(COMPOSE_UP) up -d $(if $(UP_SSO),--build) --force-recreate --remove-orphans
	@echo "FRANK: $(FRANK_URL_TLS) (http://$(FRANK_HOST) redirects there; once: make trust), API also at http://127.0.0.1:$${FRANK_PORT:-8080}"
	@echo "  sightings: $(if $(UP_S3),in Garage: S3 http://127.0.0.1:$${GARAGE_S3_PORT:-3900} and https://$(FRANK_HOST):$${GARAGE_TLS_PORT:-9443}; make s3-ls lists the bucket,in ./data (S3=0))"
	@echo "  sign-in:   $(if $(UP_SSO),SSO through the stub at http://localhost:$(SSO_STUB_PORT)/oauth2/default (development only) or a token,a token (SSO=0))"

# The OIDC client secret shared by FRANK and the stub (#238): made once,
# never printed, git-ignored. The directory is private (700); the file is
# 644 so the containers' own users (65532, 65533) can read the bind mount.
sso-env:
	@mkdir -p $(SSO_DIR) && chmod 700 $(SSO_DIR)
	@[ -s $(SSO_DIR)/client-secret ] || { umask 077; openssl rand -hex 32 > $(SSO_DIR)/client-secret; }
	@chmod 644 $(SSO_DIR)/client-secret

# The compose files name s3/*.env, which must exist for any compose command,
# also with S3=0 and in down. Empty until `make up` with S3 fills them.
s3-env:
	@mkdir -p $(S3_DIR) && chmod 700 $(S3_DIR) && (umask 077; touch $(S3_DIR)/garage.env $(S3_DIR)/frank.env) && chmod 600 $(S3_DIR)/garage.env $(S3_DIR)/frank.env

s3-ls: s3-env ## List the objects in the Garage bucket (after make up)
	@$(COMPOSE_S3) exec -T garage /garage bucket info frank
	@set -a; . $(S3_DIR)/frank.env; set +a; \
	  printf 'user = "%s:%s"\n' "$$AWS_ACCESS_KEY_ID" "$$AWS_SECRET_ACCESS_KEY" \
	  | curl -fsS --config - --aws-sigv4 "aws:amz:garage:s3" "http://127.0.0.1:$${GARAGE_S3_PORT:-3900}/frank?list-type=2" \
	  | sed 's|<Contents>|\n|g' | sed -n 's|.*<Key>\([^<]*\)</Key>.*<Size>\([0-9]*\)</Size>.*|\2\t\1|p'

s3-browse: s3-env ## Browse the Garage bucket in the terminal with rclone ncdu (brew install rclone, after make up); S3_PATH=sightings/live starts deeper
	@command -v rclone >/dev/null || { echo "s3-browse: rclone is not installed (brew install rclone)" >&2; exit 1; }
	@[ -s $(S3_DIR)/frank.env ] || { echo "s3-browse: no $(S3_DIR)/frank.env; run make up first" >&2; exit 1; }
	@set -a; . $(S3_DIR)/frank.env; set +a; \
	  RCLONE_CONFIG_GARAGE_TYPE=s3 RCLONE_CONFIG_GARAGE_PROVIDER=Other RCLONE_CONFIG_GARAGE_ENV_AUTH=true \
	  RCLONE_CONFIG_GARAGE_REGION=garage RCLONE_CONFIG_GARAGE_ENDPOINT=http://127.0.0.1:$${GARAGE_S3_PORT:-3900} \
	  rclone ncdu garage:frank/$(S3_PATH)

s3-read: s3-env ## DuckDB on the sightings in the Garage bucket (brew install duckdb, after make up): view `sightings`; SQL="SELECT …" runs one query
	@scripts/read-garage.sh

s3-column: s3-env ## column-rs (0.46+, built with --features s3-tls) on the sightings in the Garage bucket over https://frank.local:9443 (after make up and make trust; COLUMN_RS=path if not on the PATH): SQL="SELECT …" runs one query; TLS=0 reads http://127.0.0.1:3900 (0.45+); URL=s3://bucket/prefix?endpoint=…&region=… reads any location (AWS)
	@TLS="$(TLS)" URL="$(URL)" FRANK_HOST=$(FRANK_HOST) CA_CERT=$(CA_CERT) scripts/read-garage-column.sh

down: s3-env sso-env ## Stop the podman deployment, whatever S3 and SSO were (the data stays)
	$(COMPOSE_ALL) down --remove-orphans

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

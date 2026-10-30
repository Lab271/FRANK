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
COMPOSE := podman compose -f deploy/podman/compose.yaml
N ?= 60
RATE ?= 60
DURATION ?= 1h
# The MaxMind GeoLite2 licence key, read from 1Password when `make geoip` runs (#191).
GEOIP_KEY_REF ?= op://Private/MaxMind GeoLite2/license key
GEOIP_DIR := $(DATA)/geoip/geolite2

.PHONY: help check build server wasm test lint fmt run participant participants user role token demo stream-setup stream geoip image up down clean

##@ General

help: ## Show targets by section (colour on a terminal, unless NO_COLOR is set)
	@if [ -t 1 ] && [ -z "$$NO_COLOR" ]; then b=$$'\033[1m'; c=$$'\033[36m'; d=$$'\033[2m'; r=$$'\033[0m'; fi; \
	awk -v b="$$b" -v c="$$c" -v d="$$d" -v r="$$r" ' \
	  BEGIN { FS = ":.*## "; printf "%sFRANK %s%s  %smake <target> [VAR=value]%s\n", b, "$(VERSION)", r, d, r } \
	  /^##@/ { printf "\n%s%s%s\n", b, substr($$0, 5), r; next } \
	  /^[a-z-]+:.*## / { printf "  %s%-13s%s %s\n", c, $$1, r, $$2 }' $(MAKEFILE_LIST)

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

lint: ## fmt check + clippy (native and wasm32), as CI runs them
	$(CARGO) fmt --all --check
	$(CARGO) clippy --workspace --all-targets --locked -- -D warnings
	$(CARGO) clippy -p frank-wasm --target wasm32-unknown-unknown --locked -- -D warnings

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

##@ Data

demo: server ## Load N (60) synthetic sightings from the last 7 days into ./data (server stopped)
	@! pgrep -f "frank.* serve" >/dev/null || { echo "stop the running frank server first (it holds the table lock), or POST the file to /v1/sightings" >&2; exit 1; }
	python3 scripts/demo_sightings.py $(N) target/demo
	@for f in target/demo/mdr-*.json; do \
	  FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) $(FRANK) ingest --as "$$(basename $$f .json)" --create $$f || exit 1; \
	done

stream-setup: server ## Register the checked-in test tokens (scripts/stream_tokens.json) in ./participants; local only
	@FRANK_DATA=$(DATA) FRANK_PARTICIPANTS=$(PARTICIPANTS) python3 scripts/stream_sightings.py --setup --frank $(FRANK)

stream: ## Stream sightings through the API and watch the table: make stream RATE=60 DURATION=1h [FRANK_URL=…]
	python3 scripts/stream_sightings.py --rate $(RATE) --duration $(DURATION)

geoip: ## Download GeoLite2 Country + ASN into data/geoip/geolite2 (licence key from 1Password, GEOIP_KEY_REF)
	@command -v op >/dev/null || { echo "needs the 1Password CLI (op)" >&2; exit 1; }
	@install -d -m 700 $(DATA)/geoip $(GEOIP_DIR)
	@set -euo pipefail; KEY=$$(op read "$(GEOIP_KEY_REF)"); \
	tmp=$$(mktemp -d $(DATA)/geoip/.download.XXXXXX); trap 'rm -rf "$$tmp"' EXIT; \
	for ed in GeoLite2-Country GeoLite2-ASN; do \
	  printf 'url = "https://download.maxmind.com/app/geoip_download?edition_id=%s&license_key=%s&suffix=tar.gz"\n' "$$ed" "$$KEY" \
	    | curl -fsSL --config - | tar -xz -C "$$tmp"; \
	done; \
	chmod 600 "$$tmp"/*/*; mv -f "$$tmp"/*/*.mmdb "$$tmp"/*/*.txt $(GEOIP_DIR)/
	@ls -l $(GEOIP_DIR)

##@ Container (podman)

image: ## Build the container image with podman
	podman build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest -f Containerfile .

up: image ## Run in podman (the same ./data and ./participants as run; FRANK_PORT, default 8080)
	mkdir -p data participants && touch $(TOKENS)
	$(COMPOSE) up -d --force-recreate

down: ## Stop the podman deployment
	$(COMPOSE) down

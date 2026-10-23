# FRANK Phase 3 (ADR-016). Phase 2 (Python) lives in legacy/phase2.
SHELL := /bin/bash
CARGO ?= rustup run stable cargo
DATA ?= ./data
TOKENS ?= ./tokens
IMAGE ?= ghcr.io/lab271/frank
VERSION := $(shell sed -n 's/^version = "\(.*\)"/\1/p' Cargo.toml | head -1)
WASM_BINDGEN_VERSION := 0.2.129
FRANK := target/release/frank
COMPOSE := podman compose -f deploy/podman/compose.yaml
N ?= 60

.PHONY: help check build server wasm test lint fmt run participant participants user token demo image up down clean

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-13s %s\n", $$1, $$2}'

check: ## Verify the toolchain
	@rustup target list --installed | grep -q wasm32-unknown-unknown || { echo "rustup target add wasm32-unknown-unknown"; exit 1; }
	@wasm-bindgen --version | grep -q $(WASM_BINDGEN_VERSION) || { echo "cargo install wasm-bindgen-cli --version $(WASM_BINDGEN_VERSION) --locked"; exit 1; }
	@echo "toolchain ok"

build: server wasm ## Build the server (release) and the browser module

server: ## Build the server binary only
	$(CARGO) build --release --locked -p frank

wasm: ## Build web/pkg (frank-wasm for the browser)
	$(CARGO) build --release --locked -p frank-wasm --target wasm32-unknown-unknown
	wasm-bindgen --target web --no-typescript --out-dir web/pkg \
		target/wasm32-unknown-unknown/release/frank_wasm.wasm

test: ## Run all tests
	$(CARGO) test --workspace --locked

lint: ## fmt check + clippy (native and wasm32), as CI runs them
	$(CARGO) fmt --all --check
	$(CARGO) clippy --workspace --all-targets --locked -- -D warnings
	$(CARGO) clippy -p frank-wasm --target wasm32-unknown-unknown --locked -- -D warnings

fmt: ## Format the code
	$(CARGO) fmt --all

run: build ## Run on this machine (data in ./data, shared with up)
	FRANK_DATA=$(DATA) FRANK_TOKENS=$(TOKENS) $(FRANK) serve

# Participants, users and tokens live in $(DATA)/participants.db and take
# effect on the next request, with the server running or not.
participant: server ## Register an organisation with a token: make participant NAME=me STATUS=partner
	@[ -n "$(NAME)" ] && [ -n "$(STATUS)" ] || { echo "usage: make participant NAME=<organisation> STATUS=observer|contributor|partner|core" >&2; exit 2; }
	@FRANK_DATA=$(DATA) $(FRANK) participant add "$(NAME)" --status $(STATUS) --with-token

participants: server ## List organisations and tokens
	@FRANK_DATA=$(DATA) $(FRANK) participant list
	@FRANK_DATA=$(DATA) $(FRANK) token list

user: server ## Add a user with a token: make user PARTICIPANT=me NAME=alice [MACHINE=1]
	@[ -n "$(PARTICIPANT)" ] && [ -n "$(NAME)" ] || { echo "usage: make user PARTICIPANT=<organisation> NAME=<user> [MACHINE=1]" >&2; exit 2; }
	@FRANK_DATA=$(DATA) $(FRANK) user add "$(PARTICIPANT)" "$(NAME)" $(if $(MACHINE),--machine)
	@FRANK_DATA=$(DATA) $(FRANK) token new "$(NAME)"

token: server ## Another token for a user: make token NAME=alice
	@[ -n "$(NAME)" ] || { echo "usage: make token NAME=<user>" >&2; exit 2; }
	@FRANK_DATA=$(DATA) $(FRANK) token new "$(NAME)"

demo: server ## Load N (60) synthetic sightings from the last 7 days into ./data (server stopped)
	@! pgrep -f "frank.* serve" >/dev/null || { echo "stop the running frank server first (it holds the table lock), or POST the file to /v1/sightings" >&2; exit 1; }
	python3 scripts/demo_sightings.py $(N) target/demo
	@for f in target/demo/mdr-*.json; do \
	  FRANK_DATA=$(DATA) $(FRANK) ingest --as "$$(basename $$f .json)" --create $$f || exit 1; \
	done

image: ## Build the container image with podman
	podman build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest -f Containerfile .

up: image ## Run in podman (data in deploy/podman/data, tokens shared with run; FRANK_PORT, default 8080)
	mkdir -p deploy/podman/data && touch $(TOKENS)
	$(COMPOSE) up -d --force-recreate

down: ## Stop the podman deployment
	$(COMPOSE) down

clean: ## Remove build output
	$(CARGO) clean
	rm -rf web/pkg

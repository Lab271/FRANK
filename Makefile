# FRANK Phase 3 (ADR-016). Phase 2 (Python) lives in legacy/phase2.
SHELL := /bin/bash
CARGO ?= rustup run stable cargo
DATA ?= ./data
IMAGE ?= ghcr.io/lab271/frank
VERSION := $(shell sed -n 's/^version = "\(.*\)"/\1/p' Cargo.toml | head -1)
WASM_BINDGEN_VERSION := 0.2.129

.PHONY: help build wasm test lint fmt run token demo image up podman-token down clean check

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

check: ## Verify the toolchain
	@rustup target list --installed | grep -q wasm32-unknown-unknown || { echo "rustup target add wasm32-unknown-unknown"; exit 1; }
	@wasm-bindgen --version | grep -q $(WASM_BINDGEN_VERSION) || { echo "cargo install wasm-bindgen-cli --version $(WASM_BINDGEN_VERSION) --locked"; exit 1; }
	@echo "toolchain ok"

build: wasm ## Build the server (release) and the browser module
	$(CARGO) build --release -p frank

wasm: ## Build web/pkg (frank-wasm for the browser)
	$(CARGO) build --release -p frank-wasm --target wasm32-unknown-unknown
	wasm-bindgen --target web --no-typescript --out-dir web/pkg \
		target/wasm32-unknown-unknown/release/frank_wasm.wasm

test: ## Run all tests
	$(CARGO) test --workspace

lint: ## fmt check + clippy
	$(CARGO) fmt --all --check
	$(CARGO) clippy --workspace --all-targets -- -D warnings
	$(CARGO) clippy -p frank-wasm --target wasm32-unknown-unknown -- -D warnings

fmt: ## Format the code
	$(CARGO) fmt --all

run: build ## Run on this machine (data in ./data, tokens in ./tokens)
	FRANK_DATA=$(DATA) target/release/frank serve

token: ## Create a token: make token TIER=partner LABEL=me
	@target/release/frank token $(TIER) "$(LABEL)"

demo: build ## Load the example submissions into ./data
	target/release/frank ingest examples/minimal.json examples/demo/*.json

image: ## Build the container image with podman
	podman build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest -f Containerfile .

up: ## Run in podman (data and tokens on the host under ./deploy/podman)
	mkdir -p deploy/podman/data && touch deploy/podman/tokens
	podman compose -f deploy/podman/compose.yaml up -d

podman-token: ## Token for the podman deployment: make podman-token TIER=partner LABEL=me
	@touch deploy/podman/tokens
	@podman run --rm -v $(CURDIR)/deploy/podman/tokens:/etc/frank/tokens:Z $(IMAGE):latest token $(TIER) "$(LABEL)"
	@echo "restart to load it: podman compose -f deploy/podman/compose.yaml restart" >&2

down: ## Stop the podman deployment
	podman compose -f deploy/podman/compose.yaml down

clean: ## Remove build output
	$(CARGO) clean
	rm -rf web/pkg

# FRANK Phase 3 image: the server plus the web UI and its WASM module.
#   podman build -t ghcr.io/lab271/frank -f Containerfile .
# Data lives outside the container: mount host directories on /data and
# /participants.

FROM docker.io/library/rust:1.98-slim AS build
ARG WASM_BINDGEN_VERSION=0.2.129
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && rustup target add wasm32-unknown-unknown \
 && cargo install wasm-bindgen-cli --version ${WASM_BINDGEN_VERSION} --locked
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY crates crates
COPY examples examples
COPY web web
RUN cargo build --release --locked -p frank \
 && cargo build --release --locked -p frank-wasm --target wasm32-unknown-unknown \
 && wasm-bindgen --target web --no-typescript --out-dir web/pkg \
      target/wasm32-unknown-unknown/release/frank_wasm.wasm

FROM gcr.io/distroless/cc-debian12:nonroot
COPY --from=build /src/target/release/frank /usr/local/bin/frank
COPY --from=build /src/web /srv/frank/web
ENV FRANK_DATA=/data \
    FRANK_PARTICIPANTS=/participants \
    FRANK_TOKENS=/etc/frank/tokens \
    FRANK_WEB=/srv/frank/web \
    FRANK_LISTEN=0.0.0.0:8080
VOLUME ["/data", "/participants"]
EXPOSE 8080
USER 65532:65532
ENTRYPOINT ["/usr/local/bin/frank"]
CMD ["serve"]

# FRANK Phase 3 image: the server plus the web UI and its WASM module.
#   podman build -t ghcr.io/lab271/frank -f Containerfile .
# Data lives outside the container: mount host directories on /data and
# /participants.
#
# The runtime image is FROM scratch (#211): frank is a static musl binary.
# FRANK has no C dependencies and no TLS stack (TLS ends in front of it),
# so it needs no userland: no libc, CA certificates or tzdata. The build
# image is pinned by its multi-arch index digest; Dependabot bumps it.

FROM docker.io/library/rust:1.96-slim@sha256:31ee7fc65186be7e0e0ccb3f2ca305f14e4739e7642a1ae65753aa5d7b874523 AS build
ARG WASM_BINDGEN_VERSION=0.2.129
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && rustup target add wasm32-unknown-unknown "$(uname -m)-unknown-linux-musl" \
 && cargo install wasm-bindgen-cli --version ${WASM_BINDGEN_VERSION} --locked
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY crates crates
COPY examples examples
COPY docs/openapi.yaml docs/openapi.yaml
COPY web web
RUN target="$(uname -m)-unknown-linux-musl" \
 && cargo build --release --locked -p frank --target "$target" \
 && cargo build --release --locked -p frank-wasm --target wasm32-unknown-unknown \
 && wasm-bindgen --target web --no-typescript --out-dir web/pkg \
      target/wasm32-unknown-unknown/release/frank_wasm.wasm \
 && mkdir -p /out/etc \
 && cp "target/$target/release/frank" /out/frank \
 && echo 'nonroot:x:65532:65532:nonroot:/nonexistent:/sbin/nologin' >/out/etc/passwd \
 && echo 'nonroot:x:65532:' >/out/etc/group

FROM scratch
COPY --from=build /out/etc/passwd /out/etc/group /etc/
COPY --from=build /out/frank /usr/local/bin/frank
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

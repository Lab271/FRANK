# FRANK Phase 3 image: the server plus the web UI and its WASM module.
#   podman build -t ghcr.io/lab271/frank -f Containerfile .
# Data lives outside the container: mount host directories on /data and
# /participants.
#
# The runtime image is FROM scratch (#211): frank is a static musl binary,
# with no libc or tzdata. Its one TLS client is for an S3 store over HTTPS
# (AWS, #220: the `tls` feature, rustls with ring); it trusts the CA bundle
# copied in below. Inbound TLS ends in front of it. The build image is
# pinned by its multi-arch index digest; Dependabot bumps it.
# cargo auditable embeds the crate list in the binary (#213), so scanners
# (syft, trivy, grype) can read a scratch image; CI turns it into the SBOM.

FROM docker.io/library/rust:1.98-slim@sha256:4cd829461bd5c4d511c32e269da9cb8929223b666519d8004e35fc8d1d771ab7 AS build
ARG WASM_BINDGEN_VERSION=0.2.129
ARG CARGO_AUDITABLE_VERSION=0.7.7
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/* \
 && rustup target add wasm32-unknown-unknown "$(uname -m)-unknown-linux-musl" \
 && cargo install wasm-bindgen-cli --version ${WASM_BINDGEN_VERSION} --locked \
 && cargo install cargo-auditable --version ${CARGO_AUDITABLE_VERSION} --locked
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY crates crates
COPY examples examples
COPY docs/openapi.yaml docs/openapi.yaml
COPY web web
# ring's assembly and C are built by the glibc gcc for the musl target.
RUN target="$(uname -m)-unknown-linux-musl" \
 && export "CC_$(uname -m)_unknown_linux_musl=gcc" \
 && cargo auditable build --release --locked -p frank --features tls --target "$target" \
 && cargo build --release --locked -p frank-wasm --target wasm32-unknown-unknown \
 && wasm-bindgen --target web --no-typescript --out-dir web/pkg \
      target/wasm32-unknown-unknown/release/frank_wasm.wasm \
 && mkdir -p /out/etc/ssl/certs \
 && cp /etc/ssl/certs/ca-certificates.crt /out/etc/ssl/certs/ \
 && cp "target/$target/release/frank" /out/frank \
 && echo 'nonroot:x:65532:65532:nonroot:/nonexistent:/sbin/nologin' >/out/etc/passwd \
 && echo 'nonroot:x:65532:' >/out/etc/group

FROM scratch
COPY --from=build /out/etc/passwd /out/etc/group /etc/
COPY --from=build /out/etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
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

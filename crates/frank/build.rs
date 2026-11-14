//! Embeds the runtime manifest (#315, mvl-manifest): app identity, toolchain,
//! build configuration, source digests and every package in the binary.
//! `frank serve` logs it at start (`frank::serve::log_manifest`).

fn main() {
    mvl_manifest::build::generate().expect("mvl manifest");
}

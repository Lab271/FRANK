//! A request body into `frank_core::formats::parse`, as `/v1/submissions`
//! and `/v1/preview` call it: in each format, and in the one `sniff`
//! picks. Any input may be refused; none may panic, overflow the stack
//! or hang.
#![no_main]

use frank_core::formats::{parse, Format};
use libfuzzer_sys::fuzz_target;

const NOW_NS: i64 = 1_794_000_000_000_000_000;

fuzz_target!(|data: &[u8]| {
    // The server reads the body as UTF-8 before it parses it.
    let Ok(text) = std::str::from_utf8(data) else {
        return;
    };
    for format in [Format::Json, Format::Yaml, Format::Stix, Format::sniff(text)] {
        let _ = parse(text, format, NOW_NS);
    }
});

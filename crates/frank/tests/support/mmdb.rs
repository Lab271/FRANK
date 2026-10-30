//! A small MaxMind DB writer for tests (#191): format 2.0, IPv6 tree with
//! IPv4 under `::/96`, 24-bit records. Enough for a few networks; it does
//! not merge or split overlapping ones.
//! https://maxmind.github.io/MaxMind-DB/

use std::net::IpAddr;
use std::path::Path;

pub enum Val {
    Str(&'static str),
    U16(u16),
    U32(u32),
    U64(u64),
    Map(Vec<(&'static str, Val)>),
    Array(Vec<Val>),
}

/// The value of a country record.
pub fn country(iso: &'static str) -> Val {
    Val::Map(vec![(
        "country",
        Val::Map(vec![("iso_code", Val::Str(iso))]),
    )])
}

/// The value of an ASN record.
pub fn asn(n: u32, org: &'static str) -> Val {
    Val::Map(vec![
        ("autonomous_system_number", Val::U32(n)),
        ("autonomous_system_organization", Val::Str(org)),
    ])
}

fn control(out: &mut Vec<u8>, kind: u8, size: usize) {
    let (low, extra): (u8, Vec<u8>) = match size {
        0..=28 => (u8::try_from(size).unwrap(), vec![]),
        29..=284 => (29, vec![u8::try_from(size - 29).unwrap()]),
        _ => {
            let s = u16::try_from(size - 285).unwrap();
            (30, s.to_be_bytes().to_vec())
        }
    };
    if kind <= 7 {
        out.push((kind << 5) | low);
    } else {
        out.push(low);
        out.push(kind - 7);
    }
    out.extend(extra);
}

fn uint(out: &mut Vec<u8>, kind: u8, n: u64) {
    let bytes: Vec<u8> = n
        .to_be_bytes()
        .into_iter()
        .skip_while(|b| *b == 0)
        .collect();
    control(out, kind, bytes.len());
    out.extend(bytes);
}

fn encode(out: &mut Vec<u8>, v: &Val) {
    match v {
        Val::Str(s) => {
            control(out, 2, s.len());
            out.extend(s.as_bytes());
        }
        Val::U16(n) => uint(out, 5, u64::from(*n)),
        Val::U32(n) => uint(out, 6, u64::from(*n)),
        Val::U64(n) => uint(out, 9, *n),
        Val::Map(entries) => {
            control(out, 7, entries.len());
            for (k, v) in entries {
                encode(out, &Val::Str(k));
                encode(out, v);
            }
        }
        Val::Array(items) => {
            control(out, 11, items.len());
            for i in items {
                encode(out, i);
            }
        }
    }
}

#[derive(Clone, Copy)]
enum Rec {
    Empty,
    Node(usize),
    Data(usize),
}

/// Writes a database of `networks` (`"192.0.2.0/24"`, `"2001:db8::/32"`)
/// to `path`, with 24-bit records.
pub fn write(
    path: &Path,
    database_type: &'static str,
    networks: Vec<(&str, Val)>,
    build_epoch: u64,
) {
    write_with(path, database_type, networks, build_epoch, 24);
}

/// [`write`] with `record_size` 24, 28 or 32.
pub fn write_with(
    path: &Path,
    database_type: &'static str,
    networks: Vec<(&str, Val)>,
    build_epoch: u64,
    record_size: u16,
) {
    let mut data = Vec::new();
    let mut nodes: Vec<[Rec; 2]> = vec![[Rec::Empty; 2]];
    for (cidr, value) in networks {
        let (addr, len) = cidr.split_once('/').unwrap();
        let len: u32 = len.parse().unwrap();
        let (bits, len) = match addr.parse::<IpAddr>().unwrap() {
            IpAddr::V4(v4) => (u128::from(u32::from(v4)), len + 96),
            IpAddr::V6(v6) => (u128::from(v6), len),
        };
        let offset = data.len();
        encode(&mut data, &value);
        let mut node = 0;
        for depth in 0..len {
            let bit = usize::from((bits >> (127 - depth)) & 1 == 1);
            if depth + 1 == len {
                nodes[node][bit] = Rec::Data(offset);
            } else {
                node = match nodes[node][bit] {
                    Rec::Node(n) => n,
                    _ => {
                        nodes.push([Rec::Empty; 2]);
                        let n = nodes.len() - 1;
                        nodes[node][bit] = Rec::Node(n);
                        n
                    }
                };
            }
        }
    }
    let count = nodes.len();
    let mut out = Vec::new();
    for pair in &nodes {
        let [l, r] = pair.map(|r| {
            u32::try_from(match r {
                Rec::Empty => count,
                Rec::Node(n) => n,
                Rec::Data(off) => count + 16 + off,
            })
            .unwrap()
        });
        match record_size {
            24 => {
                out.extend(&l.to_be_bytes()[1..]);
                out.extend(&r.to_be_bytes()[1..]);
            }
            28 => {
                // The left record's top nibble, then the right's, in the middle byte.
                out.extend(&l.to_be_bytes()[1..]);
                out.push(u8::try_from(((l >> 24) << 4) | (r >> 24)).unwrap());
                out.extend(&r.to_be_bytes()[1..]);
            }
            _ => {
                out.extend(l.to_be_bytes());
                out.extend(r.to_be_bytes());
            }
        }
    }
    out.extend([0u8; 16]);
    out.extend(&data);
    out.extend(b"\xAB\xCD\xEFMaxMind.com");
    encode(
        &mut out,
        &Val::Map(vec![
            ("binary_format_major_version", Val::U16(2)),
            ("binary_format_minor_version", Val::U16(0)),
            ("build_epoch", Val::U64(build_epoch)),
            ("database_type", Val::Str(database_type)),
            (
                "description",
                Val::Map(vec![("en", Val::Str("FRANK test database"))]),
            ),
            ("ip_version", Val::U16(6)),
            ("languages", Val::Array(vec![Val::Str("en")])),
            ("node_count", Val::U32(u32::try_from(count).unwrap())),
            ("record_size", Val::U16(record_size)),
        ]),
    );
    std::fs::create_dir_all(path.parent().unwrap()).unwrap();
    std::fs::write(path, out).unwrap();
}

/// Country and ASN databases under `data/geoip/dbip-lite/`, named as
/// DB-IP names them: 192.0.2.0/24 is NL in AS64496, 2001:db8::/32 is DE
/// in AS64497.
pub fn dbip(data: &Path, build_epoch: u64) {
    let dir = data.join("geoip/dbip-lite");
    write(
        &dir.join("dbip-country-lite.mmdb"),
        "DBIP-Country-Lite",
        vec![
            ("192.0.2.0/24", country("NL")),
            ("2001:db8::/32", country("DE")),
        ],
        build_epoch,
    );
    write(
        &dir.join("dbip-asn-lite.mmdb"),
        "DBIP-ASN-Lite (compat=GeoLite2-ASN)",
        vec![
            ("192.0.2.0/24", asn(64496, "Example Net")),
            ("2001:db8::/32", asn(64497, "Example Six")),
        ],
        build_epoch,
    );
}

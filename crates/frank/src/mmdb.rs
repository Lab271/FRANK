//! A reader for MaxMind DB files, format 2.0 (#191), enough for FRANK's
//! country and ASN lookups: the search tree (24, 28 or 32-bit records, IPv4 under
//! `::/96` in an IPv6 tree) and the data section's types. Every read is
//! bounds-checked, so a truncated or corrupt file is an error, not a panic.
//! <https://maxmind.github.io/MaxMind-DB/>

use std::net::IpAddr;
use std::path::Path;

const MARKER: &[u8] = b"\xAB\xCD\xEFMaxMind.com";
/// The metadata is within this many bytes of the end.
const META_MAX: usize = 128 * 1024;
/// Deepest nesting of maps and arrays decoded.
const MAX_DEPTH: usize = 32;

/// A decoded value.
#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Str(String),
    Uint(u128),
    Int(i32),
    Double(f64),
    Float(f32),
    Bool(bool),
    Bytes(Vec<u8>),
    Map(Vec<(String, Value)>),
    Array(Vec<Value>),
}

impl Value {
    /// The value under the map keys `path`.
    #[must_use]
    pub fn get(&self, path: &[&str]) -> Option<&Value> {
        path.iter().try_fold(self, |v, k| match v {
            Value::Map(m) => m.iter().find(|(mk, _)| mk == k).map(|(_, v)| v),
            _ => None,
        })
    }

    #[must_use]
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::Str(s) => Some(s),
            _ => None,
        }
    }

    #[must_use]
    pub fn as_u64(&self) -> Option<u64> {
        match self {
            Value::Uint(n) => u64::try_from(*n).ok(),
            _ => None,
        }
    }
}

/// An open database.
pub struct Mmdb {
    buf: Vec<u8>,
    node_count: usize,
    record_size: usize,
    /// Bytes of the search tree; the data section starts 16 bytes after.
    tree_size: usize,
    ipv6: bool,
    /// Where IPv4 lookups start in an IPv6 tree.
    ipv4_start: usize,
    pub database_type: String,
    /// Seconds since the epoch.
    pub build_epoch: u64,
}

fn bad(why: &str) -> String {
    format!("not a usable MaxMind DB: {why}")
}

impl Mmdb {
    pub fn open(path: &Path) -> Result<Mmdb, String> {
        Mmdb::from_bytes(std::fs::read(path).map_err(|e| e.to_string())?)
    }

    pub fn from_bytes(buf: Vec<u8>) -> Result<Mmdb, String> {
        let at = metadata_start(&buf)?;
        let (meta, _) = decode(&buf, at, at, 0)?;
        let num = |k: &str| meta_num(&meta, k);
        if num("binary_format_major_version")? != 2 {
            return Err(bad("not format 2"));
        }
        let (node_count, record_size, tree_size) = tree_shape(&meta, at)?;
        let mut db = Mmdb {
            buf,
            node_count,
            record_size,
            tree_size,
            ipv6: num("ip_version")? == 6,
            ipv4_start: 0,
            database_type: meta
                .get(&["database_type"])
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string(),
            build_epoch: num("build_epoch")?,
        };
        if db.ipv6 {
            db.ipv4_start = db.ipv4_node()?;
        }
        Ok(db)
    }

    /// The node `::/96` leads to, where IPv4 lookups start in an IPv6 tree.
    fn ipv4_node(&self) -> Result<usize, String> {
        let mut node = 0;
        for _ in 0..96 {
            if node >= self.node_count {
                break;
            }
            node = self.record(node, 0)?;
        }
        Ok(node)
    }

    /// Record `side` (0 left, 1 right) of node `n`.
    fn record(&self, n: usize, side: usize) -> Result<usize, String> {
        let size = self.record_size / 4;
        let b = self
            .buf
            .get(n * size..n * size + size)
            .ok_or_else(|| bad("node past the end"))?;
        let be = |s: &[u8]| s.iter().fold(0usize, |a, x| (a << 8) | usize::from(*x));
        Ok(match (self.record_size, side) {
            (24, 0) => be(&b[0..3]),
            (24, _) => be(&b[3..6]),
            (28, 0) => (usize::from(b[3] & 0xF0) << 20) | be(&b[0..3]),
            (28, _) => (usize::from(b[3] & 0x0F) << 24) | be(&b[4..7]),
            (_, 0) => be(&b[0..4]),
            _ => be(&b[4..8]),
        })
    }

    /// The record for `ip`, or `None` when the database has none.
    pub fn lookup(&self, ip: IpAddr) -> Result<Option<Value>, String> {
        let (bits, mut node, len) = match ip {
            IpAddr::V4(v4) if self.ipv6 => (u128::from(u32::from(v4)), self.ipv4_start, 32),
            IpAddr::V4(v4) => (u128::from(u32::from(v4)), 0, 32),
            IpAddr::V6(v6) if self.ipv6 => (u128::from(v6), 0, 128),
            IpAddr::V6(_) => return Ok(None),
        };
        for i in 0..len {
            if node >= self.node_count {
                break;
            }
            let bit = usize::from((bits >> (len - 1 - i)) & 1 == 1);
            node = self.record(node, bit)?;
        }
        if node == self.node_count {
            return Ok(None);
        }
        if node < self.node_count {
            return Err(bad("search tree ends in a node"));
        }
        let data = self.tree_size + 16;
        let at = self.tree_size + (node - self.node_count);
        decode(&self.buf, data, at, 0).map(|(v, _)| Some(v))
    }
}

/// Where the metadata map starts: just after the last marker.
fn metadata_start(buf: &[u8]) -> Result<usize, String> {
    let from = buf.len().saturating_sub(META_MAX);
    buf[from..]
        .windows(MARKER.len())
        .rposition(|w| w == MARKER)
        .map(|i| from + i + MARKER.len())
        .ok_or_else(|| bad("no metadata"))
}

/// The unsigned number under the metadata key `k`.
fn meta_num(meta: &Value, k: &str) -> Result<u64, String> {
    meta.get(&[k])
        .and_then(Value::as_u64)
        .ok_or_else(|| bad(&format!("metadata has no {k}")))
}

/// The node count, record size and search tree size from the metadata,
/// checked against `at`, where the metadata starts.
fn tree_shape(meta: &Value, at: usize) -> Result<(usize, usize, usize), String> {
    let num = |k: &str| meta_num(meta, k);
    let node_count = usize::try_from(num("node_count")?).map_err(|_| bad("node_count"))?;
    let record_size = usize::try_from(num("record_size")?).map_err(|_| bad("record_size"))?;
    if !matches!(record_size, 24 | 28 | 32) {
        return Err(bad("record size"));
    }
    let tree_size = node_count
        .checked_mul(record_size / 4)
        .filter(|t| t + 16 <= at)
        .ok_or_else(|| bad("search tree past the end"))?;
    Ok((node_count, record_size, tree_size))
}

/// Decodes the payload of one data type: from `buf`, with pointers from
/// `base`, the payload at `p` of `size` (from the control byte), nested
/// `depth` deep. Returns the value and where the next one starts.
type Decoder = fn(&[u8], usize, usize, usize, usize) -> Result<(Value, usize), String>;

/// The decoder of each data type, by type number; `None` for the ones
/// handled before (0 extended, 1 pointer) or not values (12 data cache
/// container, 13 end marker).
const DECODERS: [Option<Decoder>; 16] = [
    None,
    None,
    Some(decode_str),
    Some(decode_double),
    Some(decode_bytes),
    Some(decode_uint),
    Some(decode_uint),
    Some(decode_map),
    Some(decode_int32),
    Some(decode_uint),
    Some(decode_uint),
    Some(decode_array),
    None,
    None,
    Some(decode_bool),
    Some(decode_float),
];

/// The value at `at`, and where the next one starts. Pointers are offsets
/// from `base`, the start of the data section.
fn decode(buf: &[u8], base: usize, at: usize, depth: usize) -> Result<(Value, usize), String> {
    if depth > MAX_DEPTH {
        return Err(bad("nested too deeply"));
    }
    let ctrl = byte(buf, at)?;
    let mut p = at + 1;
    let mut kind = ctrl >> 5;
    if kind == 1 {
        return decode_pointer(buf, base, ctrl, p, depth);
    }
    if kind == 0 {
        kind = byte(buf, p)?.checked_add(7).ok_or_else(|| bad("type"))?;
        p += 1;
    }
    let (size, p) = payload_size(buf, ctrl, p)?;
    let decoder = DECODERS
        .get(usize::from(kind))
        .copied()
        .flatten()
        .ok_or_else(|| bad("unknown type"))?;
    decoder(buf, base, p, size, depth)
}

fn byte(buf: &[u8], i: usize) -> Result<u8, String> {
    buf.get(i).copied().ok_or_else(|| bad("value past the end"))
}

fn take(buf: &[u8], from: usize, n: usize) -> Result<&[u8], String> {
    buf.get(from..from + n)
        .ok_or_else(|| bad("value past the end"))
}

fn be(s: &[u8]) -> u128 {
    s.iter().fold(0u128, |a, x| (a << 8) | u128::from(*x))
}

/// The pointer with control byte `ctrl` and its offset bytes at `p`: the
/// value it points to, and where the value after the pointer starts.
fn decode_pointer(
    buf: &[u8],
    base: usize,
    ctrl: u8,
    p: usize,
    depth: usize,
) -> Result<(Value, usize), String> {
    let ss = usize::from((ctrl >> 3) & 3);
    let vvv = usize::from(ctrl & 7);
    let b = take(buf, p, ss + 1)?;
    let n = usize::try_from(be(b)).map_err(|_| bad("pointer"))?;
    let target = match ss {
        0 => (vvv << 8) | n,
        1 => ((vvv << 16) | n) + 2048,
        2 => ((vvv << 24) | n) + 526_336,
        _ => n,
    };
    let (v, _) = decode(buf, base, base + target, depth + 1)?;
    Ok((v, p + ss + 1))
}

/// The payload size from the control byte `ctrl` and any size bytes at
/// `p`, and where the payload starts.
fn payload_size(buf: &[u8], ctrl: u8, p: usize) -> Result<(usize, usize), String> {
    let size = usize::from(ctrl & 0x1F);
    if size < 29 {
        return Ok((size, p));
    }
    let extra = size - 28;
    let n = usize::try_from(be(take(buf, p, extra)?)).map_err(|_| bad("size"))?;
    let size = match extra {
        1 => 29 + n,
        2 => 285 + n,
        _ => 65_821 + n,
    };
    Ok((size, p + extra))
}

/// The `n`-byte unsigned integer at `p`.
fn uint(buf: &[u8], p: usize, n: usize) -> Result<u128, String> {
    if n > 16 {
        return Err(bad("integer too wide"));
    }
    Ok(be(take(buf, p, n)?))
}

fn decode_str(
    buf: &[u8],
    _: usize,
    p: usize,
    size: usize,
    _: usize,
) -> Result<(Value, usize), String> {
    let s = String::from_utf8_lossy(take(buf, p, size)?).into_owned();
    Ok((Value::Str(s), p + size))
}

fn decode_double(
    buf: &[u8],
    _: usize,
    p: usize,
    _: usize,
    _: usize,
) -> Result<(Value, usize), String> {
    let b: [u8; 8] = take(buf, p, 8)?.try_into().map_err(|_| bad("double"))?;
    Ok((Value::Double(f64::from_be_bytes(b)), p + 8))
}

fn decode_bytes(
    buf: &[u8],
    _: usize,
    p: usize,
    size: usize,
    _: usize,
) -> Result<(Value, usize), String> {
    Ok((Value::Bytes(take(buf, p, size)?.to_vec()), p + size))
}

fn decode_uint(
    buf: &[u8],
    _: usize,
    p: usize,
    size: usize,
    _: usize,
) -> Result<(Value, usize), String> {
    Ok((Value::Uint(uint(buf, p, size)?), p + size))
}

fn decode_int32(
    buf: &[u8],
    _: usize,
    p: usize,
    size: usize,
    _: usize,
) -> Result<(Value, usize), String> {
    let n = u32::try_from(uint(buf, p, size)?).map_err(|_| bad("int32"))?;
    Ok((Value::Int(i32::from_be_bytes(n.to_be_bytes())), p + size))
}

fn decode_map(
    buf: &[u8],
    base: usize,
    mut p: usize,
    size: usize,
    depth: usize,
) -> Result<(Value, usize), String> {
    let mut m = Vec::with_capacity(size.min(64));
    for _ in 0..size {
        let (k, next) = decode(buf, base, p, depth + 1)?;
        let Value::Str(k) = k else {
            return Err(bad("map key is not a string"));
        };
        let (v, next) = decode(buf, base, next, depth + 1)?;
        m.push((k, v));
        p = next;
    }
    Ok((Value::Map(m), p))
}

fn decode_array(
    buf: &[u8],
    base: usize,
    mut p: usize,
    size: usize,
    depth: usize,
) -> Result<(Value, usize), String> {
    let mut a = Vec::with_capacity(size.min(64));
    for _ in 0..size {
        let (v, next) = decode(buf, base, p, depth + 1)?;
        a.push(v);
        p = next;
    }
    Ok((Value::Array(a), p))
}

fn decode_bool(
    _: &[u8],
    _: usize,
    p: usize,
    size: usize,
    _: usize,
) -> Result<(Value, usize), String> {
    Ok((Value::Bool(size != 0), p))
}

fn decode_float(
    buf: &[u8],
    _: usize,
    p: usize,
    _: usize,
    _: usize,
) -> Result<(Value, usize), String> {
    let b: [u8; 4] = take(buf, p, 4)?.try_into().map_err(|_| bad("float"))?;
    Ok((Value::Float(f32::from_be_bytes(b)), p + 4))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn values_decode_with_pointers_and_long_sizes() {
        // 0: "en"; 3: a map {"a": pointer to 0, "b": 300 x's (size 285 + 15)}.
        let mut buf = vec![0x42, b'e', b'n'];
        buf.extend([0xE2, 0x41, b'a', 0x20, 0x00, 0x41, b'b', 0x5E, 0x00, 0x0F]);
        buf.extend(std::iter::repeat_n(b'x', 300));
        let (v, end) = decode(&buf, 0, 3, 0).unwrap();
        assert_eq!(end, buf.len());
        assert_eq!(
            v.get(&["a"]),
            Some(&Value::Str("en".into())),
            "pointer, size 0"
        );
        assert_eq!(
            v.get(&["b"]).and_then(Value::as_str).map(str::len),
            Some(300)
        );
        // A pointer of size 1 adds 2048: offset 2048 + 1 from 0x08 0x00 0x01.
        let mut far = vec![0u8; 2049];
        far.extend([0x42, b'o', b'k']);
        let at = far.len();
        far.extend([0x28, 0x00, 0x01]);
        assert_eq!(decode(&far, 0, at, 0).unwrap().0, Value::Str("ok".into()));
        // uint32, an extended uint64 and a boolean.
        assert_eq!(
            decode(&[0xC2, 0x01, 0x00], 0, 0, 0).unwrap().0,
            Value::Uint(256)
        );
        assert_eq!(
            decode(&[0x01, 0x02, 0x07], 0, 0, 0).unwrap().0,
            Value::Uint(7)
        );
        assert_eq!(decode(&[0x01, 0x07], 0, 0, 0).unwrap().0, Value::Bool(true));
    }

    #[test]
    fn truncated_input_is_an_error_not_a_panic() {
        assert!(decode(&[0x45, b'a'], 0, 0, 0).is_err());
        assert!(decode(&[0xE1, 0x41], 0, 0, 0).is_err());
        assert!(decode(&[], 0, 0, 0).is_err());
        assert!(Mmdb::from_bytes(b"no marker here".to_vec()).is_err());
        // A loop of pointers stops at the depth limit.
        assert!(decode(&[0x20, 0x00], 0, 0, 0).is_err());
    }

    fn value(buf: &[u8]) -> Result<Value, String> {
        decode(buf, 0, 0, 0).map(|(v, end)| {
            assert_eq!(end, buf.len(), "the whole value is read");
            v
        })
    }

    #[test]
    fn each_data_type_decodes() {
        // 3 double, 4 bytes, 5 uint16, 6 uint32: type in the top 3 bits.
        let mut double = vec![0x68];
        double.extend(1.5f64.to_be_bytes());
        assert_eq!(value(&double), Ok(Value::Double(1.5)));
        assert_eq!(value(&[0x83, 1, 2, 3]), Ok(Value::Bytes(vec![1, 2, 3])));
        assert_eq!(value(&[0xA2, 0x01, 0x00]), Ok(Value::Uint(256)));
        assert_eq!(value(&[0xC1, 0x07]), Ok(Value::Uint(7)));
        // Extended types: type 0, then the type less 7 in the next byte.
        // 8 int32, 9 uint64, 10 uint128, 11 array, 14 boolean, 15 float.
        assert_eq!(
            value(&[0x04, 0x01, 0xFF, 0xFF, 0xFF, 0xFE]),
            Ok(Value::Int(-2))
        );
        assert_eq!(value(&[0x01, 0x01, 0x05]), Ok(Value::Int(5)));
        assert_eq!(value(&[0x00, 0x02]), Ok(Value::Uint(0)));
        let mut u128 = vec![0x10, 0x03];
        u128.extend([0xFF; 16]);
        assert_eq!(value(&u128), Ok(Value::Uint(u128::MAX)));
        assert_eq!(
            value(&[0x02, 0x04, 0x41, b'a', 0xA1, 0x02]),
            Ok(Value::Array(vec![Value::Str("a".into()), Value::Uint(2)]))
        );
        assert_eq!(value(&[0x00, 0x07]), Ok(Value::Bool(false)));
        let mut float = vec![0x04, 0x08];
        float.extend(0.25f32.to_be_bytes());
        assert_eq!(value(&float), Ok(Value::Float(0.25)));
        // An empty map and a string of a size in three extra bytes
        // (65 821 + 1).
        assert_eq!(value(&[0xE0]), Ok(Value::Map(vec![])));
        let mut long = vec![0x5F, 0x00, 0x00, 0x01];
        long.extend(std::iter::repeat_n(b'z', 65_822));
        assert_eq!(value(&long).unwrap().as_str().map(str::len), Some(65_822));
    }

    #[test]
    fn pointers_of_each_size_resolve_from_the_base() {
        // The data section starts at 4; "ok" at its offset 526 336 + 2.
        let base = 4;
        let mut buf = vec![0xFF; base];
        buf.resize(base + 526_338, 0);
        buf.extend([0x42, b'o', b'k']);
        let ok = Value::Str("ok".into());
        // Size 2: 526 336 + 0x000002.
        let at = buf.len();
        buf.extend([0x30, 0x00, 0x00, 0x02]);
        assert_eq!(decode(&buf, base, at, 0), Ok((ok.clone(), at + 4)));
        // Size 3: the 32-bit offset as is.
        let at = buf.len();
        buf.extend([0x38, 0x00, 0x08, 0x08, 0x02]);
        assert_eq!(decode(&buf, base, at, 0), Ok((ok, at + 5)));
    }

    #[test]
    fn malformed_values_are_errors() {
        let err = |buf: &[u8]| value(buf).unwrap_err();
        let unknown = bad("unknown type");
        assert_eq!(err(&[0x00, 0x05]), unknown, "12 data cache container");
        assert_eq!(err(&[0x00, 0x06]), unknown, "13 end marker");
        assert_eq!(err(&[0x00, 0x09]), unknown, "16");
        assert_eq!(err(&[0x00, 0xF9]), bad("type"), "past 255");
        let mut wide = vec![0xD1];
        wide.extend([0; 17]);
        assert_eq!(err(&wide), bad("integer too wide"));
        assert_eq!(err(&[0x05, 0x01, 1, 0, 0, 0, 0]), bad("int32"));
        assert_eq!(
            err(&[0xE1, 0xC1, 0x01, 0x41, b'v']),
            bad("map key is not a string")
        );
        assert_eq!(err(&[0x68, 0, 0]), bad("value past the end"), "double");
        assert_eq!(err(&[0x04, 0x08, 0]), bad("value past the end"), "float");
        assert_eq!(err(&[0x5E, 0x00]), bad("value past the end"), "size");
        assert_eq!(err(&[0x30, 0x00]), bad("value past the end"), "pointer");
    }

    const LEFT_NONE: usize = 1;
    const RIGHT_DATA: usize = 1 + 16;

    /// A database of one node, records (`left`, `right`) of `record_size`
    /// bits, the string "hit" first in the data section, and the metadata
    /// `meta` (uint32 values) with `database_type` "Test".
    fn one_node(record_size: usize, left: usize, right: usize, meta: &[(&str, u32)]) -> Vec<u8> {
        let be = |n: usize, len: usize| n.to_be_bytes()[8 - len..].to_vec();
        let mut buf = match record_size {
            24 => [be(left, 3), be(right, 3)].concat(),
            28 => {
                let mid = u8::try_from(((left >> 24) << 4) | (right >> 24)).unwrap();
                [be(left, 3), vec![mid], be(right, 3)].concat()
            }
            _ => [be(left, 4), be(right, 4)].concat(),
        };
        buf.extend([0; 16]);
        buf.extend([0x43, b'h', b'i', b't']);
        buf.extend(MARKER);
        buf.push(0xE0 | u8::try_from(meta.len() + 1).unwrap());
        let mut key = |k: &str| {
            buf.push(0x40 | u8::try_from(k.len()).unwrap());
            buf.extend(k.as_bytes());
        };
        key("database_type");
        buf.extend([0x44, b'T', b'e', b's', b't']);
        for (k, n) in meta {
            buf.push(0x40 | u8::try_from(k.len()).unwrap());
            buf.extend(k.as_bytes());
            buf.push(0xC4);
            buf.extend(n.to_be_bytes());
        }
        buf
    }

    fn meta(record_size: u32, ip_version: u32) -> Vec<(&'static str, u32)> {
        vec![
            ("binary_format_major_version", 2),
            ("node_count", 1),
            ("record_size", record_size),
            ("ip_version", ip_version),
            ("build_epoch", 1_792_454_400),
        ]
    }

    #[test]
    fn ipv4_trees_of_each_record_size_look_up() {
        let hit = Some(Value::Str("hit".into()));
        for size in [24, 28, 32] {
            let m = meta(u32::try_from(size).unwrap(), 4);
            let db = Mmdb::from_bytes(one_node(size, LEFT_NONE, RIGHT_DATA, &m)).unwrap();
            assert_eq!(
                (db.database_type.as_str(), db.build_epoch),
                ("Test", 1_792_454_400)
            );
            assert_eq!(
                db.lookup("128.0.0.1".parse().unwrap()),
                Ok(hit.clone()),
                "{size}"
            );
            assert_eq!(db.lookup("10.0.0.1".parse().unwrap()), Ok(None), "{size}");
            assert_eq!(
                db.lookup("::1".parse().unwrap()),
                Ok(None),
                "no IPv6 in an IPv4 tree"
            );
        }
    }

    #[test]
    fn ipv6_trees_look_up_both_families() {
        let db = Mmdb::from_bytes(one_node(24, LEFT_NONE, RIGHT_DATA, &meta(24, 6))).unwrap();
        assert_eq!(
            db.lookup("8000::1".parse().unwrap()),
            Ok(Some(Value::Str("hit".into())))
        );
        assert_eq!(db.lookup("::1".parse().unwrap()), Ok(None));
        assert_eq!(
            db.lookup("10.0.0.1".parse().unwrap()),
            Ok(None),
            "::/96 has no data"
        );
    }

    #[test]
    fn a_tree_that_ends_in_a_node_is_an_error() {
        let db = Mmdb::from_bytes(one_node(24, 0, RIGHT_DATA, &meta(24, 4))).unwrap();
        assert_eq!(
            db.lookup("0.0.0.0".parse().unwrap()),
            Err(bad("search tree ends in a node"))
        );
    }

    #[test]
    fn unusable_metadata_is_an_error() {
        let with = |k: &str, n: u32| {
            let m: Vec<_> = meta(24, 4)
                .into_iter()
                .map(|(mk, v)| (mk, if mk == k { n } else { v }))
                .collect();
            Mmdb::from_bytes(one_node(24, LEFT_NONE, RIGHT_DATA, &m)).err()
        };
        assert_eq!(
            with("binary_format_major_version", 3),
            Some(bad("not format 2"))
        );
        assert_eq!(with("record_size", 20), Some(bad("record size")));
        assert_eq!(
            with("node_count", 1000),
            Some(bad("search tree past the end"))
        );
        let no_epoch: Vec<_> = meta(24, 4)
            .into_iter()
            .filter(|(k, _)| *k != "build_epoch")
            .collect();
        assert_eq!(
            Mmdb::from_bytes(one_node(24, LEFT_NONE, RIGHT_DATA, &no_epoch)).err(),
            Some(bad("metadata has no build_epoch"))
        );
    }

    #[test]
    fn open_reads_a_file_or_says_why_not() {
        let path = std::env::temp_dir().join(format!("frank-mmdb-{}.mmdb", std::process::id()));
        std::fs::write(&path, one_node(24, LEFT_NONE, RIGHT_DATA, &meta(24, 4))).unwrap();
        assert_eq!(
            Mmdb::open(&path).map(|db| db.database_type),
            Ok("Test".into())
        );
        std::fs::remove_file(&path).unwrap();
        assert!(Mmdb::open(&path).is_err());
    }

    #[test]
    fn accessors_of_another_type_are_none() {
        let n = Value::Uint(u128::from(u64::MAX) + 1);
        assert_eq!((n.get(&["a"]), n.as_str(), n.as_u64()), (None, None, None));
        assert_eq!(Value::Str("a".into()).as_u64(), None);
    }
}

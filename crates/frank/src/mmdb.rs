//! A reader for MaxMind DB files, format 2.0 (#191), enough for FRANK's
//! GeoLite2 lookups: the search tree (24, 28 or 32-bit records, IPv4 under
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
        let from = buf.len().saturating_sub(META_MAX);
        let at = buf[from..]
            .windows(MARKER.len())
            .rposition(|w| w == MARKER)
            .map(|i| from + i + MARKER.len())
            .ok_or_else(|| bad("no metadata"))?;
        let (meta, _) = decode(&buf, at, at, 0)?;
        let num = |k: &str| {
            meta.get(&[k])
                .and_then(Value::as_u64)
                .ok_or_else(|| bad(&format!("metadata has no {k}")))
        };
        if num("binary_format_major_version")? != 2 {
            return Err(bad("not format 2"));
        }
        let node_count = usize::try_from(num("node_count")?).map_err(|_| bad("node_count"))?;
        let record_size = usize::try_from(num("record_size")?).map_err(|_| bad("record_size"))?;
        if !matches!(record_size, 24 | 28 | 32) {
            return Err(bad("record size"));
        }
        let tree_size = node_count
            .checked_mul(record_size / 4)
            .filter(|t| t + 16 <= at)
            .ok_or_else(|| bad("search tree past the end"))?;
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
            let mut node = 0;
            for _ in 0..96 {
                if node >= db.node_count {
                    break;
                }
                node = db.record(node, 0)?;
            }
            db.ipv4_start = node;
        }
        Ok(db)
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

/// The value at `at`, and where the next one starts. Pointers are offsets
/// from `base`, the start of the data section.
fn decode(buf: &[u8], base: usize, at: usize, depth: usize) -> Result<(Value, usize), String> {
    if depth > MAX_DEPTH {
        return Err(bad("nested too deeply"));
    }
    let byte = |i: usize| buf.get(i).copied().ok_or_else(|| bad("value past the end"));
    let take = |from: usize, n: usize| {
        buf.get(from..from + n)
            .ok_or_else(|| bad("value past the end"))
    };
    let be = |s: &[u8]| s.iter().fold(0u128, |a, x| (a << 8) | u128::from(*x));
    let ctrl = byte(at)?;
    let mut p = at + 1;
    let mut kind = ctrl >> 5;
    if kind == 1 {
        let ss = usize::from((ctrl >> 3) & 3);
        let vvv = usize::from(ctrl & 7);
        let b = take(p, ss + 1)?;
        let n = usize::try_from(be(b)).map_err(|_| bad("pointer"))?;
        let target = match ss {
            0 => (vvv << 8) | n,
            1 => ((vvv << 16) | n) + 2048,
            2 => ((vvv << 24) | n) + 526_336,
            _ => n,
        };
        let (v, _) = decode(buf, base, base + target, depth + 1)?;
        return Ok((v, p + ss + 1));
    }
    if kind == 0 {
        kind = byte(p)?.checked_add(7).ok_or_else(|| bad("type"))?;
        p += 1;
    }
    let mut size = usize::from(ctrl & 0x1F);
    if size >= 29 {
        let extra = size - 28;
        let n = usize::try_from(be(take(p, extra)?)).map_err(|_| bad("size"))?;
        size = match extra {
            1 => 29 + n,
            2 => 285 + n,
            _ => 65_821 + n,
        };
        p += extra;
    }
    let uint = |n: usize| -> Result<u128, String> {
        if n > 16 {
            return Err(bad("integer too wide"));
        }
        Ok(be(take(p, n)?))
    };
    Ok(match kind {
        2 => (
            Value::Str(String::from_utf8_lossy(take(p, size)?).into_owned()),
            p + size,
        ),
        3 => {
            let b: [u8; 8] = take(p, 8)?.try_into().map_err(|_| bad("double"))?;
            (Value::Double(f64::from_be_bytes(b)), p + 8)
        }
        4 => (Value::Bytes(take(p, size)?.to_vec()), p + size),
        5 | 6 | 9 | 10 => (Value::Uint(uint(size)?), p + size),
        8 => {
            let n = u32::try_from(uint(size)?).map_err(|_| bad("int32"))?;
            (Value::Int(i32::from_be_bytes(n.to_be_bytes())), p + size)
        }
        7 => {
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
            (Value::Map(m), p)
        }
        11 => {
            let mut a = Vec::with_capacity(size.min(64));
            for _ in 0..size {
                let (v, next) = decode(buf, base, p, depth + 1)?;
                a.push(v);
                p = next;
            }
            (Value::Array(a), p)
        }
        14 => (Value::Bool(size != 0), p),
        15 => {
            let b: [u8; 4] = take(p, 4)?.try_into().map_err(|_| bad("float"))?;
            (Value::Float(f32::from_be_bytes(b)), p + 4)
        }
        _ => return Err(bad("unknown type")),
    })
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
}

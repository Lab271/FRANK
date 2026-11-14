//! Indicators of compromise: types, normalisation, lookup keys.

use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};

use serde::{Deserialize, Serialize};

use crate::model::Error;

/// Longest IoC value accepted (a long URL fits; a log line does not).
pub const MAX_VALUE_LEN: usize = 2048;

/// The nine observable types of Phase 2 (spec 002).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum IocType {
    Ipv4,
    Ipv6,
    Domain,
    Url,
    Email,
    Certificate,
    FileHash,
    RegistryKey,
    Mutex,
}

impl IocType {
    pub const ALL: [IocType; 9] = [
        IocType::Ipv4,
        IocType::Ipv6,
        IocType::Domain,
        IocType::Url,
        IocType::Email,
        IocType::Certificate,
        IocType::FileHash,
        IocType::RegistryKey,
        IocType::Mutex,
    ];

    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            IocType::Ipv4 => "ipv4",
            IocType::Ipv6 => "ipv6",
            IocType::Domain => "domain",
            IocType::Url => "url",
            IocType::Email => "email",
            IocType::Certificate => "certificate",
            IocType::FileHash => "file_hash",
            IocType::RegistryKey => "registry_key",
            IocType::Mutex => "mutex",
        }
    }

    /// The type named `s`: our names plus the STIX object names Phase 2
    /// submissions use (`ipv4-addr`, `domain-name`, ...). Case-insensitive.
    #[must_use]
    pub fn parse(s: &str) -> Option<IocType> {
        Some(match s.trim().to_ascii_lowercase().as_str() {
            "ipv4" | "ipv4-addr" => IocType::Ipv4,
            "ipv6" | "ipv6-addr" => IocType::Ipv6,
            "domain" | "domain-name" => IocType::Domain,
            "url" => IocType::Url,
            "email" | "email-addr" => IocType::Email,
            "certificate" | "x509-certificate" => IocType::Certificate,
            "file_hash" | "hash" | "md5" | "sha1" | "sha256" => IocType::FileHash,
            "registry_key" | "windows-registry-key" => IocType::RegistryKey,
            "mutex" | "mutex-name" => IocType::Mutex,
            _ => return None,
        })
    }
}

impl std::fmt::Display for IocType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// One normalised indicator.
#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize)]
pub struct Ioc {
    #[serde(rename = "type")]
    pub ioc_type: IocType,
    pub value: String,
}

impl Ioc {
    /// Normalises `value` for `ioc_type` (spec 002 requirement 4): trimmed,
    /// lower case except URLs, IP addresses in canonical form, hashes hex.
    ///
    /// # Errors
    ///
    /// [`Error::Invalid`] for an empty, overlong or malformed value.
    pub fn new(ioc_type: IocType, value: &str) -> Result<Ioc, Error> {
        let v = value.trim();
        let bad = |why: &str| Error::Invalid(format!("{ioc_type} {v:?}: {why}"));
        if v.is_empty() {
            return Err(bad("empty"));
        }
        if v.len() > MAX_VALUE_LEN {
            return Err(bad("too long"));
        }
        if v.chars().any(char::is_control) {
            return Err(bad("control character"));
        }
        let value = match ioc_type {
            IocType::Url => v.to_string(),
            IocType::Ipv4 => v
                .parse::<Ipv4Addr>()
                .map_err(|_| bad("not an IPv4 address"))?
                .to_string(),
            IocType::Ipv6 => v
                .parse::<Ipv6Addr>()
                .map_err(|_| bad("not an IPv6 address"))?
                .to_string(),
            IocType::FileHash => {
                let h = v.to_ascii_lowercase();
                if !matches!(h.len(), 32 | 40 | 64 | 128)
                    || !h.bytes().all(|b| b.is_ascii_hexdigit())
                {
                    return Err(bad("not an MD5, SHA-1, SHA-256 or SHA-512 hex digest"));
                }
                h
            }
            _ => v.to_lowercase(),
        };
        Ok(Ioc { ioc_type, value })
    }

    /// The lookup key `type:value`.
    #[must_use]
    pub fn key(&self) -> String {
        format!("{}:{}", self.ioc_type, self.value)
    }

    /// An IP address as 32 hex digits (IPv4 mapped into IPv6), so ranges
    /// compare as text: `BETWEEN ip_hex(lo) AND ip_hex(hi)`.
    #[must_use]
    pub fn ip_hex(&self) -> Option<String> {
        match self.ioc_type {
            IocType::Ipv4 | IocType::Ipv6 => self.value.parse::<IpAddr>().ok().map(ip_hex),
            _ => None,
        }
    }
}

/// `ip` as 32 hex digits, IPv4 mapped into IPv6.
#[must_use]
pub fn ip_hex(ip: IpAddr) -> String {
    let v6 = match ip {
        IpAddr::V4(v4) => v4.to_ipv6_mapped(),
        IpAddr::V6(v6) => v6,
    };
    format!("{:032x}", u128::from(v6))
}

#[cfg(test)]
#[allow(non_snake_case)] // mcdc__<id>__v<N>_<what> (ADR-025)
mod tests {
    use super::*;

    #[test]
    fn normalises_per_type() {
        let n = |t, v| Ioc::new(t, v).unwrap().value;
        assert_eq!(n(IocType::Domain, "  EXAMPLE.com "), "example.com");
        assert_eq!(
            n(IocType::Url, " https://Evil.com/Path "),
            "https://Evil.com/Path"
        );
        assert_eq!(n(IocType::Ipv6, "2001:DB8:0:0::1"), "2001:db8::1");
        assert_eq!(
            n(IocType::FileHash, "A1B2C3D4E5F6789012345678901234AB"),
            "a1b2c3d4e5f6789012345678901234ab"
        );
        assert_eq!(
            n(IocType::Mutex, "Global\\MalwareMutex"),
            "global\\malwaremutex"
        );
    }

    #[test]
    fn refuses_malformed_values() {
        assert!(Ioc::new(IocType::Ipv4, "999.1.1.1").is_err());
        assert!(Ioc::new(IocType::FileHash, "xyz").is_err());
        assert!(Ioc::new(IocType::Domain, "  ").is_err());
        assert!(Ioc::new(IocType::Domain, "a\nb").is_err());
        assert!(Ioc::new(IocType::Url, &"x".repeat(MAX_VALUE_LEN + 1)).is_err());
    }

    #[test]
    fn ip_hex_orders_addresses() {
        let h = |v| Ioc::new(IocType::Ipv4, v).unwrap().ip_hex().unwrap();
        assert_eq!(h("10.0.0.1"), "00000000000000000000ffff0a000001");
        assert!(h("10.0.0.2") < h("10.0.1.0"));
        assert_eq!(Ioc::new(IocType::Domain, "a.nl").unwrap().ip_hex(), None);
    }

    #[test]
    fn parses_stix_names() {
        assert_eq!(IocType::parse("domain-name"), Some(IocType::Domain));
        assert_eq!(IocType::parse("SHA256"), Some(IocType::FileHash));
        assert_eq!(IocType::parse("executable"), None);
        for t in IocType::ALL {
            assert_eq!(IocType::parse(t.as_str()), Some(t));
        }
    }

    // new, file hash: `!matches!(h.len(), 32 | 40 | 64 | 128) || !all hex`
    #[test]
    fn mcdc__observable_new_93880de9__v1_hex_digest_is_kept() {
        let h = "a1b2c3d4e5f6789012345678901234ab";
        assert_eq!(Ioc::new(IocType::FileHash, h).unwrap().value, h);
    }

    #[test]
    fn mcdc__observable_new_93880de9__v2_wrong_length_is_refused() {
        assert!(Ioc::new(IocType::FileHash, "abc").is_err());
    }

    #[test]
    fn mcdc__observable_new_93880de9__v3_non_hex_is_refused() {
        assert!(Ioc::new(IocType::FileHash, "g1b2c3d4e5f6789012345678901234ab").is_err());
    }
}

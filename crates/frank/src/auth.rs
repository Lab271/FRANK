//! Bearer tokens mapped to access tiers.
//!
//! The tokens file holds one line per token, `<sha256-hex> <tier> <label>`;
//! the server never stores a token itself. `frank token` appends a line and
//! prints the token once. No token means the public tier.

use std::collections::HashMap;
use std::io::Write;
use std::path::Path;

use frank_core::Tier;
use sha2::{Digest, Sha256};

/// Who a request is: a tier, and a label for the logs.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Caller {
    pub tier: Tier,
    pub label: String,
}

impl Caller {
    #[must_use]
    pub fn public() -> Caller {
        Caller {
            tier: Tier::Public,
            label: "public".into(),
        }
    }
}

#[derive(Debug, Default, Clone)]
pub struct Tokens {
    by_hash: HashMap<String, Caller>,
}

impl Tokens {
    /// Reads a tokens file; a missing file is no tokens (public only).
    pub fn load(path: &Path) -> Result<Tokens, String> {
        let text = match std::fs::read_to_string(path) {
            Ok(t) => t,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Tokens::default()),
            Err(e) => return Err(format!("{}: {e}", path.display())),
        };
        Tokens::parse(&text).map_err(|e| format!("{}: {e}", path.display()))
    }

    pub fn parse(text: &str) -> Result<Tokens, String> {
        let mut by_hash = HashMap::new();
        for (n, line) in text.lines().enumerate() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }
            let mut parts = line.splitn(3, char::is_whitespace);
            let (Some(hash), Some(tier)) = (parts.next(), parts.next()) else {
                return Err(format!(
                    "line {}: expected `<sha256> <tier> [label]`",
                    n + 1
                ));
            };
            if hash.len() != 64 || !hash.bytes().all(|b| b.is_ascii_hexdigit()) {
                return Err(format!("line {}: not a SHA-256 hex digest", n + 1));
            }
            let tier = Tier::parse(tier)
                .ok_or_else(|| format!("line {}: unknown tier {tier:?}", n + 1))?;
            let label = parts.next().unwrap_or("").trim().to_string();
            by_hash.insert(hash.to_ascii_lowercase(), Caller { tier, label });
        }
        Ok(Tokens { by_hash })
    }

    /// The caller an `Authorization` header value names: `None` for an
    /// unknown token, the public tier for no header.
    #[must_use]
    pub fn caller(&self, authorization: Option<&str>) -> Option<Caller> {
        let Some(value) = authorization else {
            return Some(Caller::public());
        };
        let token = value.strip_prefix("Bearer ")?.trim();
        self.by_hash.get(&hash(token)).cloned()
    }

    #[must_use]
    pub fn len(&self) -> usize {
        self.by_hash.len()
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.by_hash.is_empty()
    }
}

#[must_use]
pub fn hash(token: &str) -> String {
    hex(&Sha256::digest(token.as_bytes()))
}

/// Creates a token for `tier`, appends its hash to `path` and returns it.
pub fn add_token(path: &Path, tier: Tier, label: &str) -> Result<String, String> {
    if label.chars().any(|c| c.is_control()) {
        return Err("label has a control character".into());
    }
    let token = format!("frank_{}", hex(&random::<24>()?));
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|e| format!("{}: {e}", path.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = file.set_permissions(std::fs::Permissions::from_mode(0o600));
    }
    writeln!(file, "{} {tier} {label}", hash(&token)).map_err(|e| e.to_string())?;
    Ok(token)
}

pub fn random<const N: usize>() -> Result<[u8; N], String> {
    let mut b = [0u8; N];
    getrandom::fill(&mut b).map_err(|e| e.to_string())?;
    Ok(b)
}

#[must_use]
pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tokens_resolve_to_their_tier() {
        let tokens =
            Tokens::parse(&format!("# comment\n{} partner sbp-mdr\n", hash("secret"))).unwrap();
        assert_eq!(
            tokens.caller(Some("Bearer secret")).unwrap().tier,
            Tier::Partner
        );
        assert_eq!(
            tokens.caller(Some("Bearer secret")).unwrap().label,
            "sbp-mdr"
        );
        assert_eq!(tokens.caller(None).unwrap().tier, Tier::Public);
        assert_eq!(tokens.caller(Some("Bearer wrong")), None);
        assert_eq!(tokens.caller(Some("secret")), None, "not a bearer token");
    }

    #[test]
    fn refuses_a_malformed_file() {
        assert!(Tokens::parse("abc partner").is_err());
        assert!(Tokens::parse(&format!("{} admin", hash("x"))).is_err());
    }

    #[test]
    fn added_tokens_load_back() {
        let path = std::env::temp_dir().join(format!("frank-tokens-{}", std::process::id()));
        let token = add_token(&path, Tier::Contributor, "test").unwrap();
        let tokens = Tokens::load(&path).unwrap();
        std::fs::remove_file(&path).ok();
        assert_eq!(
            tokens
                .caller(Some(&format!("Bearer {token}")))
                .unwrap()
                .tier,
            Tier::Contributor
        );
        assert!(!std::fs::read_to_string(&path)
            .unwrap_or_default()
            .contains(&token));
    }
}

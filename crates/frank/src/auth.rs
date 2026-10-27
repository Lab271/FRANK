//! Who a request is (#159): a bearer token names a user, the user belongs
//! to an organisation (the participant), and the organisation's status is
//! the caller's tier. Tokens live in `participants.db`
//! ([`crate::store::participants`]); the server never stores a token
//! itself, only its SHA-256. No token means the public tier.

use frank_core::Tier;
use serde::Serialize;
use sha2::{Digest, Sha256};

/// What a user may manage (#175, ADR-017), apart from what its
/// organisation's status lets it see. Only people hold a role.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    /// Manages the users and tokens of its own organisation
    /// (contributor, partner or core).
    Admin,
    /// Manages every organisation (core only).
    Superadmin,
}

impl Role {
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Role::Admin => "admin",
            Role::Superadmin => "superadmin",
        }
    }

    /// `admin` or `superadmin`; `None` for anything else.
    #[must_use]
    pub fn parse(s: &str) -> Option<Role> {
        match s.trim().to_ascii_lowercase().as_str() {
            "admin" => Some(Role::Admin),
            "superadmin" => Some(Role::Superadmin),
            _ => None,
        }
    }
}

impl std::fmt::Display for Role {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Who a request is.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Caller {
    /// The organisation's status.
    pub tier: Tier,
    /// The organisation's opaque id (`identity--{uuid4}`): what sightings
    /// are stored under. Empty for the public tier.
    pub participant: String,
    /// The organisation's name, for logs and `whoami`.
    pub organisation: String,
    /// The user the token belongs to.
    pub user: String,
    /// The user's role, if any.
    pub role: Option<Role>,
}

impl Caller {
    #[must_use]
    pub fn public() -> Caller {
        Caller {
            tier: Tier::Public,
            participant: String::new(),
            organisation: String::new(),
            user: String::new(),
            role: None,
        }
    }

    /// `user@organisation`, or `public`.
    #[must_use]
    pub fn label(&self) -> String {
        if self.user.is_empty() {
            "public".into()
        } else {
            format!("{}@{}", self.user, self.organisation)
        }
    }
}

#[must_use]
pub fn hash(token: &str) -> String {
    hex(&Sha256::digest(token.as_bytes()))
}

pub fn random<const N: usize>() -> Result<[u8; N], String> {
    let mut b = [0u8; N];
    getrandom::fill(&mut b).map_err(|e| e.to_string())?;
    Ok(b)
}

/// A random (version 4) UUID, lower case.
pub fn uuid4() -> Result<String, String> {
    let mut b = random::<16>()?;
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    Ok(uuid_text(&b))
}

/// 16 bytes in the 8-4-4-4-12 form.
#[must_use]
pub fn uuid_text(b: &[u8; 16]) -> String {
    let h = hex(b);
    format!(
        "{}-{}-{}-{}-{}",
        &h[..8],
        &h[8..12],
        &h[12..16],
        &h[16..20],
        &h[20..]
    )
}

#[must_use]
pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn uuid4_has_version_and_variant() {
        let u = uuid4().unwrap();
        assert_eq!(u.len(), 36);
        assert_eq!(&u[14..15], "4");
        assert!("89ab".contains(&u[19..20]), "{u}");
        assert_ne!(u, uuid4().unwrap());
    }

    #[test]
    fn labels() {
        assert_eq!(Caller::public().label(), "public");
        let c = Caller {
            tier: Tier::Partner,
            participant: "identity--x".into(),
            organisation: "lab".into(),
            user: "bob".into(),
            role: None,
        };
        assert_eq!(c.label(), "bob@lab");
    }
}

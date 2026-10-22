//! Traffic Light Protocol (TLP 2.0): the submitter's disclosure control,
//! independent of the access tier (HLD §TLP, spec 001 requirement 5). Each
//! level has a lowest tier allowed to see it; TLP:RED is never shared.

use serde::Serialize;

use crate::submission::Error;
use crate::tier::Tier;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
pub enum Tlp {
    #[serde(rename = "clear")]
    Clear,
    #[serde(rename = "green")]
    Green,
    #[serde(rename = "amber")]
    Amber,
    #[serde(rename = "amber+strict")]
    AmberStrict,
    #[serde(rename = "red")]
    Red,
}

impl Tlp {
    /// The levels FRANK stores; RED is refused at submission.
    pub const SHARED: [Tlp; 4] = [Tlp::Clear, Tlp::Green, Tlp::Amber, Tlp::AmberStrict];

    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Tlp::Clear => "clear",
            Tlp::Green => "green",
            Tlp::Amber => "amber",
            Tlp::AmberStrict => "amber+strict",
            Tlp::Red => "red",
        }
    }

    /// The level named `s`: `TLP:AMBER`, `amber`, `AMBER+STRICT`, and the
    /// `AMBER+` and `WHITE` (TLP 1.0) spellings. Case-insensitive.
    ///
    /// # Errors
    ///
    /// [`Error::Invalid`] for an unknown level.
    pub fn parse(s: &str) -> Result<Tlp, Error> {
        let t = s.trim().to_ascii_lowercase();
        let t = t.strip_prefix("tlp:").unwrap_or(&t);
        Ok(match t {
            "clear" | "white" => Tlp::Clear,
            "green" => Tlp::Green,
            "amber" => Tlp::Amber,
            "amber+strict" | "amber+" => Tlp::AmberStrict,
            "red" => Tlp::Red,
            _ => return Err(Error::Invalid(format!("unknown TLP level {s:?}"))),
        })
    }

    /// The lowest tier that may see this level (HLD categories, §TLP).
    #[must_use]
    pub fn min_tier(self) -> Tier {
        match self {
            Tlp::Clear => Tier::Public,
            Tlp::Green => Tier::Observer,
            Tlp::Amber => Tier::Contributor,
            Tlp::AmberStrict => Tier::Partner,
            Tlp::Red => Tier::Core,
        }
    }

    /// The stored levels `tier` may see.
    #[must_use]
    pub fn visible_to(tier: Tier) -> Vec<Tlp> {
        Tlp::SHARED
            .into_iter()
            .filter(|t| t.min_tier() <= tier)
            .collect()
    }
}

impl std::fmt::Display for Tlp {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_tlp_spellings() {
        assert_eq!(Tlp::parse("TLP:AMBER").unwrap(), Tlp::Amber);
        assert_eq!(Tlp::parse("amber+strict").unwrap(), Tlp::AmberStrict);
        assert_eq!(Tlp::parse("TLP:AMBER+").unwrap(), Tlp::AmberStrict);
        assert_eq!(Tlp::parse(" white ").unwrap(), Tlp::Clear);
        assert!(Tlp::parse("purple").is_err());
        for t in Tlp::SHARED {
            assert_eq!(Tlp::parse(t.as_str()).unwrap(), t);
        }
    }

    #[test]
    fn each_tier_sees_its_levels() {
        assert_eq!(Tlp::visible_to(Tier::Public), [Tlp::Clear]);
        assert_eq!(Tlp::visible_to(Tier::Observer), [Tlp::Clear, Tlp::Green]);
        assert_eq!(
            Tlp::visible_to(Tier::Contributor),
            [Tlp::Clear, Tlp::Green, Tlp::Amber]
        );
        assert_eq!(Tlp::visible_to(Tier::Partner), Tlp::SHARED);
        assert_eq!(
            Tlp::visible_to(Tier::Core),
            Tlp::SHARED,
            "RED is never stored"
        );
    }
}

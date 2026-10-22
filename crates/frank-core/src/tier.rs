//! Access tiers (ADR-002): each one sees more than the one below it.

use serde::Serialize;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Tier {
    /// No token: platform totals only.
    Public,
    /// Aggregates by type, sector and severity, small cells suppressed.
    Observer,
    /// May submit; sees rule-level statistics and IoC lookups.
    Contributor,
    /// May download the sighting files and analyse them locally.
    Partner,
    /// Platform operators.
    Core,
}

impl Tier {
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Tier::Public => "public",
            Tier::Observer => "observer",
            Tier::Contributor => "contributor",
            Tier::Partner => "partner",
            Tier::Core => "core",
        }
    }

    /// The tier named `s` (Phase 2 also wrote `core_member`).
    #[must_use]
    pub fn parse(s: &str) -> Option<Tier> {
        Some(match s.trim().to_ascii_lowercase().as_str() {
            "public" => Tier::Public,
            "observer" => Tier::Observer,
            "contributor" => Tier::Contributor,
            "partner" => Tier::Partner,
            "core" | "core_member" => Tier::Core,
            _ => return None,
        })
    }
}

impl std::fmt::Display for Tier {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tiers_are_ordered() {
        assert!(Tier::Public < Tier::Observer && Tier::Partner < Tier::Core);
        assert_eq!(Tier::parse("CORE_MEMBER"), Some(Tier::Core));
        assert_eq!(Tier::parse("admin"), None);
    }
}

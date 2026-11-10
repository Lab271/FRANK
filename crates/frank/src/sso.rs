//! Sign in with OpenID Connect (#241, ADR-020): the settings, off unless
//! all of them are given.
//!
//! The one secret, the client secret, is read from a file and is never
//! printed: [`Secret`]'s `Debug` and `Display` hide it.

use std::path::PathBuf;

/// The settings as `frank serve` receives them, each optional.
#[derive(Debug, Default, Clone)]
pub struct Settings {
    pub issuer: Option<String>,
    pub client_id: Option<String>,
    pub client_secret_file: Option<PathBuf>,
    pub redirect_url: Option<String>,
    pub organisation: Option<String>,
}

/// A value that is never printed.
#[derive(Clone, PartialEq, Eq)]
pub struct Secret(String);

impl Secret {
    #[must_use]
    pub fn new(value: impl Into<String>) -> Secret {
        Secret(value.into())
    }

    #[must_use]
    pub fn expose(&self) -> &str {
        &self.0
    }
}

impl std::fmt::Debug for Secret {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("Secret([redacted])")
    }
}

impl std::fmt::Display for Secret {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("[redacted]")
    }
}

/// Complete SSO settings.
#[derive(Debug, Clone)]
pub struct Config {
    /// The issuer, without a trailing `/`: `iss` must equal it.
    pub issuer: String,
    pub client_id: String,
    pub client_secret: Secret,
    /// Where the identity provider sends the browser back to:
    /// `…/v1/sso/callback` on FRANK's public address.
    pub redirect_url: String,
    /// The organisation (name or id) new users are created in.
    pub organisation: String,
    /// `scheme://host[:port]` of the redirect URL: the origin a
    /// cookie-authenticated write must come from.
    pub origin: String,
}

impl Config {
    /// `None` when no setting is given; an error naming what is missing
    /// when only some are, or when one is invalid. Never names the secret's
    /// value.
    pub fn from_settings(s: Settings) -> Result<Option<Config>, String> {
        let given = [
            ("FRANK_SSO_ISSUER", s.issuer.is_some()),
            ("FRANK_SSO_CLIENT_ID", s.client_id.is_some()),
            (
                "FRANK_SSO_CLIENT_SECRET_FILE",
                s.client_secret_file.is_some(),
            ),
            ("FRANK_SSO_REDIRECT_URL", s.redirect_url.is_some()),
            ("FRANK_SSO_ORGANISATION", s.organisation.is_some()),
        ];
        if given.iter().all(|(_, g)| !g) {
            return Ok(None);
        }
        let missing: Vec<&str> = given.iter().filter(|(_, g)| !g).map(|(n, _)| *n).collect();
        if !missing.is_empty() {
            return Err(format!(
                "SSO is partly configured: set {} too, or none of the FRANK_SSO_ settings",
                missing.join(", ")
            ));
        }
        let (
            Some(issuer),
            Some(client_id),
            Some(secret_file),
            Some(redirect_url),
            Some(organisation),
        ) = (
            s.issuer,
            s.client_id,
            s.client_secret_file,
            s.redirect_url,
            s.organisation,
        )
        else {
            unreachable!("checked above");
        };
        let issuer = issuer.trim().trim_end_matches('/').to_string();
        Url::parse(&issuer)
            .and_then(Url::secure)
            .map_err(|e| format!("FRANK_SSO_ISSUER: {e}"))?;
        let redirect = Url::parse(redirect_url.trim())
            .and_then(Url::secure)
            .map_err(|e| format!("FRANK_SSO_REDIRECT_URL: {e}"))?;
        let client_id = client_id.trim().to_string();
        if client_id.is_empty() {
            return Err("FRANK_SSO_CLIENT_ID is empty".into());
        }
        let organisation = organisation.trim().to_string();
        if organisation.is_empty() {
            return Err("FRANK_SSO_ORGANISATION is empty".into());
        }
        let secret = std::fs::read_to_string(&secret_file).map_err(|e| {
            format!(
                "FRANK_SSO_CLIENT_SECRET_FILE {}: {}",
                secret_file.display(),
                e.kind()
            )
        })?;
        let secret = secret.trim();
        if secret.is_empty() {
            return Err(format!(
                "FRANK_SSO_CLIENT_SECRET_FILE {} is empty",
                secret_file.display()
            ));
        }
        Ok(Some(Config {
            issuer,
            client_id,
            client_secret: Secret::new(secret),
            origin: redirect.origin(),
            redirect_url: redirect_url.trim().to_string(),
            organisation,
        }))
    }
}

/// The parts of an absolute `http(s)` URL that SSO needs.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Url {
    pub scheme: String,
    /// Lower case.
    pub host: String,
    pub port: Option<u16>,
    /// From the first `/`, query included; `/` when empty.
    pub path: String,
}

impl Url {
    pub fn parse(s: &str) -> Result<Url, String> {
        let (scheme, rest) = s
            .split_once("://")
            .ok_or_else(|| format!("{s:?} is not an absolute URL"))?;
        let scheme = scheme.to_ascii_lowercase();
        if scheme != "https" && scheme != "http" {
            return Err(format!("{s:?}: only http and https"));
        }
        let (authority, path) = match rest.find(['/', '?', '#']) {
            Some(i) => (&rest[..i], &rest[i..]),
            None => (rest, ""),
        };
        if authority.contains('@') {
            return Err(format!("{s:?}: no user info in the URL"));
        }
        let (host, port) = match authority.rsplit_once(':') {
            Some((h, p)) => (
                h,
                Some(
                    p.parse::<u16>()
                        .map_err(|_| format!("{s:?}: bad port {p:?}"))?,
                ),
            ),
            None => (authority, None),
        };
        if host.is_empty() {
            return Err(format!("{s:?}: no host"));
        }
        if path.contains('#') {
            return Err(format!("{s:?}: no fragment"));
        }
        Ok(Url {
            scheme,
            host: host.to_ascii_lowercase(),
            port,
            path: if path.is_empty() {
                "/".into()
            } else {
                path.into()
            },
        })
    }

    /// `https`, or `http` for `localhost` and `*.local` (the local stub).
    pub fn secure(self) -> Result<Url, String> {
        if self.scheme == "https" || self.is_local() {
            Ok(self)
        } else {
            Err(format!(
                "{}: https is required (http only for localhost and *.local)",
                self.origin()
            ))
        }
    }

    #[must_use]
    pub fn is_local(&self) -> bool {
        self.host == "localhost" || self.host.ends_with(".local")
    }

    /// `scheme://host[:port]`.
    #[must_use]
    pub fn origin(&self) -> String {
        match self.port {
            Some(p) => format!("{}://{}:{p}", self.scheme, self.host),
            None => format!("{}://{}", self.scheme, self.host),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct TempFile(PathBuf);
    impl Drop for TempFile {
        fn drop(&mut self) {
            let _ = std::fs::remove_file(&self.0);
        }
    }

    fn secret_file(name: &str, value: &str) -> TempFile {
        let p = std::env::temp_dir().join(format!("frank-sso-{name}-{}", std::process::id()));
        std::fs::write(&p, value).unwrap();
        TempFile(p)
    }

    fn full(file: &TempFile) -> Settings {
        Settings {
            issuer: Some("https://lab271.okta.com/oauth2/default/".into()),
            client_id: Some("0oa123".into()),
            client_secret_file: Some(file.0.clone()),
            redirect_url: Some("https://frank.lab271.dev/v1/sso/callback".into()),
            organisation: Some("lab271".into()),
        }
    }

    #[test]
    fn none_given_is_off() {
        assert!(Config::from_settings(Settings::default())
            .unwrap()
            .is_none());
    }

    #[test]
    fn complete_settings() {
        let f = secret_file("complete", "s3cr3t-value\n");
        let c = Config::from_settings(full(&f)).unwrap().unwrap();
        assert_eq!(c.issuer, "https://lab271.okta.com/oauth2/default");
        assert_eq!(c.client_secret.expose(), "s3cr3t-value");
        assert_eq!(c.origin, "https://frank.lab271.dev");
    }

    #[test]
    fn partial_settings_name_what_is_missing() {
        let f = secret_file("partial", "s3cr3t-value");
        let mut s = full(&f);
        s.client_id = None;
        s.organisation = None;
        let e = Config::from_settings(s).unwrap_err();
        assert!(e.contains("FRANK_SSO_CLIENT_ID"), "{e}");
        assert!(e.contains("FRANK_SSO_ORGANISATION"), "{e}");
        assert!(!e.contains("FRANK_SSO_ISSUER,"), "{e}");
    }

    #[test]
    fn the_secret_is_never_printed() {
        let f = secret_file("printed", "s3cr3t-value");
        let c = Config::from_settings(full(&f)).unwrap().unwrap();
        let shown = format!("{c:?} {}", c.client_secret);
        assert!(!shown.contains("s3cr3t-value"), "{shown}");
    }

    #[test]
    fn an_empty_or_missing_secret_file_is_refused() {
        let f = secret_file("empty", " \n");
        let e = Config::from_settings(full(&f)).unwrap_err();
        assert!(e.contains("is empty"), "{e}");
        let mut s = full(&f);
        s.client_secret_file = Some("/nonexistent/frank-sso-secret".into());
        let e = Config::from_settings(s).unwrap_err();
        assert!(e.contains("not found"), "{e}");
    }

    #[test]
    fn http_only_for_local_hosts() {
        let f = secret_file("http", "x");
        let mut s = full(&f);
        s.issuer = Some("http://lab271.okta.com".into());
        let e = Config::from_settings(s).unwrap_err();
        assert!(e.contains("https is required"), "{e}");
        let mut s = full(&f);
        s.issuer = Some("http://sso.frank.local:9400".into());
        s.redirect_url = Some("https://frank.local:8443/v1/sso/callback".into());
        let c = Config::from_settings(s).unwrap().unwrap();
        assert_eq!(c.origin, "https://frank.local:8443");
    }

    #[test]
    fn urls() {
        let u = Url::parse("HTTPS://Frank.Local:8443/v1/sso/callback?x=1").unwrap();
        assert_eq!(u.host, "frank.local");
        assert_eq!(u.port, Some(8443));
        assert_eq!(u.path, "/v1/sso/callback?x=1");
        assert_eq!(Url::parse("https://a.example").unwrap().path, "/");
        assert!(Url::parse("ftp://a").is_err());
        assert!(Url::parse("https://u:p@a").is_err());
        assert!(Url::parse("https://a:x").is_err());
        assert!(Url::parse("https://a/#f").is_err());
        assert!(Url::parse("a.example").is_err());
    }
}

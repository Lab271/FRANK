//! Opening the object store behind `FRANK_STORE` (#220).
//!
//! db-core's S3 store speaks `http://` only (enough for Garage); AWS needs
//! HTTPS. With the `tls` feature an `https://` endpoint (and AWS's own,
//! when the URI names none) is sent through [`tls::Https`]: ureq over rustls
//! with ring, trusting the platform's certificate store. Without it, an
//! `https://` endpoint is refused with a message that says why.

use std::io;

use db_core::storage::ingest::store::s3::{Credentials, S3Config, S3Store};
use db_core::storage::ingest::Store;

/// The store at `location`: an `s3://bucket/prefix?…` URI or a local
/// directory.
pub fn open(location: &str) -> io::Result<Store> {
    if !location.starts_with("s3://") {
        return Store::at(location);
    }
    let cfg = S3Config::from_uri(location, Credentials::from_chain()?)?;
    if !cfg.endpoint.starts_with("https://") {
        return Store::at(location);
    }
    #[cfg(feature = "tls")]
    {
        let transport = std::sync::Arc::new(tls::Https::new());
        S3Store::with_transport(cfg, transport).map(Store::S3)
    }
    #[cfg(not(feature = "tls"))]
    {
        let _ = S3Store::new;
        Err(io::Error::new(
            io::ErrorKind::Unsupported,
            format!(
                "{}: an https:// endpoint needs a FRANK built with `--features tls` \
                 (the container image is)",
                cfg.endpoint
            ),
        ))
    }
}

#[cfg(feature = "tls")]
pub mod tls {
    use std::io;
    use std::time::Duration;

    use db_core::storage::ingest::store::s3::{HttpRequest, HttpResponse, Transport};
    use ureq::tls::{RootCerts, TlsConfig, TlsProvider};

    /// db-core's [`Transport`] over HTTPS.
    pub struct Https {
        agent: ureq::Agent,
    }

    impl Https {
        #[must_use]
        pub fn new() -> Https {
            let tls = TlsConfig::builder()
                .provider(TlsProvider::Rustls)
                .root_certs(RootCerts::PlatformVerifier)
                .build();
            let agent = ureq::Agent::config_builder()
                .tls_config(tls)
                // Any status is a response for db-core, which decides itself.
                .http_status_as_error(false)
                .timeout_global(Some(Duration::from_secs(60)))
                .build()
                .new_agent();
            Https { agent }
        }
    }

    impl Default for Https {
        fn default() -> Self {
            Https::new()
        }
    }

    fn other(e: impl std::fmt::Display) -> io::Error {
        io::Error::other(e.to_string())
    }

    impl Transport for Https {
        fn send(&self, r: &HttpRequest) -> io::Result<HttpResponse> {
            let scheme = if r.endpoint.https { "https" } else { "http" };
            let url = format!("{scheme}://{}{}", r.endpoint.host_header(), r.target);
            let mut req = ureq::http::Request::builder()
                .method(r.method.as_str())
                .uri(url);
            for (k, v) in &r.headers {
                req = req.header(k.as_str(), v.as_str());
            }
            let req = req.body(r.body.clone()).map_err(other)?;
            let mut res = self.agent.run(req).map_err(other)?;
            let status = res.status().as_u16();
            let headers = res
                .headers()
                .iter()
                .filter_map(|(k, v)| Some((k.as_str().to_string(), v.to_str().ok()?.to_string())))
                .collect();
            // Parquet files outgrow ureq's 10 MB default.
            let body = res
                .body_mut()
                .with_config()
                .limit(u64::MAX)
                .read_to_vec()
                .map_err(other)?;
            Ok(HttpResponse {
                status,
                headers,
                body,
            })
        }
    }
}

#[cfg(all(test, feature = "tls"))]
mod tests {
    use std::io::{Read, Write};
    use std::net::TcpListener;

    use db_core::storage::ingest::store::s3::{Endpoint, HttpRequest, Transport};

    use super::tls::Https;

    fn request(endpoint: Endpoint, method: &str, target: &str, body: &[u8]) -> HttpRequest {
        HttpRequest {
            method: method.into(),
            endpoint,
            target: target.into(),
            headers: vec![("x-amz-content-sha256".into(), "abc".into())],
            body: body.to_vec(),
        }
    }

    /// The adapter sends the method, target, headers and body, and maps any
    /// status, the lowercased headers and the whole body back.
    #[test]
    fn sends_the_request_and_maps_the_response() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = std::thread::spawn(move || {
            let (mut s, _) = listener.accept().unwrap();
            let mut seen = Vec::new();
            let mut buf = [0u8; 1024];
            // The body comes last, so once it is in, the headers are too.
            while !seen.ends_with(b"payload") {
                let n = s.read(&mut buf).unwrap();
                seen.extend_from_slice(&buf[..n]);
            }
            s.write_all(
                b"HTTP/1.1 404 Not Found\r\nETag: \"e1\"\r\nContent-Length: 5\r\n\
                  Connection: close\r\n\r\nhello",
            )
            .unwrap();
            String::from_utf8_lossy(&seen).into_owned()
        });
        let endpoint = Endpoint::parse(&format!("http://127.0.0.1:{port}")).unwrap();
        let res = Https::new()
            .send(&request(endpoint, "PUT", "/b/k?x=y", b"payload"))
            .unwrap();
        assert_eq!(res.status, 404);
        assert_eq!(res.header("etag"), Some("\"e1\""));
        assert_eq!(res.body, b"hello");
        let seen = server.join().unwrap().to_lowercase();
        assert!(seen.starts_with("put /b/k?x=y http/1.1"), "{seen}");
        assert!(seen.contains("x-amz-content-sha256: abc"), "{seen}");
        assert!(seen.contains("content-length: 7"), "{seen}");
    }

    /// A real TLS handshake against the platform's certificate store:
    /// FRANK_TLS_TEST_URL=https://frank.local:9443 (after `make up` and
    /// `make trust`), or any HTTPS endpoint. An unsigned request gets a
    /// status (403 from Garage), which is all this checks.
    #[test]
    #[ignore = "needs an HTTPS endpoint: FRANK_TLS_TEST_URL"]
    fn talks_https_to_an_endpoint() {
        let url = std::env::var("FRANK_TLS_TEST_URL").expect("FRANK_TLS_TEST_URL");
        let res = Https::new()
            .send(&request(Endpoint::parse(&url).unwrap(), "GET", "/", b""))
            .unwrap();
        assert!(res.status >= 200, "{}", res.status);
    }
}

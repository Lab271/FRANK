//! An in-memory S3 bucket behind db-core's `Transport`, for tests that
//! count what a table in a store asks of it (#282, #283, #284). Path-style
//! (`/bkt/key`), no signature checks, no conditional puts: the subset
//! `S3Store` in `CommitMode::SingleWriter` uses.

use std::collections::BTreeMap;
use std::io;
use std::sync::{Arc, Mutex};

use db_core::storage::ingest::store::s3::{
    CommitMode, Credentials, HttpRequest, HttpResponse, S3Config, S3Store, Transport,
};
use db_core::storage::ingest::Store;

/// What the bucket was asked: object GETs (ranged or whole) and their body
/// bytes; listings and HEADs apart.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct Counts {
    pub gets: u64,
    pub bytes: u64,
    pub lists: u64,
    pub heads: u64,
}

#[derive(Default)]
pub struct FakeS3 {
    objects: Mutex<BTreeMap<String, Vec<u8>>>,
    counts: Mutex<Counts>,
}

impl FakeS3 {
    pub fn new() -> Arc<FakeS3> {
        Arc::new(FakeS3::default())
    }

    /// A store on this bucket, with `cache` bytes of read cache.
    pub fn store(self: &Arc<FakeS3>, cache: u64) -> Store {
        let creds = Credentials {
            access_key: "AKTEST".into(),
            secret_key: "secret".into(),
            session_token: None,
        };
        let mut cfg = S3Config::new("http://fake-s3:3900", "garage", "bkt", creds);
        cfg.commit = CommitMode::SingleWriter;
        cfg.read_cache_bytes = cache;
        let transport: Arc<dyn Transport> = self.clone();
        Store::S3(S3Store::with_transport(cfg, transport).expect("fake store"))
    }

    pub fn counts(&self) -> Counts {
        *self.counts.lock().expect("counts")
    }
}

fn decode(s: &str) -> String {
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        let hex = b
            .get(i + 1..i + 3)
            .and_then(|h| std::str::from_utf8(h).ok())
            .and_then(|h| u8::from_str_radix(h, 16).ok());
        match (b[i], hex) {
            (b'%', Some(v)) => {
                out.push(v);
                i += 3;
            }
            (c, _) => {
                out.push(c);
                i += 1;
            }
        }
    }
    String::from_utf8_lossy(&out).into_owned()
}

fn param(query: &str, name: &str) -> Option<String> {
    query
        .split('&')
        .find_map(|kv| kv.split_once('=').filter(|(k, _)| *k == name))
        .map(|(_, v)| decode(v))
}

fn answer(status: u16, headers: Vec<(&str, String)>, body: Vec<u8>) -> HttpResponse {
    HttpResponse {
        status,
        headers: headers
            .into_iter()
            .map(|(k, v)| (k.to_string(), v))
            .collect(),
        body,
    }
}

impl Transport for FakeS3 {
    fn send(&self, req: &HttpRequest) -> io::Result<HttpResponse> {
        let (path, query) = req.target.split_once('?').unwrap_or((&req.target, ""));
        let key = decode(path.strip_prefix("/bkt/").unwrap_or_default());
        let header = |name: &str| {
            req.headers
                .iter()
                .find(|(k, _)| k.eq_ignore_ascii_case(name))
                .map(|(_, v)| v.as_str())
        };
        let mut objects = self.objects.lock().expect("objects");
        let mut counts = self.counts.lock().expect("counts");
        let etag = |b: &[u8]| {
            format!(
                "\"{}-{}\"",
                b.len(),
                b.iter().map(|&x| u64::from(x)).sum::<u64>()
            )
        };
        Ok(match req.method.as_str() {
            "GET" if key.is_empty() => {
                counts.lists += 1;
                let prefix = param(query, "prefix").unwrap_or_default();
                let keys: String = objects
                    .keys()
                    .filter(|k| k.starts_with(&prefix))
                    .map(|k| format!("<Contents><Key>{k}</Key></Contents>"))
                    .collect();
                let body = format!(
                    "<ListBucketResult><IsTruncated>false</IsTruncated>{keys}</ListBucketResult>"
                );
                answer(200, vec![], body.into_bytes())
            }
            "GET" => {
                let Some(bytes) = objects.get(&key) else {
                    return Ok(answer(
                        404,
                        vec![],
                        b"<Error><Code>NoSuchKey</Code></Error>".to_vec(),
                    ));
                };
                counts.gets += 1;
                let range = header("range").and_then(|r| {
                    let (a, b) = r.strip_prefix("bytes=")?.split_once('-')?;
                    Some((a.parse::<usize>().ok()?, b.parse::<usize>().ok()?))
                });
                let (status, body) = match range {
                    Some((a, b)) => (
                        206,
                        bytes[a.min(bytes.len())..(b + 1).min(bytes.len())].to_vec(),
                    ),
                    None => (200, bytes.clone()),
                };
                counts.bytes += body.len() as u64;
                answer(status, vec![("etag", etag(bytes))], body)
            }
            "HEAD" => {
                counts.heads += 1;
                match objects.get(&key) {
                    Some(b) => answer(
                        200,
                        vec![("content-length", b.len().to_string()), ("etag", etag(b))],
                        vec![],
                    ),
                    None => answer(404, vec![], vec![]),
                }
            }
            "PUT" => {
                let tag = etag(&req.body);
                objects.insert(key, req.body.clone());
                answer(200, vec![("etag", tag)], vec![])
            }
            "DELETE" => {
                objects.remove(&key);
                answer(204, vec![], vec![])
            }
            other => answer(501, vec![], format!("{other} not faked").into_bytes()),
        })
    }
}

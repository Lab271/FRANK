//! Reporter pseudonyms (#148): `HMAC-SHA256(window secret, caller id)`, so
//! distinct reporters can be counted without storing who reported.
//!
//! The secret changes every [`WINDOW_DAYS`] days (by arrival time) and the
//! previous one is deleted as soon as its window ends. Within a window the
//! same reporter always gets the same pseudonym, so `count(DISTINCT
//! reporter)` is exact there; across windows it is an upper bound. With
//! the secret gone, nobody can recompute which rows a token sent.

use std::path::{Path, PathBuf};
use std::sync::Mutex;

use hmac::{Hmac, Mac};
use sha2::Sha256;

use crate::auth::{hex, random};

/// Length of a pseudonym window, in days: the default statistics window.
pub const WINDOW_DAYS: i64 = 30;
const DAY_NS: i64 = 86_400 * 1_000_000_000;
const PREFIX: &str = "reporter-";

pub struct Reporters {
    dir: PathBuf,
    now: fn() -> i64,
    /// The current window and its secret.
    current: Mutex<Option<(i64, [u8; 32])>>,
}

impl Reporters {
    /// Keeps its secrets in `<data>/secrets/`.
    pub fn open(data: &Path, now: fn() -> i64) -> Result<Reporters, String> {
        let dir = data.join("secrets");
        std::fs::create_dir_all(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let _ = std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o700));
        }
        Ok(Reporters {
            dir,
            now,
            current: Mutex::new(None),
        })
    }

    /// The pseudonym of `id` (a caller id, or `ingest:<name>`) for the
    /// current window: 32 hex digits.
    pub fn key(&self, id: &str) -> Result<String, String> {
        let window = window_of((self.now)());
        let mut current = self.current.lock().map_err(|_| "reporter lock poisoned")?;
        let secret = match *current {
            Some((w, s)) if w == window => s,
            _ => {
                let s = self.secret(window)?;
                *current = Some((window, s));
                s
            }
        };
        let mut mac = Hmac::<Sha256>::new_from_slice(&secret).map_err(|e| e.to_string())?;
        mac.update(id.as_bytes());
        Ok(hex(&mac.finalize().into_bytes()[..16]))
    }

    /// The secret of `window`: read, or created; older windows' secrets
    /// are deleted.
    fn secret(&self, window: i64) -> Result<[u8; 32], String> {
        self.forget_before(window)?;
        let path = self.dir.join(format!("{PREFIX}{window}.key"));
        if let Ok(bytes) = std::fs::read(&path) {
            return bytes
                .try_into()
                .map_err(|_| format!("{}: not a 32-byte secret", path.display()));
        }
        let secret = random::<32>()?;
        write_private(&path, &secret)?;
        Ok(secret)
    }

    fn forget_before(&self, window: i64) -> Result<(), String> {
        let entries = std::fs::read_dir(&self.dir).map_err(|e| e.to_string())?;
        for e in entries.flatten() {
            let name = e.file_name();
            let old = name
                .to_str()
                .and_then(|n| n.strip_prefix(PREFIX))
                .and_then(|n| n.strip_suffix(".key"))
                .and_then(|w| w.parse::<i64>().ok())
                .is_some_and(|w| w < window);
            if old {
                std::fs::remove_file(e.path()).map_err(|e| e.to_string())?;
            }
        }
        Ok(())
    }
}

/// The window an instant (ns since the epoch) falls in.
#[must_use]
pub fn window_of(ns: i64) -> i64 {
    ns.div_euclid(DAY_NS * WINDOW_DAYS)
}

fn write_private(path: &Path, bytes: &[u8]) -> Result<(), String> {
    use std::io::Write;
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut f = options
        .open(path)
        .map_err(|e| format!("{}: {e}", path.display()))?;
    f.write_all(bytes)
        .and_then(|()| f.sync_all())
        .map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicI64, Ordering};

    static NOW: AtomicI64 = AtomicI64::new(0);
    fn now() -> i64 {
        NOW.load(Ordering::SeqCst)
    }

    #[test]
    fn stable_within_a_window_rotated_across() {
        let dir = std::env::temp_dir().join(format!("frank-reporters-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        let window = DAY_NS * WINDOW_DAYS;
        NOW.store(5 * window + 1, Ordering::SeqCst);
        let r = Reporters::open(&dir, now).unwrap();
        let a = r.key("token-a").unwrap();
        assert_eq!(a.len(), 32);
        assert_eq!(r.key("token-a").unwrap(), a, "same window, same pseudonym");
        assert_ne!(r.key("token-b").unwrap(), a);
        // A restart in the same window reads the same secret.
        assert_eq!(
            Reporters::open(&dir, now).unwrap().key("token-a").unwrap(),
            a
        );

        NOW.store(6 * window + 1, Ordering::SeqCst);
        assert_ne!(
            r.key("token-a").unwrap(),
            a,
            "a new window, a new pseudonym"
        );
        let secrets: Vec<_> = std::fs::read_dir(dir.join("secrets"))
            .unwrap()
            .map(|e| e.unwrap().file_name().into_string().unwrap())
            .collect();
        assert_eq!(
            secrets,
            ["reporter-6.key"],
            "the old window's secret is gone"
        );
        std::fs::remove_dir_all(&dir).ok();
    }
}

//! #192, #193: list files are imported, replaced when they change, dropped
//! when they go, and a broken file leaves its list as it was.

use frank::lists::Lists;

const NOW: i64 = 1_792_670_400_000_000_000;
const MINUTE: i64 = 60 * 1_000_000_000;

struct Dir(std::path::PathBuf);
impl Drop for Dir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn names(l: &Lists, t: &str, v: &str) -> Vec<String> {
    l.annotate(&[(t.into(), v.into())])
        .pop()
        .unwrap()
        .into_iter()
        .map(|x| format!("{}:{}", x.kind, x.list))
        .collect()
}

#[test]
fn lists_follow_their_files() {
    let d = Dir(std::env::temp_dir().join(format!("frank-lists-{}", std::process::id())));
    let _ = std::fs::remove_dir_all(&d.0);
    let (w, r) = (d.0.join("lists/warning"), d.0.join("lists/reference"));
    std::fs::create_dir_all(&w).unwrap();
    std::fs::create_dir_all(&r).unwrap();

    // No files: nothing listed, nothing fails.
    let l = Lists::open(&d.0).unwrap();
    l.refresh(NOW);
    assert!(names(&l, "ipv4", "8.8.8.8").is_empty());

    std::fs::write(w.join("dns.txt"), "8.8.8.0/24\ncdn.example\n").unwrap();
    std::fs::write(
        r.join("feodo_ipblocklist.csv"),
        "# Feodo\nfirst_seen_utc,dst_ip,dst_port,c2_status,last_online,malware\n2026-10-01 00:00:00,8.8.8.8,443,online,,QakBot\n",
    )
    .unwrap();
    l.refresh(NOW + MINUTE);
    assert_eq!(
        names(&l, "ipv4", "8.8.8.8"),
        ["reference:feodo_ipblocklist", "warning:dns"]
    );
    assert_eq!(
        names(&l, "url", "https://img.cdn.example/a.png"),
        ["warning:dns"],
        "by host name"
    );
    assert!(
        names(&l, "domain", "notcdn.example").is_empty(),
        "a label, not a suffix of the text"
    );

    // A broken file leaves its list as it was.
    std::fs::write(
        w.join("misp.json"),
        r#"{"name": "m", "type": "string", "list": ["mutex-x"]}"#,
    )
    .unwrap();
    l.refresh(NOW + 2 * MINUTE);
    assert_eq!(names(&l, "mutex", "mutex-x"), ["warning:misp"]);
    std::thread::sleep(std::time::Duration::from_millis(20));
    std::fs::write(w.join("misp.json"), "{ not json").unwrap();
    l.refresh(NOW + 3 * MINUTE);
    assert_eq!(names(&l, "mutex", "mutex-x"), ["warning:misp"], "kept");

    // An emptied file empties its list; a removed one drops it.
    std::fs::write(w.join("dns.txt"), "").unwrap();
    std::fs::remove_file(r.join("feodo_ipblocklist.csv")).unwrap();
    l.refresh(NOW + 4 * MINUTE);
    assert!(names(&l, "ipv4", "8.8.8.8").is_empty());
}

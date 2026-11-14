//! The `frank` subcommands (#300), run through `frank::cli::run` against a
//! temporary data and participants directory, as `main` runs them.

use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use clap::Parser;
use frank::audit::Audit;
use frank::cli::{self, Cli, Command, Io};
use frank::store::participants::{self as parts, FILE};

struct Dir(PathBuf);
impl Drop for Dir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
fn dir(name: &str) -> Dir {
    let d = std::env::temp_dir().join(format!("frank-cli-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    Dir(d)
}

/// What a command printed, and whether it succeeded.
struct Ran {
    result: Result<(), String>,
    out: String,
    err: String,
}

/// `frank --data <d>/data --participants <d>/participants ARGS…`, parsed, with
/// no object store whatever `FRANK_STORE` says.
fn parse(d: &Path, args: &[&str]) -> Cli {
    let data = d.join("data");
    let participants = d.join("participants");
    let mut argv = vec![
        "frank",
        "--data",
        data.to_str().unwrap(),
        "--participants",
        participants.to_str().unwrap(),
    ];
    argv.extend_from_slice(args);
    let mut cli = Cli::try_parse_from(argv).expect("arguments parse");
    cli.store = None;
    cli
}

/// [`parse`], then run as `main` runs it.
fn frank(d: &Path, args: &[&str]) -> Ran {
    let cli = parse(d, args);
    let (mut out, mut err) = (Vec::new(), Vec::new());
    let result = cli::run(
        cli,
        &mut Io {
            out: &mut out,
            err: &mut err,
        },
    );
    Ran {
        result,
        out: String::from_utf8(out).unwrap(),
        err: String::from_utf8(err).unwrap(),
    }
}

fn ok(d: &Path, args: &[&str]) -> Ran {
    let ran = frank(d, args);
    assert_eq!(ran.result, Ok(()), "frank {args:?}: {}", ran.err);
    ran
}

fn failed(d: &Path, args: &[&str]) -> String {
    frank(d, args)
        .result
        .expect_err(&format!("frank {args:?} should fail"))
}

fn db(d: &Path) -> PathBuf {
    d.join("participants").join(FILE)
}

/// The audit actions written so far, oldest first.
fn actions(d: &Path) -> Vec<String> {
    Audit::open_in(&d.join("data"), None)
        .unwrap()
        .read_from(0)
        .unwrap()
        .iter()
        .map(|l| l["action"].as_str().unwrap_or_default().to_string())
        .collect()
}

#[test]
fn participant_add_list_and_set_status() {
    let d = dir("participant");
    let ran = ok(
        &d.0,
        &[
            "participant",
            "add",
            "acme",
            "--status",
            "contributor",
            "--with-token",
        ],
    );
    let token = ran.out.trim();
    assert!(
        !token.is_empty() && !token.contains(char::is_whitespace),
        "{token:?}"
    );
    assert!(
        ran.err.contains("registered \"acme\" (contributor) as "),
        "{}",
        ran.err
    );
    assert!(
        ran.err.contains("added user \"acme\" and a token for it"),
        "{}",
        ran.err
    );

    let list = ok(&d.0, &["participant", "list"]).out;
    assert!(list.starts_with("acme "), "{list}");
    assert!(
        list.contains(" contributor ") && list.contains("users: acme"),
        "{list}"
    );

    let set = ok(&d.0, &["participant", "set-status", "acme", "partner"]);
    assert_eq!(set.err, "\"acme\" is now partner\n");
    assert!(ok(&d.0, &["participant", "list"]).out.contains(" partner "));
    assert_eq!(
        actions(&d.0),
        [
            "participant_added",
            "user_added",
            "token_issued",
            "status_set"
        ]
    );
}

#[test]
fn users_are_added_listed_given_roles_disabled_and_removed() {
    let d = dir("user");
    ok(&d.0, &["participant", "add", "acme", "--status", "core"]);
    let add = ok(&d.0, &["user", "add", "acme", "alice", "--role", "admin"]);
    assert!(
        add.err.contains("added user \"alice\" to \"acme\""),
        "{}",
        add.err
    );
    ok(&d.0, &["user", "add", "acme", "feed", "--machine"]);

    let list = ok(&d.0, &["user", "list"]).out;
    let alice = list.lines().find(|l| l.starts_with("alice ")).unwrap();
    assert!(
        alice.contains(" human ") && alice.contains(" admin ") && alice.ends_with("acme"),
        "{alice}"
    );
    assert!(
        list.lines()
            .any(|l| l.starts_with("feed ") && l.contains(" machine ")),
        "{list}"
    );

    let role = ok(&d.0, &["user", "set-role", "alice", "none"]);
    assert_eq!(role.err, "\"alice\" is no admin; from the next request\n");
    let disable = ok(&d.0, &["user", "disable", "alice"]);
    assert!(
        disable.err.starts_with("disabled \"alice\""),
        "{}",
        disable.err
    );
    assert!(ok(&d.0, &["user", "list"])
        .out
        .lines()
        .any(|l| l.starts_with("alice ") && l.contains("disabled")));
    assert_eq!(
        ok(&d.0, &["user", "enable", "alice"]).err,
        "enabled \"alice\"\n"
    );
    ok(&d.0, &["user", "disable", "alice"]);
    assert_eq!(
        ok(&d.0, &["user", "remove", "alice"]).err,
        "removed \"alice\" and 0 token(s)\n"
    );
    assert!(!ok(&d.0, &["user", "list"]).out.contains("alice"));
    assert_eq!(
        actions(&d.0),
        [
            "participant_added",
            "user_added",
            "user_added",
            "role_set",
            "user_disabled",
            "user_enabled",
            "user_disabled",
            "user_removed"
        ]
    );
}

#[test]
fn tokens_are_issued_registered_listed_and_revoked() {
    let d = dir("token");
    ok(&d.0, &["participant", "add", "acme", "--status", "partner"]);
    ok(&d.0, &["user", "add", "acme", "feed", "--machine"]);
    let new = ok(&d.0, &["token", "new", "feed"]);
    assert!(!new.out.trim().is_empty());
    assert_eq!(new.err, "added a token for \"feed\"; it is shown once\n");
    let hash = "AB".repeat(32);
    let add = ok(&d.0, &["token", "add", "feed", "--hash", &hash]);
    assert_eq!(add.err, "registered token abababababab… for \"feed\"\n");

    let list = ok(&d.0, &["token", "list"]).out;
    assert_eq!(list.lines().count(), 2, "{list}");
    assert!(
        list.lines()
            .all(|l| l.contains(" active ") && l.ends_with("feed@acme")),
        "{list}"
    );

    let revoke = ok(&d.0, &["token", "revoke", "abababababab"]);
    assert_eq!(revoke.err, "revoked abababababab…\n");
    let list = ok(&d.0, &["token", "list"]).out;
    assert!(
        list.lines()
            .any(|l| l.starts_with("abababababab") && l.contains(" revoked ")),
        "{list}"
    );
    let tokens = parts::tokens(&db(&d.0)).unwrap();
    assert_eq!(tokens.iter().filter(|t| t.revoked).count(), 1);
    assert_eq!(
        actions(&d.0)[2..],
        ["token_issued", "token_issued", "token_revoked"]
    );
}

#[test]
fn bad_input_is_refused_with_what_is_allowed() {
    let d = dir("refused");
    assert_eq!(
        failed(&d.0, &["participant", "add", "acme", "--status", "boss"]),
        "status: observer, contributor, partner or core"
    );
    ok(&d.0, &["participant", "add", "acme", "--status", "core"]);
    ok(&d.0, &["user", "add", "acme", "alice"]);
    assert_eq!(
        failed(&d.0, &["user", "set-role", "alice", "owner"]),
        "role: admin, superadmin or none"
    );
    assert_eq!(
        failed(&d.0, &["user", "add", "acme", "bob", "--role", "owner"]),
        "role: admin, superadmin or none"
    );
    assert!(!failed(&d.0, &["user", "add", "nobody", "carol"]).is_empty());
}

#[test]
fn participants_db_left_in_the_data_directory_is_refused() {
    let d = dir("moved");
    std::fs::create_dir_all(d.0.join("data")).unwrap();
    std::fs::write(d.0.join("data").join(FILE), b"").unwrap();
    let e = failed(&d.0, &["participant", "list"]);
    assert!(e.contains("moved out of the data directory: mv "), "{e}");
}

fn example(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../examples")
        .join(name)
}

#[test]
fn ingest_registers_once_and_rebuild_reads_it_back() {
    let d = dir("ingest");
    let file = example("minimal.json");
    let file = file.to_str().unwrap();
    let e = failed(&d.0, &["ingest", file, "--as", "acme"]);
    assert!(e.ends_with("(register it, or pass --create)"), "{e}");

    let first = ok(&d.0, &["ingest", file, "--as", "acme", "--create"]);
    assert_eq!(first.err, "ingested 1 sightings (0 already registered)\n");
    let again = ok(&d.0, &["ingest", file, "--as", "acme"]);
    assert_eq!(again.err, "ingested 0 sightings (1 already registered)\n");

    // The same sighting id with other content refuses the file.
    let changed = d.0.join("changed.json");
    let text = std::fs::read_to_string(file).unwrap();
    std::fs::write(
        &changed,
        text.replace("\"confidence\": 87", "\"confidence\": 12"),
    )
    .unwrap();
    let e = failed(&d.0, &["ingest", changed.to_str().unwrap(), "--as", "acme"]);
    assert!(e.ends_with("is registered with other content"), "{e}");

    let rebuilt = ok(&d.0, &["rebuild"]);
    assert!(
        rebuilt.err.starts_with("rebuilt iocs from ")
            && rebuilt.err.contains("the registry with 1 registrations"),
        "{}",
        rebuilt.err
    );
    assert_eq!(actions(&d.0), ["participant_added", "ingest", "ingest"]);
}

#[test]
fn serve_refuses_zero_limits_before_it_binds() {
    let d = dir("serve");
    for flag in ["--request-timeout", "--max-concurrency"] {
        assert_eq!(
            failed(&d.0, &["serve", "--listen", "127.0.0.1:0", flag, "0"]),
            "--request-timeout and --max-concurrency must be at least 1"
        );
    }
}

/// Whether `GET /health` on the port answers 200.
fn healthy(port: u16) -> bool {
    let Ok(mut c) = std::net::TcpStream::connect(("127.0.0.1", port)) else {
        return false;
    };
    let mut answer = String::new();
    c.write_all(b"GET /health HTTP/1.1\r\nHost: frank\r\nConnection: close\r\n\r\n")
        .and_then(|()| c.read_to_string(&mut answer))
        .is_ok()
        && answer.starts_with("HTTP/1.1 200")
}

#[test]
fn serve_imports_a_tokens_file_answers_and_stops() {
    let d = dir("serve-run");
    // A Phase 3 tokens file, imported while participants.db holds no tokens.
    let tokens = d.0.join("tokens");
    std::fs::write(
        &tokens,
        format!("{} partner legacy-feed\n", "cd".repeat(32)),
    )
    .unwrap();
    let port = std::net::TcpListener::bind("127.0.0.1:0")
        .unwrap()
        .local_addr()
        .unwrap()
        .port();
    let (listen, web) = (format!("127.0.0.1:{port}"), d.0.join("web"));
    let cli = parse(
        &d.0,
        &[
            "serve",
            "--listen",
            &listen,
            "--tokens",
            tokens.to_str().unwrap(),
            "--web",
            web.to_str().unwrap(),
        ],
    );
    let ctx = cli::setup(&cli).unwrap();
    let Command::Serve(args) = cli.command else {
        unreachable!("parsed as serve")
    };
    // Stop once /health has answered, or after ten seconds.
    let answered = Arc::new(AtomicBool::new(false));
    let seen = answered.clone();
    let stop = async move {
        for _ in 0..200 {
            if tokio::task::spawn_blocking(move || healthy(port))
                .await
                .unwrap_or(false)
            {
                seen.store(true, Ordering::SeqCst);
                return;
            }
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
    };
    frank::serve::start_until(&ctx, args, stop).unwrap();
    assert!(
        answered.load(Ordering::SeqCst),
        "GET /health never answered 200"
    );
    assert_eq!(actions(&d.0), ["tokens_imported"]);
    let imported = parts::tokens(&db(&d.0)).unwrap();
    assert_eq!(imported.len(), 1);
    assert!(
        imported[0].prefix.starts_with("cdcdcdcd"),
        "{}",
        imported[0].prefix
    );
}

// `old.exists() && !db.exists()`: `participants.db` left in the data directory.
#[test]
#[allow(non_snake_case)]
fn mcdc__cli_setup_6ffe4d30__v1_only_the_old_file_is_refused() {
    let d = dir("setup-v1");
    std::fs::create_dir_all(d.0.join("data")).unwrap();
    std::fs::write(d.0.join("data").join(FILE), b"").unwrap();
    let e = cli::setup(&parse(&d.0, &["rebuild"])).err().unwrap();
    assert!(e.contains("moved out of the data directory"), "{e}");
}

#[test]
#[allow(non_snake_case)]
fn mcdc__cli_setup_6ffe4d30__v2_no_old_file_is_set_up() {
    let d = dir("setup-v2");
    assert!(cli::setup(&parse(&d.0, &["rebuild"])).is_ok());
}

#[test]
#[allow(non_snake_case)]
fn mcdc__cli_setup_6ffe4d30__v3_old_file_beside_the_moved_one_is_set_up() {
    let d = dir("setup-v3");
    for sub in ["data", "participants"] {
        std::fs::create_dir_all(d.0.join(sub)).unwrap();
        std::fs::write(d.0.join(sub).join(FILE), b"").unwrap();
    }
    assert!(cli::setup(&parse(&d.0, &["rebuild"])).is_ok());
}

// `known.contains_key(&id) || fresh.iter().any(|f| f.1 == id)`: a sighting
// registered before, or earlier in the same file, is a duplicate.
#[test]
#[allow(non_snake_case)]
fn mcdc__cli_ingest_file_adc096cb__v1_a_new_sighting_is_created() {
    let d = dir("ingest-v1");
    let file = example("minimal.json");
    let r = ok(
        &d.0,
        &["ingest", file.to_str().unwrap(), "--as", "acme", "--create"],
    );
    assert_eq!(r.err, "ingested 1 sightings (0 already registered)\n");
}

#[test]
#[allow(non_snake_case)]
fn mcdc__cli_ingest_file_adc096cb__v2_a_registered_sighting_is_a_duplicate() {
    let d = dir("ingest-v2");
    let file = example("minimal.json");
    let file = file.to_str().unwrap();
    ok(&d.0, &["ingest", file, "--as", "acme", "--create"]);
    let r = ok(&d.0, &["ingest", file, "--as", "acme"]);
    assert_eq!(r.err, "ingested 0 sightings (1 already registered)\n");
}

#[test]
#[allow(non_snake_case)]
fn mcdc__cli_ingest_file_adc096cb__v3_a_repeat_in_the_same_file_is_a_duplicate() {
    let d = dir("ingest-v3");
    let one = std::fs::read_to_string(example("minimal.json")).unwrap();
    let twice = d.0.join("twice.json");
    std::fs::write(&twice, format!("[{one},{one}]")).unwrap();
    let r = ok(
        &d.0,
        &[
            "ingest",
            twice.to_str().unwrap(),
            "--as",
            "acme",
            "--create",
        ],
    );
    assert_eq!(r.err, "ingested 1 sightings (1 already registered)\n");
}

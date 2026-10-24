//! YAML in, JSON out (#160): one YAML 1.2 document read event by event
//! into a `serde_json::Value`, which the JSON adapters then take. Anchors
//! may be set but aliases are refused, so a small document cannot expand
//! into a huge one; nesting is bounded.

use serde_json::{Map, Number, Value};
use yaml_rust2::parser::{Event, MarkedEventReceiver, Parser};
use yaml_rust2::scanner::{Marker, TScalarStyle};

use crate::model::Error;

/// Deepest nesting accepted.
const MAX_DEPTH: usize = 64;

/// The first document of `text` as JSON. Plain scalars resolve as in
/// YAML 1.2's core schema (null, booleans, numbers); quoted and block
/// scalars, and tagged ones, are strings. Infinities and NaN stay strings,
/// as JSON has none.
///
/// # Errors
///
/// [`Error::Malformed`] for text that is not YAML, an alias, a mapping
/// key that is not a scalar, nesting past 64 levels, or no document.
pub fn to_json(text: &str) -> Result<Value, Error> {
    let mut b = Builder::default();
    Parser::new_from_str(text)
        .load(&mut b, false)
        .map_err(|e| Error::Malformed(format!("YAML: {e}")))?;
    if let Some(e) = b.error {
        return Err(Error::Malformed(format!("YAML: {e}")));
    }
    b.doc
        .ok_or_else(|| Error::Malformed("YAML: no document".into()))
}

enum Frame {
    Seq(Vec<Value>),
    /// The mapping so far and the key waiting for its value.
    Map(Map<String, Value>, Option<String>),
}

#[derive(Default)]
struct Builder {
    stack: Vec<Frame>,
    doc: Option<Value>,
    error: Option<String>,
}

impl Builder {
    fn fail(&mut self, mark: Marker, why: &str) {
        self.error
            .get_or_insert_with(|| format!("line {}: {why}", mark.line()));
    }

    fn open(&mut self, frame: Frame, mark: Marker) {
        if self.stack.len() >= MAX_DEPTH {
            self.fail(mark, "nested too deeply");
        } else {
            self.stack.push(frame);
        }
    }

    fn close(&mut self, mark: Marker) {
        let v = match self.stack.pop() {
            Some(Frame::Seq(items)) => Value::Array(items),
            Some(Frame::Map(m, _)) => Value::Object(m),
            None => return,
        };
        self.push(v, mark);
    }

    fn push(&mut self, v: Value, mark: Marker) {
        match self.stack.last_mut() {
            None => self.doc = Some(v),
            Some(Frame::Seq(items)) => items.push(v),
            Some(Frame::Map(m, key)) => match key.take() {
                Some(k) => {
                    m.insert(k, v);
                }
                None => match v {
                    Value::String(s) => *key = Some(s),
                    Value::Array(_) | Value::Object(_) => {
                        self.fail(mark, "a mapping key must be a scalar");
                    }
                    other => *key = Some(other.to_string()),
                },
            },
        }
    }
}

impl MarkedEventReceiver for Builder {
    fn on_event(&mut self, ev: Event, mark: Marker) {
        if self.error.is_some() {
            return;
        }
        match ev {
            Event::Alias(_) => self.fail(mark, "aliases (*name) are not accepted"),
            Event::Scalar(s, style, _, tag) => {
                let v = scalar(s, style == TScalarStyle::Plain && tag.is_none());
                self.push(v, mark);
            }
            Event::SequenceStart(..) => self.open(Frame::Seq(Vec::new()), mark),
            Event::MappingStart(..) => self.open(Frame::Map(Map::new(), None), mark),
            Event::SequenceEnd | Event::MappingEnd => self.close(mark),
            _ => {}
        }
    }
}

fn scalar(s: String, plain: bool) -> Value {
    if !plain {
        return Value::String(s);
    }
    match s.as_str() {
        "" | "~" | "null" | "Null" | "NULL" => return Value::Null,
        "true" | "True" | "TRUE" => return Value::Bool(true),
        "false" | "False" | "FALSE" => return Value::Bool(false),
        _ => {}
    }
    if let Ok(n) = s.parse::<i64>() {
        return Value::Number(n.into());
    }
    let numeric = s.bytes().any(|b| b.is_ascii_digit())
        && s.bytes()
            .all(|b| b.is_ascii_digit() || matches!(b, b'.' | b'e' | b'E' | b'+' | b'-'));
    match s
        .parse::<f64>()
        .ok()
        .filter(|_| numeric)
        .and_then(Number::from_f64)
    {
        Some(n) => Value::Number(n),
        None => Value::String(s),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn reads_a_document_as_json() {
        let v = to_json(
            "a: 1\nb: [x, 'y', \"2\"]\nc: {d: true, e: ~, f: 0.5}\ng: |\n  two\n  lines\nh: 2026-10-22T10:00:00Z\ni: 0f8fad5b-d9cb\n",
        )
        .unwrap();
        assert_eq!(
            v,
            json!({"a": 1, "b": ["x", "y", "2"], "c": {"d": true, "e": null, "f": 0.5},
                   "g": "two\nlines\n", "h": "2026-10-22T10:00:00Z", "i": "0f8fad5b-d9cb"})
        );
    }

    #[test]
    fn refuses_aliases_and_deep_nesting() {
        let bomb = "a: &a [x, x]\nb: &b [*a, *a]\nc: [*b, *b]\n";
        assert!(matches!(to_json(bomb), Err(Error::Malformed(m)) if m.contains("aliases")));
        assert!(to_json(&format!("{}x{}", "[".repeat(65), "]".repeat(65))).is_err());
        assert!(to_json(&format!("{}x{}", "[".repeat(10), "]".repeat(10))).is_ok());
        assert!(to_json("? [a]\n: b\n").is_err(), "complex key");
        assert!(to_json("a: [").is_err());
        assert!(to_json("").is_err());
    }
}

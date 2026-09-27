//! Read-only observer grant. No experiment commands or participant fields.
use serde::Deserialize;
use serde_json::{Value, json};
use std::time::{Duration, Instant};

#[derive(Deserialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
pub enum ViewerAction {
    Start {},
    Snapshot { token: String },
    Stop { token: String },
}

pub struct ViewerSession {
    token: String,
    expires: Instant,
}

fn token() -> Result<String, String> {
    let mut bytes = [0_u8; 32];
    getrandom::fill(&mut bytes).map_err(|_| "Cannot generate viewer credentials")?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

impl ViewerSession {
    pub fn start() -> Result<(Self, Value), String> {
        let grant = token()?;
        let invite = json!({"room":format!("brsp_{}", token()?), "secret":token()?, "token":grant});
        Ok((
            Self {
                token: grant,
                expires: Instant::now() + Duration::from_secs(4 * 60 * 60),
            },
            invite,
        ))
    }

    pub fn permits(&self, value: &str) -> bool {
        value.len() == 64 && value == self.token && Instant::now() < self.expires
    }
}

pub fn projection(snapshot: &Value, progress: &Value, revision: u64) -> Value {
    let phase = snapshot["phase"].as_str().unwrap_or("starting");
    let mut result = json!({"profile":"respyra.observer/1", "revision":revision,
        "phase":phase, "inputReady":snapshot["can_start"].as_bool().unwrap_or(false),
        "event":null, "seq":null, "lslTime":null, "trial":null,
        "condition":null, "experimentPhase":null, "screen":null});
    for (source, dest) in [
        ("event", "event"),
        ("condition", "condition"),
        ("experiment_phase", "experimentPhase"),
        ("screen", "screen"),
    ] {
        if let Some(text) = progress[source]
            .as_str()
            .filter(|text| text.len() <= 80 && !text.chars().any(char::is_control))
        {
            result[dest] = json!(text);
        }
    }
    for (source, dest) in [("seq", "seq"), ("trial", "trial")] {
        if let Some(number) = progress[source]
            .as_u64()
            .filter(|number| *number <= 9_007_199_254_740_991)
        {
            result[dest] = json!(number);
        }
    }
    if let Some(time) = progress["lsl_time"]
        .as_f64()
        .filter(|time| time.is_finite() && *time >= 0.0)
    {
        result["lslTime"] = json!(time);
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn grants_rotate_expire_and_projection_excludes_private_fields() {
        let (mut first, invite) = ViewerSession::start().unwrap();
        let key = invite["token"].as_str().unwrap();
        assert!(first.permits(key));
        assert!(!first.permits("wrong"));
        let (second, _) = ViewerSession::start().unwrap();
        assert!(!second.permits(key));
        first.expires = Instant::now() - Duration::from_secs(1);
        assert!(!first.permits(key));
        let value = projection(
            &json!({"phase":"setup", "values":{"participant":"private"}, "message":"private", "can_start":true}),
            &json!({"event":"trial.started", "seq":7, "trial":2, "lsl_time":123.5, "participant":"private", "response":"private", "experiment_phase":"tracking"}),
            9,
        );
        assert!(!value.to_string().contains("private"));
        assert_eq!(value["trial"], 2);
        assert_eq!(value["lslTime"], 123.5);
        assert_eq!(value["revision"], 9);
        assert!(
            serde_json::from_value::<ViewerAction>(json!({"action":"start", "path":"x"})).is_err()
        );
        assert!(
            serde_json::from_value::<ViewerAction>(json!({"action":"start_experiment"})).is_err()
        );
    }
}

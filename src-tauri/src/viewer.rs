//! Native fences for the bundled WebView's authenticated BRSP controller.
//! Mutual HMAC proof stays in pinned BRSP JS; untrusted pages have no IPC.
use serde::Deserialize;
use serde_json::{Value, json};
use std::{
    collections::HashMap,
    time::{Duration, Instant},
};

pub const SCOPES: [&str; 3] = ["experiment.observe", "experiment.setup", "experiment.run"];
const LEASE: Duration = Duration::from_secs(6);

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RemoteCommand {
    pub command_id: String,
    pub scope: String,
    pub action: String,
    pub args: Value,
    pub expected_revision: Option<u64>,
}

#[derive(Deserialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
pub enum ViewerAction {
    Start {},
    Claim {
        token: String,
        peer_id: String,
        epoch: u32,
        scopes: Vec<String>,
    },
    Snapshot {
        token: String,
        owner: String,
    },
    Dispatch {
        token: String,
        owner: String,
        peer_id: String,
        epoch: u32,
        sequence: u32,
        command: RemoteCommand,
    },
    Stop {
        token: String,
    },
}

struct Owner {
    token: String,
    peer_id: String,
    epoch: u32,
    sequence: u32,
    deadline: Instant,
    scopes: Vec<String>,
}

struct Cached {
    request: String,
    outcome: Option<Value>,
}

pub struct ViewerSession {
    token: String,
    expires: Instant,
    owner: Option<Owner>,
    commands: HashMap<String, Cached>,
}

fn token() -> Result<String, String> {
    let mut bytes = [0_u8; 32];
    getrandom::fill(&mut bytes).map_err(|_| "Cannot generate remote credentials")?;
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
                owner: None,
                commands: HashMap::new(),
            },
            invite,
        ))
    }

    pub fn permits(&self, value: &str) -> bool {
        value.len() == 64 && value == self.token && Instant::now() < self.expires
    }

    pub fn claim(
        &mut self,
        key: &str,
        peer_id: String,
        epoch: u32,
        scopes: Vec<String>,
    ) -> Result<Value, String> {
        if !self.permits(key) || self.owner.is_some() {
            return Err("Remote session is unavailable; enable a fresh link".into());
        }
        if !(8..=96).contains(&peer_id.len())
            || !peer_id
                .bytes()
                .all(|c| c.is_ascii_alphanumeric() || b"_-".contains(&c))
            || scopes.is_empty()
            || scopes.len() > SCOPES.len()
            || !scopes.iter().any(|s| s == SCOPES[0])
            || scopes
                .iter()
                .enumerate()
                .any(|(i, s)| !SCOPES.contains(&s.as_str()) || scopes[..i].contains(s))
        {
            return Err("Invalid remote owner or scopes".into());
        }
        let owner_token = token()?;
        self.owner = Some(Owner {
            token: owner_token.clone(),
            peer_id,
            epoch,
            scopes,
            sequence: 0,
            deadline: Instant::now() + LEASE,
        });
        Ok(json!({"owner":owner_token}))
    }

    pub fn read(&self, key: &str, owner_token: &str) -> Result<(), String> {
        if !self.permits(key)
            || !self
                .owner
                .as_ref()
                .is_some_and(|owner| owner.token == owner_token && Instant::now() < owner.deadline)
        {
            return Err("Remote ownership expired; enable a fresh link".into());
        }
        Ok(())
    }

    pub fn has_scope(&self, scope: &str) -> bool {
        self.owner
            .as_ref()
            .is_some_and(|owner| owner.scopes.iter().any(|s| s == scope))
    }

    pub fn authorize(
        &mut self,
        key: &str,
        owner_token: &str,
        peer: &str,
        epoch: u32,
        sequence: u32,
        scope: &str,
    ) -> Result<(), String> {
        self.read(key, owner_token)?;
        let owner = self.owner.as_mut().ok_or("Remote owner missing")?;
        let distance = sequence.wrapping_sub(owner.sequence);
        if owner.peer_id != peer
            || owner.epoch != epoch
            || distance == 0
            || distance >= 0x8000_0000
            || !owner.scopes.iter().any(|s| s == scope)
        {
            return Err("Remote owner, sequence or scope rejected".into());
        }
        owner.sequence = sequence;
        owner.deadline = Instant::now() + LEASE;
        Ok(())
    }

    pub fn begin_command(&mut self, command: &RemoteCommand) -> Result<Option<Value>, String> {
        if !(8..=96).contains(&command.command_id.len())
            || !command
                .command_id
                .bytes()
                .all(|c| c.is_ascii_alphanumeric() || b"_-".contains(&c))
        {
            return Err("Invalid command ID".into());
        }
        let request = json!({"scope":command.scope, "action":command.action,
            "args":command.args, "expectedRevision":command.expected_revision})
        .to_string();
        if request.len() > 4096 {
            return Err("Remote command is too large".into());
        }
        if let Some(cached) = self.commands.get(&command.command_id) {
            if cached.request != request {
                self.owner = None;
                return Err(
                    "Command ID reused with a different body; remote control revoked".into(),
                );
            }
            return cached
                .outcome
                .clone()
                .map(Some)
                .ok_or("Command outcome is still unknown".into());
        }
        if self.commands.len() >= 4096 {
            return Err("Remote command limit reached; enable a fresh link".into());
        }
        self.commands.insert(
            command.command_id.clone(),
            Cached {
                request,
                outcome: None,
            },
        );
        Ok(None)
    }

    pub fn complete(&mut self, command_id: &str, outcome: Value) {
        if let Some(cached) = self.commands.get_mut(command_id) {
            cached.outcome = Some(outcome);
        }
    }
}

pub fn projection(
    snapshot: &Value,
    progress: &Value,
    revision: u64,
    monitor_revision: u64,
    setup_scope: bool,
) -> Value {
    let mut result = json!({"profile":"respyra.controller/1", "revision":revision,
        "monitorRevision":monitor_revision, "phase":snapshot["phase"],
        "message":if setup_scope { snapshot["message"].clone() }
            else { json!("Observe-only connection. Use the local controller for details.") },
        "setup":null, "progress":progress});
    if setup_scope && snapshot["phase"] == "setup" {
        let mut setup = snapshot.clone();
        let rows = setup["streams"].as_array().cloned().unwrap_or_default();
        setup["streams"] = json!([]);
        result["setup"] = setup;
        result["setup"]["omitted_streams"] = json!(rows.len());
        for (index, mut row) in rows.into_iter().enumerate() {
            row["row"] = json!(index);
            let mut candidate = result.clone();
            candidate["setup"]["streams"]
                .as_array_mut()
                .unwrap()
                .push(row);
            candidate["setup"]["omitted_streams"] = json!(
                result["setup"]["omitted_streams"]
                    .as_u64()
                    .unwrap_or(0)
                    .saturating_sub(1)
            );
            if candidate.to_string().len() <= 7900 {
                result = candidate;
            }
        }
        let visible = result["setup"]["streams"]
            .as_array()
            .unwrap()
            .iter()
            .any(|row| row["row"] == result["setup"]["selected_row"]);
        if result["setup"]["can_use"] == true && !visible {
            result["setup"]["can_use"] = json!(false);
        }
    }
    if result.to_string().len() > 8192 {
        return json!({"profile":"respyra.controller/1", "revision":revision,
            "monitorRevision":monitor_revision, "phase":snapshot["phase"],
            "message":"State exceeds the phone limit. Use the local controller.",
            "setup":null, "progress":null});
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn ownership_scopes_sequence_expiry_and_deduplication() {
        let (mut session, invite) = ViewerSession::start().unwrap();
        let key = invite["token"].as_str().unwrap();
        assert!(session.read(key, "unclaimed").is_err());
        let owner = session
            .claim(
                key,
                "phone_test".into(),
                7,
                SCOPES.iter().map(|s| s.to_string()).collect(),
            )
            .unwrap();
        let owner = owner["owner"].as_str().unwrap();
        assert!(
            session
                .claim(key, "second_phone".into(), 8, vec![SCOPES[0].into()])
                .is_err()
        );
        assert!(
            session
                .authorize(key, owner, "wrong_peer", 7, 1, SCOPES[1])
                .is_err()
        );
        assert!(
            session
                .authorize(key, owner, "phone_test", 8, 1, SCOPES[1])
                .is_err()
        );
        session
            .authorize(key, owner, "phone_test", 7, 1, SCOPES[1])
            .unwrap();
        assert!(
            session
                .authorize(key, owner, "phone_test", 7, 1, SCOPES[1])
                .is_err()
        );
        let mut command = RemoteCommand {
            command_id: "cmd_12345".into(),
            scope: SCOPES[1].into(),
            action: "scan".into(),
            args: json!({}),
            expected_revision: Some(0),
        };
        assert!(session.begin_command(&command).unwrap().is_none());
        assert!(session.begin_command(&command).is_err());
        session.complete(&command.command_id, json!({"ok":true, "revision":1}));
        assert_eq!(
            session.begin_command(&command).unwrap().unwrap()["ok"],
            true
        );
        session.owner.as_mut().unwrap().deadline = Instant::now() - Duration::from_secs(1);
        assert!(session.read(key, owner).is_err());
        assert!(
            session
                .authorize(key, owner, "phone_test", 7, 2, SCOPES[1])
                .is_err()
        );
        command.action = "start".into();
        assert!(session.begin_command(&command).is_err());
        assert!(session.owner.is_none());
        assert!(
            serde_json::from_value::<ViewerAction>(json!({"action":"start","path":"x"})).is_err()
        );
    }
    #[test]
    fn projections_are_bounded_and_scoped() {
        let snapshot = json!({"phase":"setup","message":"Ready","values":{"participant":"private"},"streams":[]});
        assert!(
            !projection(&snapshot, &Value::Null, 1, 2, false)
                .to_string()
                .contains("private")
        );
        assert!(
            projection(&snapshot, &Value::Null, 1, 2, true)
                .to_string()
                .contains("private")
        );
        let mut snapshot = snapshot;
        snapshot["streams"] = json!(
            (0..100)
                .map(|_| json!({"source_id":"s".repeat(500)}))
                .collect::<Vec<_>>()
        );
        let view = projection(&snapshot, &Value::Null, 1, 2, true);
        assert!(view.to_string().len() <= 8192);
        assert!(view["setup"]["omitted_streams"].as_u64().unwrap() > 0);
    }
}

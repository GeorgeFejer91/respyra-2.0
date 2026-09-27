#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::HashMap,
    io::{BufRead, BufReader, Read, Write},
    path::Path,
    process::{Child, ChildStdin, Command, Stdio},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread,
    time::{Duration, Instant},
};
use tauri::{Emitter, Manager};

const PREFIX: &str = "RESPYRA/1 ";
mod viewer;

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
enum Field {
    Participant,
    Session,
    MarkerName,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
enum RecordingOption {
    SaveCsv,
}

#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
enum CloseReason {
    CloseButton,
    ProtocolFailure,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
enum Action {
    Shown {
        ui_seq: u64,
        ui_time_ms: f64,
    },
    FieldKey {
        ui_seq: u64,
        ui_time_ms: f64,
        field: Field,
        key: String,
    },
    FieldEdit {
        ui_seq: u64,
        ui_time_ms: f64,
        field: Field,
        value: String,
    },
    Option {
        ui_seq: u64,
        ui_time_ms: f64,
        field: RecordingOption,
        enabled: bool,
    },
    Scan {
        ui_seq: u64,
        ui_time_ms: f64,
    },
    Select {
        ui_seq: u64,
        ui_time_ms: f64,
        row: usize,
    },
    Use {
        ui_seq: u64,
        ui_time_ms: f64,
    },
    Start {
        ui_seq: u64,
        ui_time_ms: f64,
    },
    Cancel {
        ui_seq: u64,
        ui_time_ms: f64,
    },
    Abort {
        ui_seq: u64,
        ui_time_ms: f64,
    },
}

fn encode_action(action: &Action) -> Result<Vec<u8>, String> {
    let value = serde_json::to_value(action).map_err(|e| e.to_string())?;
    let seq = value["ui_seq"].as_u64().unwrap_or(0);
    let time = value["ui_time_ms"].as_f64().unwrap_or(-1.0);
    if seq == 0 || !time.is_finite() || time < 0.0 {
        return Err("Invalid UI sequence or timestamp".into());
    }
    for key in ["key", "value"] {
        if value[key]
            .as_str()
            .is_some_and(|text| text.chars().count() > 128)
        {
            return Err("Participant input is too long".into());
        }
    }
    let mut bytes = serde_json::to_vec(action).map_err(|e| e.to_string())?;
    bytes.push(b'\n');
    Ok(bytes)
}

struct Engine {
    child: Option<Child>,
    input: Option<ChildStdin>,
    snapshot: Value,
    launched: bool,
    progress: Value,
    revision: u64,
    control_revision: u64,
    sequence: u64,
    local_sequence: u64,
    pending: HashMap<u64, mpsc::Sender<Value>>,
    viewer: Option<viewer::ViewerSession>,
}

struct Desktop {
    engine: Arc<Mutex<Engine>>,
    closing: Arc<AtomicBool>,
}

impl Default for Desktop {
    fn default() -> Self {
        Self {
            engine: Arc::new(Mutex::new(Engine {
                child: None,
                input: None,
                snapshot: json!({"phase":"starting", "message":"Starting the experiment engine…"}),
                launched: false,
                progress: Value::Null,
                revision: 0,
                control_revision: 0,
                sequence: 0,
                local_sequence: 0,
                pending: HashMap::new(),
                viewer: None,
            })),
            closing: Arc::new(AtomicBool::new(false)),
        }
    }
}

fn publish(app: &tauri::AppHandle, engine: &Arc<Mutex<Engine>>, snapshot: Value) {
    let mut display = snapshot.clone();
    if let Ok(mut state) = engine.lock() {
        if snapshot["phase"] == "action_result" {
            if let Some(sequence) = snapshot["ui_seq"].as_u64()
                && let Some(reply) = state.pending.remove(&sequence)
            {
                let _ = reply.send(
                    json!({"ok":snapshot["ok"], "revision":state.control_revision,
                    "message":snapshot["message"]}),
                );
            }
            return;
        }
        state.revision += 1;
        if snapshot["phase"] == "progress" {
            state.progress = snapshot.clone();
            display = state.snapshot.clone();
        } else {
            if state.snapshot != snapshot {
                state.control_revision += 1;
            }
            state.snapshot = snapshot.clone();
        }
        display["progress"] = state.progress.clone();
        display["revision"] = json!(state.control_revision);
    }
    if let Some(window) = app.get_webview_window("main")
        && (snapshot["phase"] == "finished" || snapshot["phase"] == "error")
    {
        let _ = window.show();
        let _ = window.set_focus();
    }
    let _ = app.emit("setup-state", display);
}

fn decode_frame(line: &str) -> Result<Option<Value>, String> {
    let Some(payload) = line.strip_prefix(PREFIX) else {
        return Ok(None);
    };
    let value: Value = serde_json::from_str(payload).map_err(|e| e.to_string())?;
    if !matches!(
        value["phase"].as_str(),
        Some(
            "starting"
                | "setup"
                | "experiment"
                | "finished"
                | "error"
                | "progress"
                | "action_result"
        )
    ) {
        return Err("Invalid engine state".into());
    }
    Ok(Some(value))
}

#[tauri::command]
fn launch_backend(
    app: tauri::AppHandle,
    desktop: tauri::State<'_, Desktop>,
) -> Result<Value, String> {
    let mut state = desktop
        .engine
        .lock()
        .map_err(|_| "Desktop state lock failed")?;
    if state.launched {
        return Ok(state.snapshot.clone());
    }
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .ok_or("Missing workspace root")?;
    let python = root.join(if cfg!(windows) {
        ".venv/Scripts/python.exe"
    } else {
        ".venv/bin/python"
    });
    if !python.is_file() {
        return Err(
            "Python environment missing. Run uv sync --frozen in the checkout first.".into(),
        );
    }
    let mut command = Command::new(python);
    command
        .arg("-u")
        .arg(root.join("scripts/run_experiment.py"))
        .arg("--desktop")
        .current_dir(root)
        .env("PYTHONIOENCODING", "utf-8")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW; PsychoPy owns its display.
    }
    let mut child = command
        .spawn()
        .map_err(|e| format!("Cannot start experiment engine: {e}"))?;
    let output = child.stdout.take().ok_or("Engine output pipe missing")?;
    state.input = child.stdin.take();
    state.child = Some(child);
    state.launched = true;
    let initial = state.snapshot.clone();
    drop(state);
    let engine = Arc::clone(&desktop.engine);
    let closing = Arc::clone(&desktop.closing);
    thread::spawn(move || {
        let mut reader = BufReader::new(output);
        let failure = loop {
            let mut line = String::new();
            match (&mut reader).take(1_000_001).read_line(&mut line) {
                Ok(0) => break None,
                Ok(_) if line.len() > 1_000_000 || !line.ends_with('\n') => {
                    break Some("Oversized or incomplete engine frame".to_string());
                }
                Ok(_) => match decode_frame(&line) {
                    Ok(Some(snapshot)) => publish(&app, &engine, snapshot),
                    Ok(None) => (),
                    Err(error) => break Some(error),
                },
                Err(error) => break Some(error.to_string()),
            }
        };
        if let Some(error) = failure {
            publish(&app, &engine, json!({"phase":"error", "message":error}));
            shutdown(&engine, "engine_failed");
        } else if !closing.load(Ordering::Acquire) {
            // Never treat a crashed engine as a completed experiment.
            let success = shutdown(&engine, "engine_failed");
            let complete = engine.lock().is_ok_and(|state| {
                matches!(state.snapshot["phase"].as_str(), Some("finished" | "error"))
            });
            if !complete || !success {
                let already_error = engine
                    .lock()
                    .is_ok_and(|state| state.snapshot["phase"] == "error");
                if !already_error {
                    publish(
                        &app,
                        &engine,
                        json!({"phase":"error", "message":"Experiment engine exited unexpectedly. Check the LSL recording."}),
                    );
                }
            }
        }
    });
    Ok(initial)
}

fn queue_action(
    state: &mut Engine,
    action: Action,
    origin: &str,
) -> Result<Result<(u64, mpsc::Receiver<Value>), Value>, String> {
    encode_action(&action)?;
    let mut value = serde_json::to_value(action).map_err(|e| e.to_string())?;
    let client_sequence = value["ui_seq"].as_u64().ok_or("Invalid client sequence")?;
    if origin == "local" {
        if client_sequence != state.local_sequence + 1 {
            return Err("Local actions arrived out of order".into());
        }
        state.local_sequence = client_sequence;
    }
    let permitted = if value["action"] == "abort" {
        state.snapshot["phase"] == "experiment"
    } else {
        state.snapshot["phase"] == "setup"
    };
    if !permitted {
        return Ok(Err(
            json!({"ok":false,"revision":state.control_revision,"message":"Control is unavailable in this phase"}),
        ));
    }
    if state.pending.len() >= 128 {
        return Err("Engine action queue is full".into());
    }
    state.sequence += 1;
    let sequence = state.sequence;
    value["ui_seq"] = json!(sequence);
    value["ui_client_seq"] = json!(client_sequence);
    value["ui_origin"] = json!(origin);
    let mut bytes = serde_json::to_vec(&value).map_err(|e| e.to_string())?;
    bytes.push(b'\n');
    let (sender, receiver) = mpsc::channel();
    state.pending.insert(sequence, sender);
    let input = state
        .input
        .as_mut()
        .ok_or("Experiment engine is not running")?;
    input
        .write_all(&bytes)
        .and_then(|_| input.flush())
        .map_err(|e| e.to_string())?;
    Ok(Ok((sequence, receiver)))
}

fn wait_action(queued: Result<(u64, mpsc::Receiver<Value>), Value>) -> Result<Value, String> {
    match queued {
        Err(rejected) => Ok(rejected),
        Ok((_sequence, receiver)) => receiver.recv_timeout(Duration::from_secs(12)).map_err(|_| {
            "Command outcome unknown; check the local controller before trying again".into()
        }),
    }
}

#[tauri::command]
async fn setup_action(action: Action, desktop: tauri::State<'_, Desktop>) -> Result<Value, String> {
    if desktop.closing.load(Ordering::Acquire) {
        return Err("Desktop is closing".into());
    }
    let engine = Arc::clone(&desktop.engine);
    tauri::async_runtime::spawn_blocking(move || {
        let queued = queue_action(
            &mut *engine.lock().map_err(|_| "Desktop state lock failed")?,
            action,
            "local",
        )?;
        wait_action(queued)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn viewer_action(
    app: tauri::AppHandle,
    action: viewer::ViewerAction,
    desktop: tauri::State<'_, Desktop>,
) -> Result<Value, String> {
    if desktop.closing.load(Ordering::Acquire) {
        return Err("Desktop is closing".into());
    }
    let engine = Arc::clone(&desktop.engine);
    tauri::async_runtime::spawn_blocking(move || handle_viewer(app, &engine, action))
        .await
        .map_err(|e| e.to_string())?
}

fn handle_viewer(
    app: tauri::AppHandle,
    engine: &Arc<Mutex<Engine>>,
    action: viewer::ViewerAction,
) -> Result<Value, String> {
    let mut state = engine.lock().map_err(|_| "Desktop state lock failed")?;
    match action {
        viewer::ViewerAction::Start {} => {
            let (session, invitation) = viewer::ViewerSession::start()?;
            state.viewer = Some(session);
            Ok(invitation)
        }
        viewer::ViewerAction::Claim {
            token,
            peer_id,
            epoch,
            scopes,
        } => state
            .viewer
            .as_mut()
            .ok_or("Remote control disabled")?
            .claim(&token, peer_id, epoch, scopes),
        viewer::ViewerAction::Snapshot { token, owner } => {
            let session = state.viewer.as_ref().ok_or("Remote control disabled")?;
            session.read(&token, &owner)?;
            Ok(viewer::projection(
                &state.snapshot,
                &state.progress,
                state.control_revision,
                state.revision,
                session.has_scope(viewer::SCOPES[1]),
            ))
        }
        viewer::ViewerAction::Dispatch {
            token,
            owner,
            peer_id,
            epoch,
            sequence,
            command,
        } => {
            let session = state.viewer.as_mut().ok_or("Remote control disabled")?;
            session.authorize(&token, &owner, &peer_id, epoch, sequence, &command.scope)?;
            if command.scope == viewer::SCOPES[0]
                && command.action == "renew"
                && command.args == json!({})
                && command.expected_revision.is_none()
            {
                return Ok(
                    json!({"ok":true,"revision":state.control_revision,"result":null,"error":null}),
                );
            }
            if let Some(cached) = session.begin_command(&command)? {
                return Ok(cached);
            }
            let command_id = command.command_id.clone();
            let outcome = if command.expected_revision != Some(state.control_revision) {
                Err("State changed; review the current controls".to_string())
            } else if command.scope == viewer::SCOPES[2]
                && command.action == "close"
                && command.args == json!({})
                && matches!(state.snapshot["phase"].as_str(), Some("finished" | "error"))
            {
                let outcome =
                    json!({"ok":true,"revision":state.control_revision,"result":null,"error":null});
                state
                    .viewer
                    .as_mut()
                    .unwrap()
                    .complete(&command_id, outcome.clone());
                drop(state);
                // The reliable acceptance reply precedes shutdown; this is not
                // a claim that the final LSL marker has already been persisted.
                thread::spawn(move || {
                    thread::sleep(Duration::from_millis(800));
                    request_close(app, "close_button");
                });
                return Ok(outcome);
            } else {
                remote_action(&command)
                    .and_then(|action| queue_action(&mut state, action, "remote"))
            };
            let revision = state.control_revision;
            drop(state);
            let receipt = match outcome {
                Ok(queued) => wait_action(queued),
                Err(error) => Err(error),
            };
            let mut state = engine.lock().map_err(|_| "Desktop state lock failed")?;
            let outcome = match receipt {
                Ok(value) => json!({"ok":value["ok"],"revision":value["revision"],
                    "result":null,"error":if value["ok"] == true { Value::Null } else { value["message"].clone() }}),
                Err(error) => json!({"ok":false,"revision":revision,"result":null,"error":error}),
            };
            if let Some(session) = state.viewer.as_mut().filter(|s| s.permits(&token)) {
                session.complete(&command_id, outcome.clone());
            }
            Ok(outcome)
        }
        viewer::ViewerAction::Stop { token } => {
            if state
                .viewer
                .as_ref()
                .is_some_and(|session| session.permits(&token))
            {
                state.viewer = None;
            }
            Ok(Value::Null)
        }
    }
}

fn remote_action(command: &viewer::RemoteCommand) -> Result<Action, String> {
    let permitted = match command.scope.as_str() {
        "experiment.setup" => matches!(
            command.action.as_str(),
            "field_key" | "field_edit" | "option" | "scan" | "select" | "use" | "cancel"
        ),
        "experiment.run" => matches!(command.action.as_str(), "start" | "abort"),
        _ => false,
    };
    if !permitted {
        return Err("Unsupported remote action or scope".into());
    }
    let mut payload = command
        .args
        .as_object()
        .cloned()
        .ok_or("Invalid remote arguments")?;
    if payload.contains_key("action") {
        return Err("Unexpected remote action field".into());
    }
    payload.insert("action".into(), json!(command.action));
    let action: Action = serde_json::from_value(Value::Object(payload))
        .map_err(|_| "Invalid remote action fields")?;
    encode_action(&action)?;
    Ok(action)
}

fn shutdown(engine: &Arc<Mutex<Engine>>, reason: &str) -> bool {
    if let Ok(mut state) = engine.lock()
        && let Some(mut input) = state.input.take()
    {
        let message = json!({"action":"shutdown", "reason":reason}).to_string() + "\n";
        let _ = input.write_all(message.as_bytes());
        let _ = input.flush();
    }
    let deadline = Instant::now() + Duration::from_secs(15);
    loop {
        if let Ok(mut state) = engine.lock() {
            let Some(child) = state.child.as_mut() else {
                return true;
            };
            match child.try_wait() {
                Ok(Some(status)) => {
                    state.child.take();
                    return status.success();
                }
                _ if Instant::now() >= deadline => {
                    eprintln!(
                        "Respyra engine did not stop within 15 seconds; terminating it. Final LSL markers may be absent."
                    );
                    // Windows' venv launcher owns a second Python process.
                    // Kill that owned tree as well if graceful cleanup hangs.
                    #[cfg(windows)]
                    if let Some(system_root) = std::env::var_os("SystemRoot") {
                        use std::os::windows::process::CommandExt;
                        let _ = Command::new(Path::new(&system_root).join("System32/taskkill.exe"))
                            .args(["/PID", &child.id().to_string(), "/T", "/F"])
                            .stdin(Stdio::null())
                            .stdout(Stdio::null())
                            .stderr(Stdio::null())
                            .creation_flags(0x08000000)
                            .status();
                    }
                    let _ = child.kill();
                    let _ = child.wait();
                    state.child.take();
                    return false;
                }
                _ => (),
            }
        } else {
            eprintln!("Cannot lock the engine during shutdown.");
            return false;
        }
        thread::sleep(Duration::from_millis(50));
    }
}

fn request_close(app: tauri::AppHandle, reason: &'static str) {
    let desktop = app.state::<Desktop>();
    if desktop.closing.swap(true, Ordering::AcqRel) {
        return;
    }
    let engine = Arc::clone(&desktop.engine);
    if let Ok(mut state) = engine.lock() {
        state.viewer = None;
    }
    thread::spawn(move || {
        shutdown(&engine, reason);
        app.exit(0);
    });
}

#[tauri::command]
fn close_app(app: tauri::AppHandle, reason: CloseReason) {
    request_close(
        app,
        match reason {
            CloseReason::CloseButton => "close_button",
            CloseReason::ProtocolFailure => "protocol_failure",
        },
    );
}

fn main() {
    tauri::Builder::default()
        .manage(Desktop::default())
        .invoke_handler(tauri::generate_handler![
            launch_backend,
            setup_action,
            close_app,
            viewer_action
        ])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                request_close(window.app_handle().clone(), "window_closed");
            }
        })
        .build(tauri::generate_context!())
        .expect("Cannot initialize Respyra desktop")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                shutdown(&app.state::<Desktop>().engine, "window_closed");
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn shutdown_reaps_normal_failed_and_hung_engines() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        let python = root.join(if cfg!(windows) {
            ".venv/Scripts/python.exe"
        } else {
            ".venv/bin/python"
        });
        for (script, expected) in [
            (
                "import json,sys; assert json.loads(sys.stdin.readline()) == {'action':'shutdown','reason':'window_closed'}",
                true,
            ),
            ("import sys; sys.exit(7)", false),
            ("import time; time.sleep(60)", false),
        ] {
            let mut command = Command::new(&python);
            command
                .args(["-c", script])
                .stdin(Stdio::piped())
                .stdout(Stdio::null())
                .stderr(Stdio::null());
            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                command.creation_flags(0x08000000);
            }
            let mut child = command.spawn().unwrap();
            let desktop = Desktop::default();
            {
                let mut engine = desktop.engine.lock().unwrap();
                engine.input = child.stdin.take();
                engine.child = Some(child);
            }
            assert_eq!(shutdown(&desktop.engine, "window_closed"), expected);
            let engine = desktop.engine.lock().unwrap();
            assert!(engine.child.is_none() && engine.input.is_none());
        }
    }
    #[test]
    fn closed_actions_and_bounds() {
        for invalid in [
            r#"{"action":"shutdown"}"#,
            r#"{"action":"shown","ui_seq":1,"ui_time_ms":1,"path":"x"}"#,
            r#"{"action":"field_edit","ui_seq":1,"ui_time_ms":1,"field":"other","value":"x"}"#,
        ] {
            assert!(serde_json::from_str::<Action>(invalid).is_err());
        }
        assert!(
            encode_action(&Action::Shown {
                ui_seq: 0,
                ui_time_ms: 1.0
            })
            .is_err()
        );
        assert!(
            encode_action(&Action::Shown {
                ui_seq: 1,
                ui_time_ms: f64::NAN
            })
            .is_err()
        );
        assert!(
            encode_action(&Action::FieldEdit {
                ui_seq: 1,
                ui_time_ms: 1.0,
                field: Field::Participant,
                value: "x".repeat(129)
            })
            .is_err()
        );
    }
    #[test]
    fn framed_state_only() {
        assert!(decode_frame("RESPYRA/1 {\"phase\":\"starting\"}\n").is_ok());
        assert!(decode_frame("RESPYRA/1 {\"phase\":\"waiting_recorder\"}\n").is_err());
        assert!(
            decode_frame("ordinary PsychoPy diagnostic\n")
                .unwrap()
                .is_none()
        );
        assert!(
            decode_frame("RESPYRA/1 {\"phase\":\"setup\"}\n")
                .unwrap()
                .is_some()
        );
        assert!(decode_frame("RESPYRA/1 {\"phase\":\"shell\"}\n").is_err());
        assert!(decode_frame("RESPYRA/1 broken\n").is_err());
    }
}

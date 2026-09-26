#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    io::{BufRead, BufReader, Read, Write},
    path::Path,
    process::{Child, ChildStdin, Command, Stdio},
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
    thread,
    time::{Duration, Instant},
};
use tauri::{Emitter, Manager};

const PREFIX: &str = "RESPYRA/1 ";

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
enum Field {
    Participant,
    Session,
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
            })),
            closing: Arc::new(AtomicBool::new(false)),
        }
    }
}

fn publish(app: &tauri::AppHandle, engine: &Arc<Mutex<Engine>>, snapshot: Value) {
    if let Ok(mut state) = engine.lock() {
        state.snapshot = snapshot.clone();
    }
    if let Some(window) = app.get_webview_window("main") {
        if snapshot["phase"] == "experiment" {
            let _ = window.hide();
        } else if snapshot["phase"] == "finished" || snapshot["phase"] == "error" {
            let _ = window.show();
            let _ = window.set_focus();
        }
    }
    let _ = app.emit("setup-state", snapshot);
}

fn decode_frame(line: &str) -> Result<Option<Value>, String> {
    let Some(payload) = line.strip_prefix(PREFIX) else {
        return Ok(None);
    };
    let value: Value = serde_json::from_str(payload).map_err(|e| e.to_string())?;
    if !matches!(
        value["phase"].as_str(),
        Some("waiting_recorder" | "setup" | "experiment" | "finished" | "error")
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

#[tauri::command]
fn setup_action(action: Action, desktop: tauri::State<'_, Desktop>) -> Result<(), String> {
    if desktop.closing.load(Ordering::Acquire) {
        return Err("Desktop is closing".into());
    }
    let bytes = encode_action(&action)?;
    let mut state = desktop
        .engine
        .lock()
        .map_err(|_| "Desktop state lock failed")?;
    if state.snapshot["phase"] != "setup" {
        return Err("Setup is not available".into());
    }
    let input = state
        .input
        .as_mut()
        .ok_or("Experiment engine is not running")?;
    input
        .write_all(&bytes)
        .and_then(|_| input.flush())
        .map_err(|e| e.to_string())
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
            close_app
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

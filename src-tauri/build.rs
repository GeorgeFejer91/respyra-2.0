fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "launch_backend",
            "setup_action",
            "close_app",
            "viewer_action",
            "error_report",
            "report_control_failure",
        ]),
    ))
    .expect("failed to generate desktop command permissions");
}

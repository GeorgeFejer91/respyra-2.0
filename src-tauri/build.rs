fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "launch_backend",
            "setup_action",
            "close_app",
            "viewer_action",
        ]),
    ))
    .expect("failed to generate desktop command permissions");
}
